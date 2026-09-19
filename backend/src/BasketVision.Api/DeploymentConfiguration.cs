using System.Net;
using Microsoft.AspNetCore.HttpOverrides;
using Npgsql;

namespace BasketVision.Api;

public static class DeploymentConfiguration
{
    public static string? DatabaseConnection(IConfiguration configuration)
    {
        if (string.IsNullOrWhiteSpace(configuration["Database:Host"]))
            return configuration.GetConnectionString("Default");
        return new NpgsqlConnectionStringBuilder {
            Host = configuration["Database:Host"],
            Database = configuration["Database:Name"],
            Username = configuration["Database:User"],
            Password = configuration["Database:Password"]
        }.ConnectionString;
    }

    public static void AddDeploymentConfiguration(this WebApplicationBuilder builder)
    {
        var proxy = builder.Configuration["ReverseProxy:KnownProxy"];
        if (string.IsNullOrWhiteSpace(proxy)) return;
        var address = IPAddress.Parse(proxy);
        builder.Services.Configure<ForwardedHeadersOptions>(options => {
            options.ForwardedHeaders = ForwardedHeaders.XForwardedFor | ForwardedHeaders.XForwardedProto;
            options.ForwardLimit = 1;
            options.KnownNetworks.Clear();
            options.KnownProxies.Clear();
            options.KnownProxies.Add(address);
            options.KnownProxies.Add(address.MapToIPv6());
        });
    }
}
