using BasketVision.Domain;
using BasketVision.Infrastructure;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;

namespace BasketVision.Api;

public static class Bootstrap
{
    public static async Task Initialize(IServiceProvider services, IConfiguration config)
    {
        using var scope = services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<BasketVisionDbContext>();
        await db.Database.OpenConnectionAsync();
        await db.Database.ExecuteSqlRawAsync("SELECT pg_advisory_lock(824719321)");
        try
        {
            await AdoptLegacySchema(db);
            await db.Database.MigrateAsync();
            foreach (var section in config.GetSection("Plans").GetChildren())
            {
                var plan = await db.Plans.Include(x => x.Entitlements).SingleOrDefaultAsync(x => x.Name == section.Key);
                // Seed once. Runtime plan edits are not overwritten by an API restart.
                if (plan != null) continue;
                plan = new Plan { Name = section.Key };
                foreach (var item in section.GetChildren())
                {
                    var value = new PlanEntitlement { PlanId = plan.Id, Feature = item.Key };
                    if (bool.TryParse(item.Value, out var enabled)) value.Enabled = enabled;
                    else if (long.TryParse(item.Value, out var limit) && limit >= 0) value.Limit = limit;
                    else throw new InvalidOperationException($"Invalid entitlement {section.Key}/{item.Key}");
                    plan.Entitlements.Add(value);
                }
                db.Plans.Add(plan);
            }
            await db.SaveChangesAsync();
            var roles = scope.ServiceProvider.GetRequiredService<RoleManager<IdentityRole<Guid>>>();
            foreach (var role in new[] { Roles.Admin, Roles.User })
                if (!await roles.RoleExistsAsync(role)) Check(await roles.CreateAsync(new IdentityRole<Guid>(role)));
            var users = scope.ServiceProvider.GetRequiredService<UserManager<ApplicationUser>>();
            foreach (var seed in new[] { ("Admin", Roles.Admin), ("Demo", Roles.User) })
            {
                var email = config[$"Seed:{seed.Item1}:Email"];
                var password = config[$"Seed:{seed.Item1}:Password"];
                if (string.IsNullOrWhiteSpace(email) && string.IsNullOrWhiteSpace(password)) continue;
                if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(password)) throw new InvalidOperationException($"Configure both Seed:{seed.Item1}:Email and Password.");
                var user = await users.FindByEmailAsync(email);
                if (user == null)
                {
                    user = new ApplicationUser { Id = Guid.NewGuid(), Email = email, UserName = email, EmailConfirmed = true };
                    Check(await users.CreateAsync(user, password));
                    Check(await users.AddToRoleAsync(user, seed.Item2));
                }
                // Existing users' passwords and roles are never silently replaced by the seed.
                if (!await db.Subscriptions.AnyAsync(s => s.UserId == user.Id))
                    db.Subscriptions.Add(new Subscription { UserId = user.Id, PlanId = await db.Plans.Where(p => p.Name == "Free").Select(p => p.Id).SingleAsync() });
            }
            await db.SaveChangesAsync();
        }
        finally
        {
            await db.Database.ExecuteSqlRawAsync("SELECT pg_advisory_unlock(824719321)");
            await db.Database.CloseConnectionAsync();
        }
    }

    private static void Check(IdentityResult result)
    {
        if (!result.Succeeded) throw new InvalidOperationException(string.Join("; ", result.Errors.Select(e => e.Description)));
    }

    private static async Task AdoptLegacySchema(BasketVisionDbContext db)
    {
        var tables = await db.Database.SqlQueryRaw<string>("SELECT table_name AS \"Value\" FROM information_schema.tables WHERE table_schema = 'public'").ToListAsync();
        if (tables.Contains("__EFMigrationsHistory") || !tables.Contains("Games")) return;
        var expected = new Dictionary<string, string[]> {
            ["Games"] = ["Id", "Name", "VideoPath", "CreatedAtUtc"],
            ["Teams"] = ["Id", "GameId", "Name", "Side"],
            ["AnalysisJobs"] = ["Id", "GameId", "Status", "Progress", "Error", "CreatedAtUtc", "CompletedAtUtc"],
            ["GameEvents"] = ["Id", "GameId", "AnalysisJobId", "Type", "TeamId", "VideoTimestamp", "EndTimestamp", "Confidence", "Status", "MetadataJson"],
            ["Possessions"] = ["Id", "GameId", "TeamId", "StartTimestamp", "EndTimestamp", "Confidence"]
        };
        foreach (var (table, columns) in expected)
        {
            var existing = await db.Database.SqlQuery<string>($"SELECT column_name AS \"Value\" FROM information_schema.columns WHERE table_schema = 'public' AND table_name = {table}").ToListAsync();
            if (!existing.Order().SequenceEqual(columns.Order()))
                throw new InvalidOperationException($"Legacy schema differs at {table}; migration stopped. Restore/inspect the database before retrying.");
        }
        await using var tx = await db.Database.BeginTransactionAsync();
        await db.Database.ExecuteSqlRawAsync("""
            CREATE TABLE "__EFMigrationsHistory" ("MigrationId" varchar(150) PRIMARY KEY, "ProductVersion" varchar(32) NOT NULL);
            INSERT INTO "__EFMigrationsHistory" VALUES ('20260918205823_LegacyBaseline', '8.0.31');
            """);
        await tx.CommitAsync();
    }
}
