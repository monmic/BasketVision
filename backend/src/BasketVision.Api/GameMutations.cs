using System.Text.Json;
using BasketVision.Application;
using BasketVision.Domain;
using BasketVision.Infrastructure;
using Microsoft.EntityFrameworkCore;

namespace BasketVision.Api;

public sealed class StoragePaths(IConfiguration configuration)
{
    public string Root { get; } = Path.GetFullPath(configuration["Storage:Root"] ?? "/app/storage");
    public string Analysis(Guid id, string suffix) => Path.Combine(Root, "analysis", id + suffix);
}

public static class GameMutations
{
    public static async Task<IResult> Upload(Guid id, HttpRequest request, BasketVisionDbContext db, ICurrentUser user,
        AccessService access, IVideoProbe probe, StoragePaths storage)
    {
        await using var tx = await db.Database.BeginTransactionAsync();
        // Same lock order for upload/start/resume: owner first, then game.
        var owner = await db.Games.Where(g => g.Id == id).Select(g => new { g.OwnerUserId }).SingleOrDefaultAsync();
        if (owner == null) return Results.NotFound();
        var ownerId = owner.OwnerUserId ?? user.UserId!.Value;
        await access.LockUser(ownerId);
        var game = await db.Games.FromSqlInterpolated($"SELECT * FROM \"Games\" WHERE \"Id\" = {id} FOR UPDATE").SingleOrDefaultAsync();
        if (game == null) return Results.NotFound();
        if (await db.AnalysisJobs.AnyAsync(j => j.GameId == id && (j.Status == AnalysisStatus.Pending || j.Status == AnalysisStatus.Processing || j.Status == AnalysisStatus.Paused)))
            return Results.Conflict(new { code = "VIDEO_IN_USE", message = "Termina o elimina le analisi attive prima di sostituire il video." });
        if (!request.HasFormContentType) return Results.BadRequest("multipart/form-data expected");
        var form = await request.ReadFormAsync();
        var file = form.Files.GetFile("file");
        if (file == null || file.Length == 0) return Results.BadRequest("file is required");
        var account = await access.GetAccess(ownerId, user.IsAdmin);
        var used = await db.Games.IgnoreQueryFilters().Where(g => g.OwnerUserId == ownerId && g.Id != id).SumAsync(g => g.VideoSizeBytes);
        var error = AccessService.Limit(account, Features.MaxStorageBytes, used + file.Length);
        if (error != null) return AccessService.Denied(error);
        var ext = Path.GetExtension(file.FileName).ToLowerInvariant();
        if (!new[] { ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v" }.Contains(ext)) return Results.BadRequest("Formato video non supportato.");
        var path = Path.Combine(storage.Root, "videos", $"{id}-{Guid.NewGuid():N}{ext}");
        var previous = game.VideoPath;
        var committed = false;
        try
        {
            await using (var stream = File.Create(path)) await file.CopyToAsync(stream, request.HttpContext.RequestAborted);
            var duration = await probe.Duration(path, request.HttpContext.RequestAborted);
            game.VideoPath = path; game.VideoSizeBytes = file.Length; game.VideoDurationSeconds = duration;
            await db.SaveChangesAsync(); await tx.CommitAsync(); committed = true;
            if (previous != null && File.Exists(previous)) File.Delete(previous);
            return Results.Ok(new { game.Id, fileName = Path.GetFileName(path), game.VideoPath });
        }
        catch (InvalidDataException ex) { return Results.BadRequest(new { code = "INVALID_VIDEO", message = ex.Message }); }
        finally { if (!committed && File.Exists(path)) File.Delete(path); }
    }

    public static async Task<IResult> Start(Guid id, StartAnalysisRequest? req, BasketVisionDbContext db, ICurrentUser user,
        AccessService access, IVideoProbe probe, StoragePaths storage)
    {
        await using var tx = await db.Database.BeginTransactionAsync();
        var owner = await db.Games.Where(g => g.Id == id).Select(g => new { g.OwnerUserId }).SingleOrDefaultAsync();
        if (owner == null) return Results.NotFound();
        var ownerId = owner.OwnerUserId ?? user.UserId!.Value;
        await access.LockUser(ownerId);
        var game = await db.Games.FromSqlInterpolated($"SELECT * FROM \"Games\" WHERE \"Id\" = {id} FOR UPDATE").SingleOrDefaultAsync();
        if (game == null) return Results.NotFound();
        if (string.IsNullOrWhiteSpace(game.VideoPath) || !File.Exists(game.VideoPath)) return Results.BadRequest("Upload a video first.");
        double duration;
        try { duration = game.VideoDurationSeconds ?? await probe.Duration(game.VideoPath); }
        catch (InvalidDataException ex) { return Results.BadRequest(new { code = "INVALID_VIDEO", message = ex.Message }); }
        game.VideoDurationSeconds = duration;
        game.VideoSizeBytes = new FileInfo(game.VideoPath).Length;
        var start = req?.StartSeconds ?? 0;
        var end = req?.EndSeconds ?? duration;
        if (!double.IsFinite(start) || !double.IsFinite(end) || start < 0 || start >= duration || end <= start || end > duration + 0.1)
            return Results.BadRequest(new { code = "INVALID_ANALYSIS_RANGE", message = "DA e A devono essere compresi nella durata del video, con A maggiore di DA." });
        end = Math.Min(end, duration);
        var minutes = (end - start) / 60;
        var error = await access.AuthorizeJob(ownerId, minutes, isNew: true);
        if (error != null) return AccessService.Denied(error);
        var job = new AnalysisJob { GameId = id };
        var path = storage.Analysis(job.Id, ".request.json");
        var committed = false;
        try
        {
            await File.WriteAllTextAsync(path, JsonSerializer.Serialize(new { startSeconds = start, endSeconds = end }));
            db.AnalysisJobs.Add(job);
            db.UsageRecords.Add(new UsageRecord { UserId = ownerId, AnalysisJobId = job.Id, ReservedMinutes = minutes });
            await db.SaveChangesAsync(); await tx.CommitAsync(); committed = true;
            return Results.Accepted($"/api/analysis/{job.Id}", new { analysisId = job.Id, job.GameId, job.Status, job.Progress, job.Error, startSeconds = start, endSeconds = end });
        }
        finally { if (!committed && File.Exists(path)) File.Delete(path); }
    }

    public static async Task<IResult> Resume(Guid id, BasketVisionDbContext db, ICurrentUser user, AccessService access)
    {
        await using var tx = await db.Database.BeginTransactionAsync();
        var owner = await db.AnalysisJobs.Where(j => j.Id == id).Join(db.Games, j => j.GameId, g => g.Id, (j,g) => new { g.OwnerUserId }).SingleOrDefaultAsync();
        if (owner == null) return Results.NotFound();
        var ownerId = owner.OwnerUserId ?? user.UserId!.Value;
        await access.LockUser(ownerId);
        var job = await db.AnalysisJobs.FromSqlInterpolated($"SELECT * FROM \"AnalysisJobs\" WHERE \"Id\" = {id} FOR UPDATE").SingleOrDefaultAsync();
        if (job == null) return Results.NotFound();
        if (job.Status != AnalysisStatus.Paused) return Results.BadRequest("Only paused analyses can be resumed.");
        var usage = await db.UsageRecords.SingleOrDefaultAsync(x => x.AnalysisJobId == id);
        if (usage == null && !user.IsAdmin) return Results.Conflict(new { code = "LEGACY_ANALYSIS", message = "Questa analisi precedente richiede un amministratore per la ripresa." });
        var error = await access.AuthorizeJob(ownerId, usage?.ReservedMinutes ?? 0, isNew: false);
        if (error != null) return AccessService.Denied(error);
        job.Status = AnalysisStatus.Pending; job.Error = null;
        await db.SaveChangesAsync(); await tx.CommitAsync();
        return Results.Ok(new { analysisId = job.Id, job.GameId, job.Status, job.Progress, job.Error });
    }
}
