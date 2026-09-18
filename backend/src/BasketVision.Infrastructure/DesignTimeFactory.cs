using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;

namespace BasketVision.Infrastructure;

public sealed class DesignTimeFactory : IDesignTimeDbContextFactory<BasketVisionDbContext>
{
    public BasketVisionDbContext CreateDbContext(string[] args) => new(
        new DbContextOptionsBuilder<BasketVisionDbContext>().UseNpgsql(
            Environment.GetEnvironmentVariable("ConnectionStrings__Default")
            ?? "Host=localhost;Port=5433;Database=basketvision;Username=basketvision;Password=basketvision").Options);
}
