using BasketVision.Application;
using BasketVision.Domain;
using BasketVision.Infrastructure;
using Microsoft.EntityFrameworkCore;
using System.Text.Json.Nodes;

namespace BasketVision.Api;

public static class ShotReviews
{
    public static int? Value(GameEvent ev)
    {
        try { return JsonNode.Parse(ev.MetadataJson ?? "{}")?["shotValue"]?.GetValue<int>() is int v && v is >= 1 and <= 3 ? v : null; }
        catch (Exception ex) when (ex is System.Text.Json.JsonException or InvalidOperationException or FormatException) { return null; }
    }

    public static ShootingDto Shooting(IEnumerable<GameEvent> events, Guid teamId)
    {
        var shots = events.Where(e => e.TeamId == teamId && e.Status is (DetectionStatus.Confirmed or DetectionStatus.Corrected)
            && e.Type is (EventType.ShotMade or EventType.ShotMissed)).ToList();
        var categories = Enumerable.Range(1, 3).Select(value =>
        {
            var attempts = shots.Where(e => Value(e) == value).ToList();
            var made = attempts.Count(e => e.Type == EventType.ShotMade);
            return new ShotCategoryDto(value, made, attempts.Count, attempts.Count == 0 ? null : Math.Round(100d * made / attempts.Count, 1));
        }).ToList();
        return new ShootingDto(categories.Sum(c => c.Value * c.Made), shots.Count(e => Value(e) is null), categories);
    }
    public static Task<IResult> Create(Guid id, ReviewShotRequest req, BasketVisionDbContext db, AccessService access, ICurrentUser user) =>
        Save(id, null, req, db, access, user);

    public static Task<IResult> Update(Guid id, Guid eventId, ReviewShotRequest req, BasketVisionDbContext db, AccessService access, ICurrentUser user) =>
        Save(id, eventId, req, db, access, user);

    private static async Task<IResult> Save(Guid id, Guid? eventId, ReviewShotRequest req, BasketVisionDbContext db, AccessService access, ICurrentUser user)
    {
        var game = await db.Games.Include(g => g.Teams).SingleOrDefaultAsync(g => g.Id == id);
        if (game is null) return Results.NotFound();
        var denial = AccessService.Feature(await access.GetAccess(user.UserId!.Value, user.IsAdmin), Features.AdvancedEvents);
        if (denial != null) return AccessService.Denied(denial);
        var job = await db.AnalysisJobs.SingleOrDefaultAsync(j => j.Id == req.AnalysisJobId && j.GameId == id);
        if (job is null) return Results.BadRequest("Analisi non valida per questa partita.");
        if (job.Status != AnalysisStatus.Completed) return Results.Conflict("Completa l'analisi prima della revisione.");
        if ((req.ShotValue.HasValue && req.ShotValue is not (1 or 2 or 3))
            || req.Type is not (EventType.ShotCandidate or EventType.ShotMade or EventType.ShotMissed)
            || req.Status is not (DetectionStatus.Confirmed or DetectionStatus.Corrected or DetectionStatus.Rejected)
            || !double.IsFinite(req.VideoTimestamp) || req.VideoTimestamp < 0
            || game.VideoDurationSeconds is not double duration || req.VideoTimestamp > duration
            || (req.TeamId.HasValue && !game.Teams.Any(t => t.Id == req.TeamId))
            || (req.Status != DetectionStatus.Rejected && (req.TeamId is null || req.Type == EventType.ShotCandidate)))
            return Results.BadRequest("Indica un timestamp valido, la squadra e l'esito del tiro.");
        GameEvent ev;
        if (eventId.HasValue)
        {
            var existing = await db.GameEvents.SingleOrDefaultAsync(e => e.Id == eventId && e.GameId == id);
            if (existing is null) return Results.NotFound();
            if (existing.AnalysisJobId != req.AnalysisJobId || existing.Type is not (EventType.ShotCandidate or EventType.ShotMade or EventType.ShotMissed))
                return Results.BadRequest("Evento non modificabile come tiro.");
            ev = existing;
        }
        else
        {
            ev = new GameEvent { GameId = id, AnalysisJobId = job.Id, Confidence = 1, MetadataJson = "{\"source\":\"manual-review\"}" };
            db.GameEvents.Add(ev);
        }
        ev.Type = req.Type;
        ev.TeamId = req.TeamId;
        ev.VideoTimestamp = req.VideoTimestamp;
        ev.Status = req.Status;
        var metadata = JsonNode.Parse(ev.MetadataJson ?? "{}")!.AsObject();
        metadata["shotValue"] = req.ShotValue;
        ev.MetadataJson = metadata.ToJsonString();
        await db.SaveChangesAsync();
        return Results.Ok(new { ev.Id });
    }
}
