using System.Security.Claims;
using BasketVision.Domain;
using BasketVision.Infrastructure;
using Microsoft.EntityFrameworkCore;

namespace BasketVision.Api;

public sealed class CurrentUser(IHttpContextAccessor accessor) : ICurrentUser
{
    public Guid? UserId => Guid.TryParse(accessor.HttpContext?.User.FindFirstValue(ClaimTypes.NameIdentifier), out var id) ? id : null;
    public bool IsAdmin => accessor.HttpContext?.User.IsInRole(Roles.Admin) == true;
}

public sealed record AccessFailure(string Code, string Feature, double? Limit, double Current);
public sealed record EntitlementValue(bool? Enabled, long? Limit);
public sealed record AccountAccess(string Plan, bool Bypass, Dictionary<string, EntitlementValue> Entitlements);

public sealed class AccessService(BasketVisionDbContext db, ICurrentUser current)
{
    public async Task LockUser(Guid userId) => await db.Database.ExecuteSqlInterpolatedAsync(
        $"SELECT 1 FROM \"AspNetUsers\" WHERE \"Id\" = {userId} FOR UPDATE");

    public async Task<AccountAccess> GetAccess(Guid userId, bool bypass)
    {
        var now = DateTime.UtcNow;
        var subscription = await db.Subscriptions.AsNoTracking().Include(x => x.Plan).ThenInclude(x => x.Entitlements)
            .SingleOrDefaultAsync(x => x.UserId == userId && x.Status == SubscriptionStatus.Active
                && x.StartsAt <= now && (x.EndsAt == null || x.EndsAt > now));
        return new(subscription?.Plan.Name ?? "Nessun piano attivo", bypass,
            subscription?.Plan.Entitlements.ToDictionary(x => x.Feature, x => new EntitlementValue(x.Enabled, x.Limit)) ?? []);
    }

    public static AccessFailure? Feature(AccountAccess access, string feature) =>
        access.Bypass || (access.Entitlements.TryGetValue(feature, out var value) && value.Enabled == true)
            ? null : new("FEATURE_NOT_AVAILABLE", feature, null, 0);

    public static AccessFailure? Limit(AccountAccess access, string feature, double current)
    {
        if (access.Bypass) return null;
        if (!access.Entitlements.TryGetValue(feature, out var value)) return new("FEATURE_NOT_AVAILABLE", feature, 0, current);
        return value.Limit is { } limit && current > limit ? new("PLAN_LIMIT_EXCEEDED", feature, limit, current) : null;
    }

    public static IResult Denied(AccessFailure failure) => Results.Json(failure, statusCode: StatusCodes.Status403Forbidden);

    public async Task<AccessFailure?> AuthorizeJob(Guid userId, double minutes, bool isNew)
    {
        var access = await GetAccess(userId, current.IsAdmin);
        var error = Feature(access, Features.VideoAnalysis) ?? Limit(access, Features.MaxVideoDurationMinutes, minutes);
        if (error != null) return error;
        var month = MonthStart();
        if (isNew)
        {
            var used = await db.UsageRecords.CountAsync(x => x.UserId == userId && x.StartedAt >= month);
            error = Limit(access, Features.MaxAnalysesPerMonth, used + 1);
            if (error != null) return error;
        }
        // Paused jobs free their slot; resuming must acquire it again under the same user lock.
        var concurrent = await db.AnalysisJobs.IgnoreQueryFilters()
            .Join(db.Games.IgnoreQueryFilters().Where(g => g.OwnerUserId == userId), j => j.GameId, g => g.Id, (j, g) => j)
            .CountAsync(x => x.Status == AnalysisStatus.Pending || x.Status == AnalysisStatus.Processing);
        return Limit(access, Features.MaxConcurrentJobs, concurrent + 1);
    }

    public static DateTime MonthStart() => new(DateTime.UtcNow.Year, DateTime.UtcNow.Month, 1, 0, 0, 0, DateTimeKind.Utc);

    public async Task SyncCompletedUsage(Guid userId)
    {
        await db.UsageRecords.Where(u => u.UserId == userId && u.AnalyzedMinutes == 0
            && db.AnalysisJobs.IgnoreQueryFilters().Any(j => j.Id == u.AnalysisJobId && j.Status == AnalysisStatus.Completed))
            .ExecuteUpdateAsync(s => s.SetProperty(u => u.AnalyzedMinutes, u => u.ReservedMinutes));
    }

    public async Task<object> Me(Guid userId)
    {
        await SyncCompletedUsage(userId);
        var account = await db.Users.AsNoTracking().SingleAsync(x => x.Id == userId);
        var roles = await db.UserRoles.Where(x => x.UserId == userId).Join(db.Roles, x => x.RoleId, r => r.Id, (x,r) => r.Name).ToListAsync();
        var access = await GetAccess(userId, current.IsAdmin);
        var month = MonthStart();
        var usage = await db.UsageRecords.Where(x => x.UserId == userId && x.StartedAt >= month).ToListAsync();
        var storage = await db.Games.IgnoreQueryFilters().Where(x => x.OwnerUserId == userId).SumAsync(x => x.VideoSizeBytes);
        return new { account.Id, account.Email, roles, plan = access.Plan, bypass = access.Bypass, access.Entitlements,
            subscription = await db.Subscriptions.AsNoTracking().Where(x => x.UserId == userId)
                .Select(x => new { x.PlanId, x.StartsAt, x.EndsAt, x.Status }).SingleOrDefaultAsync(),
            usage = new { month, analysesStarted = usage.Count, reservedMinutes = usage.Sum(x => x.ReservedMinutes),
                analyzedMinutes = usage.Sum(x => x.AnalyzedMinutes), storageBytes = storage } };
    }
}
