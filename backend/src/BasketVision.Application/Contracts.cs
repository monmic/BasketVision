using BasketVision.Domain;

namespace BasketVision.Application;

public sealed record CreateGameRequest(string Name, string TeamAName, string TeamBName);
public sealed record RimCalibrationDto(double X, double Y, double Width, double StartSeconds, double EndSeconds);
public sealed record ShotCandidateOptionsDto(bool Enabled, RimCalibrationDto? Rim);
public sealed record StartAnalysisRequest(double? StartSeconds, double? EndSeconds, ShotCandidateOptionsDto? ShotCandidates = null);
public sealed record ReviewShotRequest(Guid AnalysisJobId, Guid? TeamId, double VideoTimestamp, EventType Type, DetectionStatus Status, int? ShotValue = null);
public sealed record GameEventDto(Guid Id, EventType Type, string? Team, double VideoTimestamp, double Confidence, DetectionStatus Status, Guid? TeamId, Guid AnalysisJobId, int? ShotValue);
public sealed record ReportDto(Guid GameId, string GameName, IReadOnlyList<TeamStatDto> Teams, IReadOnlyList<GameEventDto> Events);
public sealed record ShotCategoryDto(int Value, int Made, int Attempted, double? Percentage);
public sealed record ShootingDto(int Points, int Unspecified, IReadOnlyList<ShotCategoryDto> Categories);
public sealed record TeamStatDto(Guid TeamId, string TeamName, Dictionary<string, int> Stats, ShootingDto? Shooting = null);
