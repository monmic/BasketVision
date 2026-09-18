namespace BasketVision.Domain;

public enum TeamSide { A, B }
public enum AnalysisStatus { Pending, Processing, Completed, Failed, Paused }
public enum DetectionStatus { Detected, Confirmed, Corrected, Rejected }
public enum EventType
{
    ShotMade, ShotMissed, FreeThrowMade, FreeThrowMissed,
    OffensiveRebound, DefensiveRebound, Turnover, Steal,
    Assist, Block, Foul, TechnicalFoul, Violation,
    JumpBall, PeriodStart, PeriodEnd, Timeout
}

public sealed class Team
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid GameId { get; set; }
    public string Name { get; set; } = string.Empty;
    public TeamSide Side { get; set; }
}

public sealed class Game
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid? OwnerUserId { get; set; }
    public long VideoSizeBytes { get; set; }
    public double? VideoDurationSeconds { get; set; }
    public string Name { get; set; } = string.Empty;
    public string? VideoPath { get; set; }
    public DateTime CreatedAtUtc { get; set; } = DateTime.UtcNow;
    public List<Team> Teams { get; set; } = [];
}

public sealed class AnalysisJob
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid GameId { get; set; }
    public AnalysisStatus Status { get; set; } = AnalysisStatus.Pending;
    public int Progress { get; set; }
    public string? Error { get; set; }
    public DateTime CreatedAtUtc { get; set; } = DateTime.UtcNow;
    public DateTime? CompletedAtUtc { get; set; }
}

public sealed class GameEvent
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid GameId { get; set; }
    public Guid AnalysisJobId { get; set; }
    public EventType Type { get; set; }
    public Guid? TeamId { get; set; }
    public double VideoTimestamp { get; set; }
    public double? EndTimestamp { get; set; }
    public double Confidence { get; set; }
    public DetectionStatus Status { get; set; } = DetectionStatus.Detected;
    public string? MetadataJson { get; set; }
}

public sealed class Possession
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid GameId { get; set; }
    public Guid? TeamId { get; set; }
    public double StartTimestamp { get; set; }
    public double EndTimestamp { get; set; }
    public double Confidence { get; set; }
}
