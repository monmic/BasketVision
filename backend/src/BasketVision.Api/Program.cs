using BasketVision.Application;
using BasketVision.Api;
using BasketVision.Domain;
using BasketVision.Infrastructure;
using Microsoft.EntityFrameworkCore;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Http.Features;

var builder = WebApplication.CreateBuilder(args);
builder.Configuration.AddJsonFile("plans.json", optional: false).AddEnvironmentVariables();
builder.AddAuth();
builder.AddDeploymentConfiguration();
builder.Services.AddSingleton<StoragePaths>();

const long maxVideoUploadBytes = 10L * 1024 * 1024 * 1024; // 10 GB for local development
builder.WebHost.ConfigureKestrel(options => options.Limits.MaxRequestBodySize = maxVideoUploadBytes);
builder.Services.Configure<FormOptions>(options => options.MultipartBodyLengthLimit = maxVideoUploadBytes);
builder.Services.AddDbContext<BasketVisionDbContext>(o => o.UseNpgsql(DeploymentConfiguration.DatabaseConnection(builder.Configuration)));
builder.Services.AddCors(o => o.AddDefaultPolicy(p => p
    .WithOrigins(new[] { builder.Configuration["Frontend:Origin"] ?? "http://localhost:5173", builder.Configuration["Frontend:AdditionalOrigin"] }
        .Where(origin => !string.IsNullOrWhiteSpace(origin)).Select(origin => origin!).ToArray())
    .AllowAnyHeader().AllowAnyMethod().AllowCredentials()));
builder.Services.AddEndpointsApiExplorer();
builder.Services.ConfigureHttpJsonOptions(o => o.SerializerOptions.Converters.Add(new JsonStringEnumConverter()));

var app = builder.Build();
if (string.IsNullOrWhiteSpace(app.Configuration["Auth:SigningKey"]) || System.Text.Encoding.UTF8.GetByteCount(app.Configuration["Auth:SigningKey"]!) < 32)
    throw new InvalidOperationException("Configure Auth__SigningKey with at least 32 random bytes.");
if (!string.IsNullOrWhiteSpace(app.Configuration["ReverseProxy:KnownProxy"])) app.UseForwardedHeaders();
app.UseCors();
app.UseAuthentication();
app.UseAuthorization();
app.UseRateLimiter();
var storage = app.Services.GetRequiredService<StoragePaths>().Root;
Directory.CreateDirectory(Path.Combine(storage, "videos"));
Directory.CreateDirectory(Path.Combine(storage, "analysis"));
await Bootstrap.Initialize(app.Services, app.Configuration);
app.MapAuth();

app.MapGet("/health", () => Results.Ok(new { status = "ok" })).AllowAnonymous();
app.MapGet("/api/health", () => Results.Ok(new { status = "ok" })).AllowAnonymous();

app.MapPost("/api/games", async (CreateGameRequest req, BasketVisionDbContext db, ICurrentUser user) =>
{
    if (string.IsNullOrWhiteSpace(req.Name) || req.Name.Length > 200 || string.IsNullOrWhiteSpace(req.TeamAName) || string.IsNullOrWhiteSpace(req.TeamBName))
        return Results.BadRequest("Nome partita e squadre obbligatori (max 200 caratteri per la partita).");
    var game = new Game { Name = req.Name, OwnerUserId = user.UserId };
    game.Teams.Add(new Team { GameId = game.Id, Name = req.TeamAName, Side = TeamSide.A });
    game.Teams.Add(new Team { GameId = game.Id, Name = req.TeamBName, Side = TeamSide.B });
    db.Games.Add(game);
    await db.SaveChangesAsync();
    return Results.Created($"/api/games/{game.Id}", new { game.Id, game.Name });
});

app.MapGet("/api/games", async (BasketVisionDbContext db) =>
    Results.Ok(await db.Games.Include(x => x.Teams).OrderByDescending(x => x.CreatedAtUtc).ToListAsync()));

app.MapGet("/api/games/{id:guid}", async (Guid id, BasketVisionDbContext db) =>
{
    var game = await db.Games.Include(x => x.Teams).SingleOrDefaultAsync(x => x.Id == id);
    return game is null ? Results.NotFound() : Results.Ok(game);
});

app.MapPost("/api/games/{id:guid}/video", GameMutations.Upload).DisableAntiforgery();

app.MapGet("/api/games/{id:guid}/video", async (Guid id, BasketVisionDbContext db) =>
{
    var game = await db.Games.FindAsync(id);
    if (game?.VideoPath is null || !File.Exists(game.VideoPath)) return Results.NotFound();
    return Results.File(game.VideoPath, "video/mp4", enableRangeProcessing: true);
});

app.MapPost("/api/games/{id:guid}/analysis", GameMutations.Start);

app.MapGet("/api/analysis/{id:guid}", async (Guid id, BasketVisionDbContext db) =>
{
    var job = await db.AnalysisJobs.FindAsync(id);
    return job is null ? Results.NotFound() : Results.Ok(new
    {
        analysisId = job.Id,
        job.GameId,
        job.Status,
        job.Progress,
        job.Error
    });
});

app.MapPost("/api/analysis/{id:guid}/pause", async (Guid id, BasketVisionDbContext db) =>
{
    var job = await db.AnalysisJobs.FindAsync(id);
    if (job is null) return Results.NotFound();
    if (job.Status is AnalysisStatus.Completed or AnalysisStatus.Failed)
        return Results.BadRequest("Completed/failed analyses cannot be paused.");
    job.Status = AnalysisStatus.Paused;
    await db.SaveChangesAsync();
    return Results.Ok(new { analysisId = job.Id, job.GameId, job.Status, job.Progress, job.Error });
});

app.MapPost("/api/analysis/{id:guid}/resume", GameMutations.Resume);

app.MapDelete("/api/analysis/{id:guid}", async (Guid id, BasketVisionDbContext db) =>
{
    var job = await db.AnalysisJobs.FindAsync(id);
    if (job is null) return Results.NotFound();

    if (job.Status == AnalysisStatus.Completed)
        await db.UsageRecords.Where(u => u.AnalysisJobId == id).ExecuteUpdateAsync(s => s.SetProperty(u => u.AnalyzedMinutes, u => u.ReservedMinutes));
    var events = await db.GameEvents.Where(x => x.AnalysisJobId == id).ToListAsync();
    db.GameEvents.RemoveRange(events);
    db.AnalysisJobs.Remove(job);
    await db.SaveChangesAsync();

    foreach (var suffix in new[] { ".json", ".json.tmp", ".request.json", ".checkpoint.json", ".checkpoint.json.tmp" })
    {
        var path = Path.Combine(storage, "analysis", $"{id}{suffix}");
        if (File.Exists(path)) File.Delete(path);
    }
    var debugDirectory = Path.Combine(storage, "analysis", $"{id}.debug");
    if (Directory.Exists(debugDirectory)) Directory.Delete(debugDirectory, recursive: true);
    return Results.NoContent();
});

app.MapGet("/api/analysis/{id:guid}/vision", async (Guid id, BasketVisionDbContext db) =>
{
    var job = await db.AnalysisJobs.FindAsync(id);
    if (job is null) return Results.NotFound();

    var path = Path.Combine(storage, "analysis", $"{id}.json");
    if (!File.Exists(path)) return Results.NotFound();

    var json = await File.ReadAllTextAsync(path);
    return Results.Text(json, "application/json");
});

app.MapGet("/api/analysis/{id:guid}/debug/{fileName}", async (Guid id, string fileName, BasketVisionDbContext db) =>
{
    if (await db.AnalysisJobs.FindAsync(id) is null) return Results.NotFound();
    if (!string.Equals(Path.GetFileName(fileName), fileName, StringComparison.Ordinal)
        || !fileName.EndsWith(".jpg", StringComparison.OrdinalIgnoreCase))
        return Results.BadRequest("Invalid debug asset name.");

    var path = Path.Combine(storage, "analysis", $"{id}.debug", fileName);
    return File.Exists(path) ? Results.File(path, "image/jpeg") : Results.NotFound();
});

app.MapGet("/api/games/{id:guid}/analysis/latest", async (Guid id, BasketVisionDbContext db) =>
{
    var job = await db.AnalysisJobs
        .Where(x => x.GameId == id)
        .OrderByDescending(x => x.CreatedAtUtc)
        .FirstOrDefaultAsync();

    return job is null ? Results.NotFound() : Results.Ok(new
    {
        analysisId = job.Id,
        job.GameId,
        job.Status,
        job.Progress,
        job.Error
    });
});

app.MapGet("/api/analysis/active", async (BasketVisionDbContext db) =>
{
    var jobs = await db.AnalysisJobs
        .Where(x => x.Status == AnalysisStatus.Pending || x.Status == AnalysisStatus.Processing || x.Status == AnalysisStatus.Paused)
        .Join(db.Games,
            job => job.GameId,
            game => game.Id,
            (job, game) => new
            {
                analysisId = job.Id,
                job.GameId,
                gameName = game.Name,
                job.Status,
                job.Progress,
                job.Error,
                job.CreatedAtUtc
            })
        .OrderBy(x => x.CreatedAtUtc)
        .ToListAsync();

    return Results.Ok(jobs);
});

app.MapGet("/api/games/{id:guid}/events", async (Guid id, BasketVisionDbContext db, AccessService access, ICurrentUser user) =>
{
    if (!await db.Games.AnyAsync(g => g.Id == id)) return Results.NotFound();
    var denial = AccessService.Feature(await access.GetAccess(user.UserId!.Value, user.IsAdmin), Features.AdvancedEvents);
    if (denial != null) return AccessService.Denied(denial);
    var events = await db.GameEvents.Where(x => x.GameId == id).OrderBy(x => x.VideoTimestamp).ToListAsync();
    return Results.Ok(events);
});

app.MapGet("/api/games/{id:guid}/report", async (Guid id, BasketVisionDbContext db, AccessService access, ICurrentUser user) =>
{
    var game = await db.Games.Include(x => x.Teams).SingleOrDefaultAsync(x => x.Id == id);
    if (game is null) return Results.NotFound();
    var denial = AccessService.Feature(await access.GetAccess(user.UserId!.Value, user.IsAdmin), Features.AdvancedEvents);
    if (denial != null) return AccessService.Denied(denial);
    var events = await db.GameEvents.Where(x => x.GameId == id).OrderBy(x => x.VideoTimestamp).ToListAsync();

    var stats = game.Teams.Select(team => new TeamStatDto(team.Id, team.Name, new Dictionary<string, int>
    {
        ["ShotMade"] = events.Count(e => e.TeamId == team.Id && e.Type == EventType.ShotMade),
        ["ShotMissed"] = events.Count(e => e.TeamId == team.Id && e.Type == EventType.ShotMissed),
        ["OffensiveRebound"] = events.Count(e => e.TeamId == team.Id && e.Type == EventType.OffensiveRebound),
        ["DefensiveRebound"] = events.Count(e => e.TeamId == team.Id && e.Type == EventType.DefensiveRebound),
        ["Turnover"] = events.Count(e => e.TeamId == team.Id && e.Type == EventType.Turnover),
        ["Steal"] = events.Count(e => e.TeamId == team.Id && e.Type == EventType.Steal),
        ["Assist"] = events.Count(e => e.TeamId == team.Id && e.Type == EventType.Assist),
        ["Block"] = events.Count(e => e.TeamId == team.Id && e.Type == EventType.Block)
    })).ToList();

    var eventDtos = events.Select(e => new GameEventDto(e.Id, e.Type,
        game.Teams.FirstOrDefault(t => t.Id == e.TeamId)?.Name,
        e.VideoTimestamp, e.Confidence, e.Status)).ToList();

    return Results.Ok(new ReportDto(game.Id, game.Name, stats, eventDtos));
});

app.Run();

public partial class Program { }
