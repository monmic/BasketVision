using BasketVision.Domain;

namespace BasketVision.Application;

public sealed record CreateGameRequest(string Name, string TeamAName, string TeamBName);
public sealed record RimCalibrationDto(double X, double Y, double Width, double StartSeconds, double EndSeconds);
public sealed record ShotCandidateOptionsDto(bool Enabled, RimCalibrationDto? Rim);
public sealed record StartAnalysisRequest(double? StartSeconds, double? EndSeconds, ShotCandidateOptionsDto? ShotCandidates = null);
public sealed record GameEventDto(Guid Id, EventType Type, string? Team, double VideoTimestamp, double Confidence, DetectionStatus Status);
public sealed record ReportDto(Guid GameId, string GameName, IReadOnlyList<TeamStatDto> Teams, IReadOnlyList<GameEventDto> Events);
public sealed record TeamStatDto(Guid TeamId, string TeamName, Dictionary<string, int> Stats);
