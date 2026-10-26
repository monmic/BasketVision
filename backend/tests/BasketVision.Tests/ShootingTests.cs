using BasketVision.Api;
using BasketVision.Domain;
using Xunit;

namespace BasketVision.Tests;

public sealed class ShootingTests
{
    [Fact] public void Points_and_percentages_exclude_unclassified_and_unreviewed_shots()
    {
        var team = Guid.NewGuid();
        GameEvent Shot(int? value, EventType type, DetectionStatus status = DetectionStatus.Confirmed) => new()
        { TeamId = team, Type = type, Status = status, MetadataJson = value.HasValue ? $"{{\"shotValue\":{value}}}" : null };
        var events = new[] {
            Shot(2, EventType.ShotMade), Shot(2, EventType.ShotMissed),
            Shot(3, EventType.ShotMade, DetectionStatus.Corrected), Shot(1, EventType.ShotMade),
            Shot(null, EventType.ShotMade), Shot(3, EventType.ShotMade, DetectionStatus.Rejected),
            Shot(3, EventType.ShotMade, DetectionStatus.Detected), Shot(3, EventType.ShotCandidate)
        };
        var report = ShotReviews.Shooting(events, team);
        Assert.Equal(6, report.Points);
        Assert.Equal(1, report.Unspecified);
        Assert.Equal(50d, report.Categories.Single(c => c.Value == 2).Percentage);
        Assert.Equal(2, report.Categories.Single(c => c.Value == 2).Attempted);
        Assert.Equal(100d, report.Categories.Single(c => c.Value == 1).Percentage);
        Assert.All(ShotReviews.Shooting(events, Guid.NewGuid()).Categories, c => Assert.Null(c.Percentage));
    }
}
