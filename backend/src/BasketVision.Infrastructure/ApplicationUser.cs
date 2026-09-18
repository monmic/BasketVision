using Microsoft.AspNetCore.Identity;

namespace BasketVision.Infrastructure;

public sealed class ApplicationUser : IdentityUser<Guid> { }

public sealed class AuthSession
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid UserId { get; set; }
    public string RefreshTokenHash { get; set; } = "";
    public DateTime ExpiresAt { get; set; }
    public DateTime? RevokedAt { get; set; }
}
