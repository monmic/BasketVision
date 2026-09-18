using BasketVision.Domain;
using Microsoft.EntityFrameworkCore;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;

namespace BasketVision.Infrastructure;

public sealed class BasketVisionDbContext(DbContextOptions<BasketVisionDbContext> options, ICurrentUser? user = null)
    : IdentityDbContext<ApplicationUser, IdentityRole<Guid>, Guid>(options)
{
    private Guid? CurrentUserId => user?.UserId;
    private bool IsAdmin => user?.IsAdmin == true;
    public DbSet<Plan> Plans => Set<Plan>();
    public DbSet<PlanEntitlement> PlanEntitlements => Set<PlanEntitlement>();
    public DbSet<Subscription> Subscriptions => Set<Subscription>();
    public DbSet<UsageRecord> UsageRecords => Set<UsageRecord>();
    public DbSet<AuthSession> AuthSessions => Set<AuthSession>();
    public DbSet<Game> Games => Set<Game>();
    public DbSet<Team> Teams => Set<Team>();
    public DbSet<AnalysisJob> AnalysisJobs => Set<AnalysisJob>();
    public DbSet<GameEvent> GameEvents => Set<GameEvent>();
    public DbSet<Possession> Possessions => Set<Possession>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        base.OnModelCreating(b);
        b.Entity<Plan>().HasIndex(x => x.Name).IsUnique();
        b.Entity<PlanEntitlement>().HasKey(x => new { x.PlanId, x.Feature });
        b.Entity<Plan>().HasMany(x => x.Entitlements).WithOne().HasForeignKey(x => x.PlanId);
        b.Entity<Subscription>().HasIndex(x => x.UserId).IsUnique();
        b.Entity<Subscription>().HasOne<ApplicationUser>().WithMany().HasForeignKey(x => x.UserId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<UsageRecord>().HasIndex(x => new { x.UserId, x.StartedAt });
        b.Entity<UsageRecord>().HasIndex(x => x.AnalysisJobId).IsUnique();
        b.Entity<UsageRecord>().HasOne<ApplicationUser>().WithMany().HasForeignKey(x => x.UserId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<AuthSession>().HasIndex(x => x.RefreshTokenHash).IsUnique();
        b.Entity<AuthSession>().HasOne<ApplicationUser>().WithMany().HasForeignKey(x => x.UserId);
        b.Entity<Game>().HasOne<ApplicationUser>().WithMany().HasForeignKey(x => x.OwnerUserId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<Game>().HasQueryFilter(x => IsAdmin || (CurrentUserId != null && x.OwnerUserId == CurrentUserId));
        b.Entity<AnalysisJob>().HasQueryFilter(x => Games.Any(g => g.Id == x.GameId));
        b.Entity<Team>().HasQueryFilter(x => Games.Any(g => g.Id == x.GameId));
        b.Entity<GameEvent>().HasQueryFilter(x => Games.Any(g => g.Id == x.GameId));
        b.Entity<Possession>().HasQueryFilter(x => Games.Any(g => g.Id == x.GameId));
        b.Entity<Game>().HasKey(x => x.Id);
        b.Entity<Game>().Property(x => x.Name).HasMaxLength(200).IsRequired();
        b.Entity<Game>().HasMany(x => x.Teams).WithOne().HasForeignKey(x => x.GameId).OnDelete(DeleteBehavior.Cascade);
        b.Entity<Team>().HasIndex(x => new { x.GameId, x.Side }).IsUnique();
        b.Entity<AnalysisJob>().HasIndex(x => new { x.Status, x.CreatedAtUtc });
        b.Entity<GameEvent>().HasIndex(x => new { x.GameId, x.VideoTimestamp });
        b.Entity<Possession>().HasIndex(x => new { x.GameId, x.StartTimestamp });
    }
}
