using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using BasketVision.Api;
using BasketVision.Domain;
using BasketVision.Infrastructure;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Xunit;

namespace BasketVision.Tests;

public sealed class ApiFactory : WebApplicationFactory<Program>
{
    public string Storage { get; } = Path.Combine(Path.GetTempPath(), "basketvision-tests-" + Guid.NewGuid());
    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureAppConfiguration((_, c) => c.AddInMemoryCollection(new Dictionary<string,string?> {
            ["ConnectionStrings:Default"] = Environment.GetEnvironmentVariable("TEST_DATABASE_URL") ?? "Host=localhost;Port=5544;Database=basketvision_tests;Username=test;Password=test",
            ["Auth:SigningKey"] = Convert.ToHexString(System.Security.Cryptography.RandomNumberGenerator.GetBytes(48)),
            ["Auth:SecureCookies"] = "false", ["Storage:Root"] = Storage
        }));
        builder.ConfigureServices(s => {
            s.RemoveAll<IVideoProbe>(); s.AddSingleton<IVideoProbe, FakeProbe>();
            // Functional tests share one loopback IP; do not exhaust the production login quota.
            s.AddSingleton<IStartupFilter, TestClientAddress>();
        });
    }
    private sealed class TestClientAddress : IStartupFilter
    {
        private static int nextAddress;
        public Action<Microsoft.AspNetCore.Builder.IApplicationBuilder> Configure(Action<Microsoft.AspNetCore.Builder.IApplicationBuilder> next) => app =>
        {
            Microsoft.AspNetCore.Builder.UseExtensions.Use(app, async (context, nextRequest) =>
            {
                context.Connection.RemoteIpAddress = new IPAddress((long)Interlocked.Increment(ref nextAddress));
                await nextRequest();
            });
            next(app);
        };
    }
    private sealed class FakeProbe : IVideoProbe { public Task<double> Duration(string path, CancellationToken cancellationToken = default) => Task.FromResult(3600d); }
}

public sealed class AuthorizationTests(ApiFactory factory) : IClassFixture<ApiFactory>
{
    private async Task<(HttpClient Client, Guid UserId, Guid GameId)> Account(bool admin = false)
    {
        var client = factory.CreateClient(new WebApplicationFactoryClientOptions { HandleCookies = true });
        using var scope = factory.Services.CreateScope();
        var users = scope.ServiceProvider.GetRequiredService<UserManager<ApplicationUser>>();
        var db = scope.ServiceProvider.GetRequiredService<BasketVisionDbContext>();
        var email = $"{Guid.NewGuid():N}@test.local";
        var password = "T!" + Guid.NewGuid().ToString("N") + "9a";
        var user = new ApplicationUser { Id = Guid.NewGuid(), Email = email, UserName = email };
        Assert.True((await users.CreateAsync(user, password)).Succeeded);
        Assert.True((await users.AddToRoleAsync(user, admin ? Roles.Admin : Roles.User)).Succeeded);
        db.Subscriptions.Add(new Subscription { UserId = user.Id, PlanId = await db.Plans.Where(p => p.Name == "Free").Select(p => p.Id).SingleAsync() });
        var game = new Game { OwnerUserId = user.Id, Name = "Test game", VideoDurationSeconds = 3600 };
        game.VideoPath = Path.Combine(factory.Storage, "videos", game.Id + ".mp4");
        await File.WriteAllBytesAsync(game.VideoPath, [0,1,2,3]); game.VideoSizeBytes = 4;
        db.Games.Add(game); await db.SaveChangesAsync();
        var login = await client.PostAsJsonAsync("/auth/login", new { email, password });
        Assert.Equal(HttpStatusCode.OK, login.StatusCode);
        var body = await login.Content.ReadFromJsonAsync<JsonElement>();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", body.GetProperty("accessToken").GetString());
        return (client, user.Id, game.Id);
    }
    private static Task<HttpResponseMessage> Start(HttpClient client, Guid gameId, double? end = 60) =>
        client.PostAsJsonAsync($"/api/games/{gameId}/analysis", new { startSeconds = 0, endSeconds = end });

    [Fact] public async Task Anonymous_is_401_and_health_is_public()
    {
        var client = factory.CreateClient();
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync("/api/games")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/health")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/health")).StatusCode);
    }
    [Fact] public async Task Free_under_quota_creates_job_and_usage()
    {
        var a = await Account();
        Assert.Equal(HttpStatusCode.Accepted, (await Start(a.Client, a.GameId)).StatusCode);
        var me = await a.Client.GetFromJsonAsync<JsonElement>("/auth/me");
        Assert.Equal(1, me.GetProperty("usage").GetProperty("analysesStarted").GetInt32());
    }
    [Fact] public async Task Shot_candidate_calibration_must_stay_inside_analysis_range()
    {
        var a = await Account();
        var invalid = await a.Client.PostAsJsonAsync($"/api/games/{a.GameId}/analysis", new
        {
            startSeconds = 10,
            endSeconds = 20,
            shotCandidates = new { enabled = true, rim = new { x = 500, y = 200, width = 40, startSeconds = 9, endSeconds = 20 } }
        });
        Assert.Equal(HttpStatusCode.BadRequest, invalid.StatusCode);
        var error = await invalid.Content.ReadFromJsonAsync<JsonElement>();
        Assert.Equal("INVALID_RIM_CALIBRATION", error.GetProperty("code").GetString());

        var valid = await a.Client.PostAsJsonAsync($"/api/games/{a.GameId}/analysis", new
        {
            startSeconds = 10,
            endSeconds = 20,
            shotCandidates = new { enabled = true, rim = new { x = 500, y = 200, width = 40, startSeconds = 10, endSeconds = 20 } }
        });
        Assert.Equal(HttpStatusCode.Accepted, valid.StatusCode);
        var accepted = await valid.Content.ReadFromJsonAsync<JsonElement>();
        var request = JsonDocument.Parse(await File.ReadAllTextAsync(Path.Combine(factory.Storage, "analysis", accepted.GetProperty("analysisId").GetGuid() + ".request.json")));
        Assert.True(request.RootElement.GetProperty("shotCandidates").GetProperty("enabled").GetBoolean());
        Assert.Equal(500, request.RootElement.GetProperty("shotCandidates").GetProperty("rim").GetProperty("x").GetDouble());
    }
    [Fact] public async Task Monthly_quota_survives_job_deletion()
    {
        var a = await Account();
        for (var i = 0; i < 2; i++) {
            var response = await Start(a.Client,a.GameId);
            Assert.Equal(HttpStatusCode.Accepted,response.StatusCode);
            var json = await response.Content.ReadFromJsonAsync<JsonElement>();
            Assert.Equal(HttpStatusCode.NoContent,(await a.Client.DeleteAsync("/api/analysis/" + json.GetProperty("analysisId").GetString())).StatusCode);
        }
        await AssertLimit(await Start(a.Client,a.GameId), Features.MaxAnalysesPerMonth);
    }
    [Theory] [InlineData(660d)] [InlineData(null)]
    public async Task Duration_limit_cannot_be_bypassed_by_omitting_end(double? end)
    {
        var a = await Account();
        await AssertLimit(await Start(a.Client,a.GameId,end), Features.MaxVideoDurationMinutes);
    }
    [Fact] public async Task Admin_bypasses_duration_monthly_and_concurrency()
    {
        var a = await Account(true);
        for (var i=0;i<4;i++) Assert.Equal(HttpStatusCode.Accepted,(await Start(a.Client,a.GameId,null)).StatusCode);
    }
    [Fact] public async Task Other_user_cannot_access_game_video_jobs_or_debug()
    {
        var a = await Account(); var b = await Account();
        var response = await Start(a.Client,a.GameId);
        var job = (await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("analysisId").GetString();
        foreach (var path in new[] {$"/api/games/{a.GameId}",$"/api/games/{a.GameId}/video",$"/api/games/{a.GameId}/report",$"/api/games/{a.GameId}/events",$"/api/analysis/{job}",$"/api/analysis/{job}/vision",$"/api/analysis/{job}/debug/a.jpg"})
            Assert.Equal(HttpStatusCode.NotFound,(await b.Client.GetAsync(path)).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound,(await b.Client.PostAsync($"/api/analysis/{job}/pause",null)).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound,(await b.Client.DeleteAsync($"/api/analysis/{job}")).StatusCode);
        var games = await b.Client.GetFromJsonAsync<JsonElement>("/api/games");
        Assert.DoesNotContain(games.EnumerateArray(), g => g.GetProperty("id").GetGuid()==a.GameId);
    }
    [Fact] public async Task Parallel_requests_cannot_bypass_concurrent_limit()
    {
        var a=await Account();
        var results=await Task.WhenAll(Start(a.Client,a.GameId),Start(a.Client,a.GameId));
        Assert.Single(results, r=>r.StatusCode==HttpStatusCode.Accepted);
        await AssertLimit(results.Single(r=>r.StatusCode==HttpStatusCode.Forbidden),Features.MaxConcurrentJobs);
    }
    [Fact] public async Task Resume_checks_concurrency_without_charging_again()
    {
        var a=await Account();
        var first=await Start(a.Client,a.GameId);
        var id=(await first.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("analysisId").GetString();
        Assert.Equal(HttpStatusCode.OK,(await a.Client.PostAsync($"/api/analysis/{id}/pause",null)).StatusCode);
        Assert.Equal(HttpStatusCode.Accepted,(await Start(a.Client,a.GameId)).StatusCode);
        await AssertLimit(await a.Client.PostAsync($"/api/analysis/{id}/resume",null),Features.MaxConcurrentJobs);
    }
    [Fact] public async Task Logout_revokes_existing_access_token()
    {
        var a=await Account();
        Assert.Equal(HttpStatusCode.NoContent,(await a.Client.PostAsync("/auth/logout",null)).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized,(await a.Client.GetAsync("/auth/me")).StatusCode);
    }
    [Fact] public async Task Refresh_requires_custom_header_and_rotates_token()
    {
        var a=await Account();
        Assert.Equal(HttpStatusCode.Unauthorized,(await a.Client.PostAsync("/auth/refresh",null)).StatusCode);
        a.Client.DefaultRequestHeaders.Add("X-BasketVision-CSRF","1");
        Assert.Equal(HttpStatusCode.OK,(await a.Client.PostAsync("/auth/refresh",null)).StatusCode);
    }
    [Fact] public async Task User_cannot_assign_plan_and_free_events_are_blocked()
    {
        var a=await Account();
        Assert.Equal(HttpStatusCode.Forbidden,(await a.Client.GetAsync("/api/admin/users")).StatusCode);
        Assert.Equal(HttpStatusCode.Forbidden,(await a.Client.GetAsync($"/api/games/{a.GameId}/report")).StatusCode);
    }
    [Fact] public async Task Reviewed_shots_update_statistics_and_reject_foreign_teams()
    {
        var a = await Account(true);
        using var scope = factory.Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<BasketVisionDbContext>();
        var team = new Team { GameId = a.GameId, Name = "Home", Side = TeamSide.A };
        var job = new AnalysisJob { GameId = a.GameId, Status = AnalysisStatus.Completed };
        db.Teams.Add(team); db.AnalysisJobs.Add(job); await db.SaveChangesAsync();
        var path = $"/api/games/{a.GameId}/shots";
        object Body(Guid? teamId, string type, string status) => new { analysisJobId = job.Id, teamId, videoTimestamp = 435, type, status, shotValue = 3 };
        Assert.Equal(HttpStatusCode.BadRequest, (await a.Client.PostAsJsonAsync(path, Body(Guid.NewGuid(), "ShotMade", "Confirmed"))).StatusCode);
        var created = await a.Client.PostAsJsonAsync(path, Body(team.Id, "ShotMade", "Confirmed"));
        Assert.Equal(HttpStatusCode.OK, created.StatusCode);
        var eventId = (await created.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
        var report = await a.Client.GetFromJsonAsync<JsonElement>($"/api/games/{a.GameId}/report");
        Assert.Equal(1, report.GetProperty("teams")[0].GetProperty("stats").GetProperty("ShotMade").GetInt32());
        Assert.Equal(3, report.GetProperty("teams")[0].GetProperty("shooting").GetProperty("points").GetInt32());
        Assert.Equal(3, report.GetProperty("events")[0].GetProperty("shotValue").GetInt32());
        var export = await a.Client.GetAsync($"/api/games/{a.GameId}/report.csv");
        Assert.Equal(HttpStatusCode.OK, export.StatusCode);
        Assert.Equal("text/csv", export.Content.Headers.ContentType?.MediaType);
        Assert.Contains(".csv", export.Content.Headers.ContentDisposition?.FileNameStar ?? "");
        Assert.Contains("\"Home\";\"3\";\"0\";\"Da 3\"", await export.Content.ReadAsStringAsync());
        Assert.Equal(HttpStatusCode.OK, (await a.Client.PutAsJsonAsync(path + "/" + eventId, Body(team.Id, "ShotMissed", "Corrected"))).StatusCode);
        report = await a.Client.GetFromJsonAsync<JsonElement>($"/api/games/{a.GameId}/report");
        Assert.Equal(0, report.GetProperty("teams")[0].GetProperty("stats").GetProperty("ShotMade").GetInt32());
        Assert.Equal(1, report.GetProperty("teams")[0].GetProperty("stats").GetProperty("ShotMissed").GetInt32());
        Assert.Equal(HttpStatusCode.OK, (await a.Client.PutAsJsonAsync(path + "/" + eventId, Body(team.Id, "ShotMissed", "Rejected"))).StatusCode);
        report = await a.Client.GetFromJsonAsync<JsonElement>($"/api/games/{a.GameId}/report");
        Assert.Equal(0, report.GetProperty("teams")[0].GetProperty("stats").GetProperty("ShotMissed").GetInt32());
        var other = await Account();
        Assert.Equal(HttpStatusCode.NotFound, (await other.Client.GetAsync($"/api/games/{a.GameId}/report.csv")).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await other.Client.PutAsJsonAsync(path + "/" + eventId, Body(team.Id, "ShotMade", "Confirmed"))).StatusCode);
    }

    private static async Task AssertLimit(HttpResponseMessage response,string feature)
    {
        Assert.Equal(HttpStatusCode.Forbidden,response.StatusCode);
        var error=await response.Content.ReadFromJsonAsync<JsonElement>();
        Assert.Equal("PLAN_LIMIT_EXCEEDED",error.GetProperty("code").GetString());
        Assert.Equal(feature,error.GetProperty("feature").GetString());
    }

    [Fact] public async Task Admin_can_assign_plan_and_expired_subscription_blocks_analysis()
    {
        var admin=await Account(true); var user=await Account();
        using var scope=factory.Services.CreateScope();
        var db=scope.ServiceProvider.GetRequiredService<BasketVisionDbContext>();
        var planId=await db.Plans.Where(p=>p.Name=="Pro").Select(p=>p.Id).SingleAsync();
        Assert.Equal(HttpStatusCode.OK,(await admin.Client.PutAsJsonAsync($"/api/admin/users/{user.UserId}/subscription",new {planId})).StatusCode);
        var me=await user.Client.GetFromJsonAsync<JsonElement>("/auth/me");
        Assert.Equal("Pro",me.GetProperty("plan").GetString());
        Assert.Equal(HttpStatusCode.Accepted,(await Start(user.Client,user.GameId,660)).StatusCode);
        await db.Subscriptions.Where(s=>s.UserId==user.UserId).ExecuteUpdateAsync(s=>s.SetProperty(x=>x.EndsAt,DateTime.UtcNow.AddDays(-1)));
        Assert.Equal(HttpStatusCode.Forbidden,(await Start(user.Client,user.GameId)).StatusCode);
    }

    [Fact] public async Task Storage_limit_is_enforced_on_upload()
    {
        var a=await Account();
        using var scope=factory.Services.CreateScope();
        var db=scope.ServiceProvider.GetRequiredService<BasketVisionDbContext>();
        db.Games.Add(new Game { OwnerUserId=a.UserId, Name="Existing storage", VideoSizeBytes=2147483648 });
        await db.SaveChangesAsync();
        using var form=new MultipartFormDataContent();
        form.Add(new ByteArrayContent([0,1,2,3]),"file","clip.mp4");
        await AssertLimit(await a.Client.PostAsync($"/api/games/{a.GameId}/video",form),Features.MaxStorageBytes);
    }

    [Fact] public async Task Media_cookie_supports_range_but_cannot_authorize_mutations()
    {
        var a=await Account();
        a.Client.DefaultRequestHeaders.Authorization=null;
        using var request=new HttpRequestMessage(HttpMethod.Get,$"/api/games/{a.GameId}/video");
        request.Headers.Range=new RangeHeaderValue(0,1);
        Assert.Equal(HttpStatusCode.PartialContent,(await a.Client.SendAsync(request)).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized,(await Start(a.Client,a.GameId)).StatusCode);
    }
}
