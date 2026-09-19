using System.Net;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Net.Http.Json;
using BasketVision.Api;
using BasketVision.Domain;
using BasketVision.Infrastructure;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Xunit;

namespace BasketVision.Tests;

public sealed class AdminDashboardTests(ApiFactory factory) : IClassFixture<ApiFactory>
{
    private async Task<(HttpClient Client, Guid UserId, Guid SessionId)> Account(bool admin)
    {
        var client = factory.CreateClient();
        using var scope = factory.Services.CreateScope();
        var users = scope.ServiceProvider.GetRequiredService<UserManager<ApplicationUser>>();
        var db = scope.ServiceProvider.GetRequiredService<BasketVisionDbContext>();
        var email = Guid.NewGuid() + "@dashboard.test";
        var user = new ApplicationUser { Id = Guid.NewGuid(), UserName = email, Email = email };
        Assert.True((await users.CreateAsync(user, "Aa1!" + Guid.NewGuid())).Succeeded);
        Assert.True((await users.AddToRoleAsync(user, admin ? Roles.Admin : Roles.User)).Succeeded);
        db.Subscriptions.Add(new Subscription { UserId = user.Id, PlanId = await db.Plans.Where(p => p.Name == "Free").Select(p => p.Id).SingleAsync() });
        var session = new AuthSession { UserId = user.Id, ExpiresAt = DateTime.UtcNow.AddDays(1) };
        db.AuthSessions.Add(session);
        var tokens = scope.ServiceProvider.GetRequiredService<TokenService>();
        var token = JsonSerializer.SerializeToElement(await tokens.Issue(user, session, new DefaultHttpContext())).GetProperty("accessToken").GetString();
        await db.SaveChangesAsync();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
        return (client, user.Id, session.Id);
    }

    [Fact]
    public async Task Dashboard_is_admin_only()
    {
        Assert.Equal(HttpStatusCode.Unauthorized, (await factory.CreateClient().GetAsync("/api/admin/dashboard")).StatusCode);
        var user = await Account(false);
        Assert.Equal(HttpStatusCode.Forbidden, (await user.Client.GetAsync("/api/admin/dashboard")).StatusCode);
        var admin = await Account(true);
        Assert.Equal(HttpStatusCode.OK, (await admin.Client.GetAsync("/api/admin/dashboard")).StatusCode);
    }

    [Fact]
    public async Task Presence_distinguishes_multiple_sessions_inactivity_revocation_and_expiry()
    {
        var admin = await Account(true);
        var user = await Account(false);
        using var scope = factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<BasketVisionDbContext>();
        var second = new AuthSession { UserId = user.UserId, RefreshTokenHash = Guid.NewGuid().ToString(), ExpiresAt = DateTime.UtcNow.AddHours(1), LastSeenAt = DateTime.UtcNow };
        db.AuthSessions.Add(second); await db.SaveChangesAsync();
        async Task<JsonElement> Row()
        {
            var data = await admin.Client.GetFromJsonAsync<JsonElement>("/api/admin/dashboard");
            return Assert.Single(data.GetProperty("users").EnumerateArray(), row => row.GetProperty("id").GetGuid() == user.UserId);
        }
        var row = await Row();
        Assert.Equal(2, row.GetProperty("onlineSessions").GetInt32());
        Assert.Equal(2, row.GetProperty("validSessions").GetInt32());
        await db.AuthSessions.Where(s => s.UserId == user.UserId).ExecuteUpdateAsync(s => s.SetProperty(x => x.LastSeenAt, DateTime.UtcNow.AddMinutes(-10)));
        row = await Row();
        Assert.Equal(0, row.GetProperty("onlineSessions").GetInt32());
        Assert.Equal(2, row.GetProperty("validSessions").GetInt32());
        // A real authenticated request restores presence, including legacy null timestamps.
        await db.AuthSessions.Where(s => s.Id == user.SessionId).ExecuteUpdateAsync(s => s.SetProperty(x => x.LastSeenAt, (DateTime?)null));
        Assert.Equal(HttpStatusCode.OK, (await user.Client.GetAsync("/auth/me")).StatusCode);
        Assert.Equal(1, (await Row()).GetProperty("onlineSessions").GetInt32());
        await db.AuthSessions.Where(s => s.Id == user.SessionId).ExecuteUpdateAsync(s => s.SetProperty(x => x.RevokedAt, DateTime.UtcNow));
        await db.AuthSessions.Where(s => s.Id == second.Id).ExecuteUpdateAsync(s => s.SetProperty(x => x.ExpiresAt, DateTime.UtcNow.AddMinutes(-1)).SetProperty(x => x.LastSeenAt, DateTime.UtcNow));
        row = await Row();
        Assert.Equal(0, row.GetProperty("onlineSessions").GetInt32());
        Assert.Equal(0, row.GetProperty("validSessions").GetInt32());
    }

    [Fact]
    public async Task Dashboard_exposes_aggregates_but_no_session_credentials()
    {
        var admin = await Account(true);
        var response = await admin.Client.GetAsync("/api/admin/dashboard");
        Assert.Equal("no-store", response.Headers.CacheControl?.ToString());
        var text = await response.Content.ReadAsStringAsync();
        Assert.DoesNotContain("refreshTokenHash", text);
        Assert.DoesNotContain("passwordHash", text);
        Assert.DoesNotContain("accessToken", text);
        var data = JsonDocument.Parse(text).RootElement;
        foreach (var status in Enum.GetNames<AnalysisStatus>()) Assert.True(data.GetProperty("jobs").GetProperty(status).GetInt32() >= 0);
        Assert.True(data.GetProperty("registeredUsers").GetInt32() >= 1);
        Assert.True(data.GetProperty("onlineUsers").GetInt32() >= 1);
        Assert.Equal(5, data.GetProperty("onlineWindowMinutes").GetInt32());
    }
}
