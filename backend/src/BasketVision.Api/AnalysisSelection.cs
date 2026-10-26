using BasketVision.Infrastructure;
using Microsoft.EntityFrameworkCore;

namespace BasketVision.Api;

public static class AnalysisSelection
{
    public static Task<Guid?> Resolve(BasketVisionDbContext db, Guid gameId, Guid? analysisId) =>
        db.AnalysisJobs.Where(j => j.GameId == gameId && (!analysisId.HasValue || j.Id == analysisId))
            .OrderByDescending(j => j.CreatedAtUtc).ThenByDescending(j => j.Id)
            .Select(j => (Guid?)j.Id).FirstOrDefaultAsync();
}
