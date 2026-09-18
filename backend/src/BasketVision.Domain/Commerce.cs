namespace BasketVision.Domain;

public static class Roles
{
    public const string Admin = "Admin";
    public const string User = "User";
}

public static class Features
{
    public const string VideoAnalysis = "VideoAnalysis";
    public const string AdvancedEvents = "AdvancedEvents";
    public const string ExportCsv = "ExportCsv";
    public const string ExportPdf = "ExportPdf";
    public const string MaxVideoDurationMinutes = "MaxVideoDurationMinutes";
    public const string MaxAnalysesPerMonth = "MaxAnalysesPerMonth";
    public const string MaxConcurrentJobs = "MaxConcurrentJobs";
    public const string MaxStorageBytes = "MaxStorageBytes";
}

public interface ICurrentUser
{
    Guid? UserId { get; }
    bool IsAdmin { get; }
}

public sealed class Plan
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string Name { get; set; } = "";
    public List<PlanEntitlement> Entitlements { get; set; } = [];
}

// Boolean features use Enabled; numeric limits use Limit (null means unlimited).
public sealed class PlanEntitlement
{
    public Guid PlanId { get; set; }
    public string Feature { get; set; } = "";
    public bool? Enabled { get; set; }
    public long? Limit { get; set; }
}

public enum SubscriptionStatus { Active, Suspended, Cancelled }

public sealed class Subscription
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid UserId { get; set; }
    public Guid PlanId { get; set; }
    public Plan Plan { get; set; } = null!;
    public DateTime StartsAt { get; set; } = DateTime.UtcNow;
    public DateTime? EndsAt { get; set; }
    public SubscriptionStatus Status { get; set; } = SubscriptionStatus.Active;
}

// Independent of AnalysisJob's lifetime: deleting an analysis does not refund usage.
public sealed class UsageRecord
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid UserId { get; set; }
    public Guid AnalysisJobId { get; set; }
    public DateTime StartedAt { get; set; } = DateTime.UtcNow;
    public double ReservedMinutes { get; set; }
    public double AnalyzedMinutes { get; set; }
}
