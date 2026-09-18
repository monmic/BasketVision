using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Threading.RateLimiting;
using BasketVision.Domain;
using BasketVision.Infrastructure;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;

namespace BasketVision.Api;

public sealed record LoginRequest(string Email, string Password);
public sealed record AssignPlanRequest(Guid PlanId, DateTime? EndsAt);

public static class Auth
{
    public static void AddAuth(this WebApplicationBuilder builder)
    {
        builder.Services.AddHttpContextAccessor();
        builder.Services.AddScoped<ICurrentUser, CurrentUser>();
        builder.Services.AddScoped<AccessService>();
        builder.Services.AddScoped<TokenService>();
        builder.Services.AddScoped<IVideoProbe, VideoProbe>();
        builder.Services.AddIdentityCore<ApplicationUser>(o => {
            o.User.RequireUniqueEmail = true;
            o.Password.RequiredLength = 12;
            o.Lockout.MaxFailedAccessAttempts = 5;
            o.Lockout.DefaultLockoutTimeSpan = TimeSpan.FromMinutes(15);
        }).AddRoles<IdentityRole<Guid>>().AddEntityFrameworkStores<BasketVisionDbContext>().AddSignInManager();
        builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer(o => {
            var key = builder.Configuration["Auth:SigningKey"]!;
            o.MapInboundClaims = false;
            o.TokenValidationParameters = new TokenValidationParameters {
                ValidateIssuer = true, ValidIssuer = "BasketVision", ValidateAudience = true, ValidAudience = "BasketVision.Web",
                ValidateLifetime = true, ValidateIssuerSigningKey = true, IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(key)),
                ClockSkew = TimeSpan.FromSeconds(10), NameClaimType = ClaimTypes.NameIdentifier, RoleClaimType = ClaimTypes.Role,
                ValidAlgorithms = [SecurityAlgorithms.HmacSha256]
            };
            o.Events = new JwtBearerEvents {
                OnMessageReceived = ctx => {
                    var path = ctx.Request.Path.Value ?? "";
                    // Native video/img requests cannot attach Authorization. Never accept this cookie for mutations.
                    if (!ctx.Request.Headers.ContainsKey("Authorization") && (HttpMethods.IsGet(ctx.Request.Method) || HttpMethods.IsHead(ctx.Request.Method))
                        && (path.EndsWith("/video", StringComparison.Ordinal) || path.Contains("/debug/", StringComparison.Ordinal)))
                        ctx.Token = ctx.Request.Cookies["bv_media"];
                    return Task.CompletedTask;
                },
                OnTokenValidated = async ctx => {
                    if (!Guid.TryParse(ctx.Principal?.FindFirstValue("sid"), out var sid)
                        || !Guid.TryParse(ctx.Principal?.FindFirstValue(ClaimTypes.NameIdentifier), out var uid)) { ctx.Fail("Invalid session"); return; }
                    var db = ctx.HttpContext.RequestServices.GetRequiredService<BasketVisionDbContext>();
                    if (!await db.AuthSessions.AnyAsync(s => s.Id == sid && s.UserId == uid && s.RevokedAt == null && s.ExpiresAt > DateTime.UtcNow))
                    { ctx.Fail("Session expired"); return; }
                    var account = await db.Users.FindAsync(uid);
                    if (account == null || account.LockoutEnd > DateTimeOffset.UtcNow) { ctx.Fail("Account unavailable"); return; }
                    var identity = (ClaimsIdentity)ctx.Principal!.Identity!;
                    foreach (var claim in identity.FindAll(ClaimTypes.Role).ToList()) identity.RemoveClaim(claim);
                    var roles = await db.UserRoles.Where(r => r.UserId == uid).Join(db.Roles, r => r.RoleId, r => r.Id, (ur,r) => r.Name).ToListAsync();
                    foreach (var role in roles) identity.AddClaim(new Claim(ClaimTypes.Role, role!));
                }
            };
        });
        builder.Services.AddAuthorization(o => o.FallbackPolicy = new AuthorizationPolicyBuilder().RequireAuthenticatedUser().Build());
        builder.Services.AddRateLimiter(o => {
            o.RejectionStatusCode = 429;
            o.AddPolicy("login", context => RateLimitPartition.GetFixedWindowLimiter(
                context.Connection.RemoteIpAddress?.ToString() ?? "unknown", _ => new FixedWindowRateLimiterOptions {
                    PermitLimit = 20, Window = TimeSpan.FromMinutes(1), QueueLimit = 0 }));
        });
    }

    public static void MapAuth(this WebApplication app)
    {
        app.MapPost("/auth/login", async (LoginRequest request, SignInManager<ApplicationUser> signIn, UserManager<ApplicationUser> users,
            BasketVisionDbContext db, TokenService tokens, HttpContext http) => {
            if (string.IsNullOrWhiteSpace(request.Email) || string.IsNullOrEmpty(request.Password)) return Results.Unauthorized();
            var user = await users.FindByEmailAsync(request.Email);
            if (user == null || !(await signIn.CheckPasswordSignInAsync(user, request.Password, lockoutOnFailure: true)).Succeeded)
                return Results.Json(new { code = "INVALID_CREDENTIALS", message = "Credenziali non valide o account temporaneamente bloccato." }, statusCode: 401);
            var session = new AuthSession { UserId = user.Id, ExpiresAt = DateTime.UtcNow.AddDays(7) };
            db.AuthSessions.Add(session);
            var result = await tokens.Issue(user, session, http);
            await db.SaveChangesAsync();
            return Results.Ok(result);
        }).AllowAnonymous().RequireRateLimiting("login");

        app.MapPost("/auth/refresh", async (HttpContext http, BasketVisionDbContext db, TokenService tokens) => {
            if (http.Request.Headers["X-BasketVision-CSRF"] != "1" || !http.Request.Cookies.TryGetValue("bv_refresh", out var refresh))
                return Results.Unauthorized();
            var hash = TokenService.Hash(refresh);
            await using var tx = await db.Database.BeginTransactionAsync();
            var session = await db.AuthSessions.FromSqlInterpolated($"SELECT * FROM \"AuthSessions\" WHERE \"RefreshTokenHash\" = {hash} FOR UPDATE").SingleOrDefaultAsync();
            if (session == null || session.RevokedAt != null || session.ExpiresAt <= DateTime.UtcNow) return Results.Unauthorized();
            var user = await db.Users.FindAsync(session.UserId);
            if (user == null || user.LockoutEnd > DateTimeOffset.UtcNow) return Results.Unauthorized();
            var result = await tokens.Issue(user, session, http);
            await db.SaveChangesAsync();
            await tx.CommitAsync();
            return Results.Ok(result);
        }).AllowAnonymous().RequireRateLimiting("login");

        app.MapPost("/auth/logout", async (HttpContext http, BasketVisionDbContext db) => {
            var sid = Guid.Parse(http.User.FindFirstValue("sid")!);
            await db.AuthSessions.Where(x => x.Id == sid).ExecuteUpdateAsync(s => s.SetProperty(x => x.RevokedAt, DateTime.UtcNow));
            http.Response.Cookies.Delete("bv_refresh", new CookieOptions { Path = "/auth" });
            http.Response.Cookies.Delete("bv_media", new CookieOptions { Path = "/api" });
            return Results.NoContent();
        });
        app.MapGet("/auth/me", async (ICurrentUser user, AccessService access) => Results.Ok(await access.Me(user.UserId!.Value)));

        var admin = app.MapGroup("/api/admin").RequireAuthorization(p => p.RequireRole(Roles.Admin));
        admin.MapGet("/plans", async (BasketVisionDbContext db) => Results.Ok(await db.Plans.Include(x => x.Entitlements).ToListAsync()));
        admin.MapGet("/users", async (BasketVisionDbContext db) => Results.Ok(await db.Users
            .Select(u => new { u.Id, u.Email, subscription = db.Subscriptions.Where(s => s.UserId == u.Id)
                .Select(s => new { s.PlanId, plan = s.Plan.Name, s.Status, s.StartsAt, s.EndsAt }).FirstOrDefault() }).ToListAsync()));
        admin.MapPut("/users/{id:guid}/subscription", async (Guid id, AssignPlanRequest request, BasketVisionDbContext db, AccessService access) => {
            if (request.EndsAt is { } end && (end.Kind != DateTimeKind.Utc || end <= DateTime.UtcNow)) return Results.BadRequest("EndsAt deve essere una data UTC futura.");
            await using var tx = await db.Database.BeginTransactionAsync();
            await access.LockUser(id);
            if (!await db.Users.AnyAsync(x => x.Id == id) || !await db.Plans.AnyAsync(x => x.Id == request.PlanId)) return Results.NotFound();
            var sub = await db.Subscriptions.SingleOrDefaultAsync(x => x.UserId == id);
            if (sub == null) { sub = new Subscription { UserId = id }; db.Subscriptions.Add(sub); }
            sub.PlanId = request.PlanId; sub.StartsAt = DateTime.UtcNow; sub.EndsAt = request.EndsAt; sub.Status = SubscriptionStatus.Active;
            await db.SaveChangesAsync(); await tx.CommitAsync();
            return Results.Ok(new { sub.UserId, sub.PlanId, sub.StartsAt, sub.EndsAt, sub.Status });
        });
    }
}

public sealed class TokenService(IConfiguration config, UserManager<ApplicationUser> users)
{
    public static string Hash(string token) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(token)));
    public async Task<object> Issue(ApplicationUser user, AuthSession session, HttpContext http)
    {
        var expires = DateTime.UtcNow.AddMinutes(15);
        var claims = new List<Claim> { new(ClaimTypes.NameIdentifier, user.Id.ToString()), new("sid", session.Id.ToString()), new(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString()) };
        claims.AddRange((await users.GetRolesAsync(user)).Select(role => new Claim(ClaimTypes.Role, role)));
        var token = new JwtSecurityToken("BasketVision", "BasketVision.Web", claims, expires: expires,
            signingCredentials: new SigningCredentials(new SymmetricSecurityKey(Encoding.UTF8.GetBytes(config["Auth:SigningKey"]!)), SecurityAlgorithms.HmacSha256));
        var access = new JwtSecurityTokenHandler().WriteToken(token);
        var refresh = Convert.ToHexString(RandomNumberGenerator.GetBytes(48));
        session.RefreshTokenHash = Hash(refresh);
        var secure = config.GetValue("Auth:SecureCookies", true);
        http.Response.Cookies.Append("bv_refresh", refresh, new CookieOptions { HttpOnly = true, Secure = secure, SameSite = SameSiteMode.Strict, Path = "/auth", Expires = session.ExpiresAt });
        http.Response.Cookies.Append("bv_media", access, new CookieOptions { HttpOnly = true, Secure = secure, SameSite = SameSiteMode.Strict, Path = "/api", Expires = expires });
        http.Response.Headers.CacheControl = "no-store";
        return new { accessToken = access, expiresAt = expires };
    }
}
