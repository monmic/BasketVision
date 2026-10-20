using BasketVision.Api;
using BasketVision.Domain;
using Xunit;

namespace BasketVision.Tests;

public sealed class ReportExportTests
{
    [Fact] public void Csv_preserves_quoted_names_and_separates_review_states_from_totals()
    {
        var game = new Game { Name = "Partita;\"test\"\nfinale" };
        var team = new Team { GameId = game.Id, Name = "=SUM(A1)", Side = TeamSide.A };
        game.Teams.Add(team);
        var csv = ReportExport.Render(game, new[] {
            new GameEvent { TeamId = team.Id, VideoTimestamp = 435.25, Type = EventType.ShotMade,
                Status = DetectionStatus.Confirmed, MetadataJson = "{\"shotValue\":3}" },
            new GameEvent { TeamId = team.Id, Type = EventType.ShotMade, Status = DetectionStatus.Rejected, MetadataJson = "{\"shotValue\":3}" },
            new GameEvent { Type = EventType.ShotCandidate, Status = DetectionStatus.Detected }
        });
        Assert.Contains("\"Partita;\"\"test\"\"\nfinale\"", csv);
        Assert.Contains("\"'=SUM(A1)\";\"3\";\"0\";\"Da 3\";\"1\";\"1\";\"100\"", csv);
        Assert.Contains("\"435.25\"", csv);
        Assert.Contains("\"Scartato\"", csv);
        Assert.Contains("\"Da revisionare\"", csv);
        Assert.Contains("\"Da specificare\"", csv);
    }
}
