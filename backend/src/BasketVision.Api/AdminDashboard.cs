using BasketVision.Domain;
using BasketVision.Infrastructure;
using Microsoft.EntityFrameworkCore;

namespace BasketVision.Api;

public static class AdminDashboard
{
    public const int OnlineWindowMinutes = 5;

    public static async Task<IResult> Get(BasketVisionDbContext db, HttpContext http)
    {
        http.Response.Headers.CacheControl = "no-store";
        var now = DateTime.UtcNow;
        var cutoff = now.AddMinutes(-OnlineWindowMinutes);
        var month = AccessService.MonthStart();
        var valid = db.AuthSessions.Where(s => s.RevokedAt == null && s.ExpiresAt > now);
        var online = valid.Where(s => s.LastSeenAt >= cutoff);
        var users = await db.Users.Select(u => new {
            u.Id, u.Email,
            plan = db.Subscriptions.Where(s => s.UserId == u.Id && s.Status == SubscriptionStatus.Active
                && s.StartsAt <= now && (s.EndsAt == null || s.EndsAt > now)).Select(s => s.Plan.Name).FirstOrDefault(),
            lastSeenAt = db.AuthSessions.Where(s => s.UserId == u.Id).Max(s => s.LastSeenAt),
            validSessions = valid.Count(s => s.UserId == u.Id),
            onlineSessions = online.Count(s => s.UserId == u.Id)
        }).OrderByDescending(u => u.onlineSessions > 0).ThenByDescending(u => u.lastSeenAt).ThenBy(u => u.Id).Take(100).ToListAsync();
        var jobGroups = await db.AnalysisJobs.GroupBy(j => j.Status).Select(g => new { status = g.Key, count = g.Count() }).ToListAsync();
        var jobs = Enum.GetValues<AnalysisStatus>().ToDictionary(s => s.ToString(), s => jobGroups.FirstOrDefault(g => g.status == s)?.count ?? 0);
        return Results.Ok(new {
            generatedAt = now, onlineWindowMinutes = OnlineWindowMinutes,
            registeredUsers = await db.Users.CountAsync(),
            onlineUsers = await online.Select(s => s.UserId).Distinct().CountAsync(),
            validSessions = await valid.CountAsync(),
            games = await db.Games.CountAsync(),
            videos = await db.Games.CountAsync(g => g.VideoPath != null),
            storageBytes = await db.Games.SumAsync(g => g.VideoSizeBytes),
            videosWithoutSize = await db.Games.CountAsync(g => g.VideoPath != null && g.VideoSizeBytes == 0),
            monthlyAnalysesStarted = await db.UsageRecords.CountAsync(u => u.StartedAt >= month),
            monthlyRequestedMinutes = await db.UsageRecords.Where(u => u.StartedAt >= month).SumAsync(u => u.ReservedMinutes),
            jobs, users
        });
    }
}
