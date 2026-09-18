using BasketVision.Domain;

namespace BasketVision.Application;

public sealed record CreateGameRequest(string Name, string TeamAName, string TeamBName);
public sealed record StartAnalysisRequest(double? StartSeconds, double? EndSeconds);
public sealed record GameEventDto(Guid Id, EventType Type, string? Team, double VideoTimestamp, double Confidence, DetectionStatus Status);
public sealed record ReportDto(Guid GameId, string GameName, IReadOnlyList<TeamStatDto> Teams, IReadOnlyList<GameEventDto> Events);
public sealed record TeamStatDto(Guid TeamId, string TeamName, Dictionary<string, int> Stats);
