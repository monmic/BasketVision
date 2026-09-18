using BasketVision.Api;
using BasketVision.Infrastructure;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;
using Xunit;

namespace BasketVision.Tests;

public sealed class MigrationTests
{
    [Fact]
    public async Task Legacy_EnsureCreated_database_is_adopted_without_losing_games()
    {
        var connection=new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("TEST_DATABASE_URL")
            ?? "Host=localhost;Port=5544;Database=basketvision_tests;Username=test;Password=test");
        var database="bv_legacy_"+Guid.NewGuid().ToString("N");
        await using (var admin=new NpgsqlConnection(connection.ConnectionString))
        {
            await admin.OpenAsync();
            await using var command=new NpgsqlCommand($"CREATE DATABASE {database}",admin);
            await command.ExecuteNonQueryAsync();
        }
        connection.Database=database;
        var options=new DbContextOptionsBuilder<BasketVisionDbContext>().UseNpgsql(connection.ConnectionString).Options;
        var gameId=Guid.NewGuid();
        await using (var legacy=new BasketVisionDbContext(options))
        {
            await legacy.GetService<IMigrator>().MigrateAsync("20260918205823_LegacyBaseline");
            await legacy.Database.ExecuteSqlInterpolatedAsync($"INSERT INTO \"Games\" (\"Id\",\"Name\",\"CreatedAtUtc\") VALUES ({gameId},'Legacy game',{DateTime.UtcNow})");
            await legacy.Database.ExecuteSqlRawAsync("DROP TABLE \"__EFMigrationsHistory\"");
        }
        var config=new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string,string?> { ["Plans:Free:VideoAnalysis"]="true" }).Build();
        var services=new ServiceCollection();
        services.AddLogging(); services.AddSingleton<IConfiguration>(config);
        services.AddDbContext<BasketVisionDbContext>(o=>o.UseNpgsql(connection.ConnectionString));
        services.AddIdentityCore<ApplicationUser>().AddRoles<IdentityRole<Guid>>().AddEntityFrameworkStores<BasketVisionDbContext>();
        await using var provider=services.BuildServiceProvider();
        await Bootstrap.Initialize(provider,config);
        await Bootstrap.Initialize(provider,config);
        await using var migrated=new BasketVisionDbContext(options);
        var game=await migrated.Games.IgnoreQueryFilters().SingleAsync();
        Assert.Equal(gameId,game.Id); Assert.Null(game.OwnerUserId);
        Assert.Equal(2,(await migrated.Database.GetAppliedMigrationsAsync()).Count());
        Assert.Empty(await migrated.Games.ToListAsync());
    }
}
