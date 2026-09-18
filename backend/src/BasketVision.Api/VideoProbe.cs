using System.Diagnostics;
using System.Globalization;

namespace BasketVision.Api;

public interface IVideoProbe { Task<double> Duration(string path, CancellationToken cancellationToken = default); }

public sealed class VideoProbe : IVideoProbe
{
    public async Task<double> Duration(string path, CancellationToken cancellationToken = default)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(30));
        var start = new ProcessStartInfo("ffprobe") { RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false };
        foreach (var arg in new[] { "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path }) start.ArgumentList.Add(arg);
        using var process = Process.Start(start) ?? throw new InvalidOperationException("ffprobe unavailable");
        var outputTask = process.StandardOutput.ReadToEndAsync(timeout.Token);
        var errorTask = process.StandardError.ReadToEndAsync(timeout.Token);
        try { await process.WaitForExitAsync(timeout.Token); }
        catch { if (!process.HasExited) process.Kill(true); throw; }
        var output = await outputTask;
        await errorTask;
        if (process.ExitCode != 0 || !double.TryParse(output.Trim(), CultureInfo.InvariantCulture, out var duration) || !double.IsFinite(duration) || duration <= 0)
            throw new InvalidDataException("Il file non contiene un video con durata valida.");
        return duration;
    }
}
