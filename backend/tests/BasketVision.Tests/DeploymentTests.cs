using System.Net;
using BasketVision.Api;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.HttpOverrides;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Npgsql;
using Xunit;

namespace BasketVision.Tests;

public sealed class DeploymentTests
{
    [Theory]
    [InlineData("172.30.80.2", true)]
    [InlineData("::ffff:172.30.80.2", true)]
    [InlineData("172.30.80.3", false)]
    public async Task Forwarded_headers_are_only_accepted_from_configured_caddy(string source, bool trusted)
    {
        var builder = WebApplication.CreateBuilder();
        builder.Configuration.AddInMemoryCollection(new Dictionary<string,string?> { ["ReverseProxy:KnownProxy"] = "172.30.80.2" });
        builder.AddDeploymentConfiguration();
        await using var app = builder.Build();
        var options = app.Services.GetRequiredService<IOptions<ForwardedHeadersOptions>>();
        var middleware = new ForwardedHeadersMiddleware(_ => Task.CompletedTask, NullLoggerFactory.Instance, options);
        var context = new DefaultHttpContext();
        context.Connection.RemoteIpAddress = IPAddress.Parse(source);
        context.Request.Scheme = "http";
        context.Request.Headers["X-Forwarded-For"] = "198.51.100.20";
        context.Request.Headers["X-Forwarded-Proto"] = "https";
        await middleware.Invoke(context);
        Assert.Equal(trusted ? "https" : "http", context.Request.Scheme);
        Assert.Equal(trusted ? IPAddress.Parse("198.51.100.20") : IPAddress.Parse(source), context.Connection.RemoteIpAddress);
    }

    [Fact]
    public void Database_password_is_escaped_and_local_connection_string_is_preserved()
    {
        var config = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string,string?> {
            ["ConnectionStrings:Default"] = "Host=local;Database=dev"
        }).Build();
        Assert.Equal("Host=local;Database=dev", DeploymentConfiguration.DatabaseConnection(config));
        var password = "a; b='quoted'\"\\secret";
        config["Database:Host"] = "db"; config["Database:Name"] = "production";
        config["Database:User"] = "test"; config["Database:Password"] = password;
        var parsed = new NpgsqlConnectionStringBuilder(DeploymentConfiguration.DatabaseConnection(config));
        Assert.Equal(password, parsed.Password);
        Assert.Equal("db", parsed.Host);
        Assert.Equal("production", parsed.Database);
    }
}
