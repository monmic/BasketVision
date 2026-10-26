using System.Globalization;
using System.Text;
using BasketVision.Domain;
using BasketVision.Infrastructure;
using Microsoft.EntityFrameworkCore;

namespace BasketVision.Api;

public static class ReportExport
{
    public static async Task<IResult> Download(Guid id, Guid? analysisId, BasketVisionDbContext db, AccessService access, ICurrentUser user)
    {
        var game = await db.Games.Include(g => g.Teams).SingleOrDefaultAsync(g => g.Id == id);
        if (game is null) return Results.NotFound();
        var denial = AccessService.Feature(await access.GetAccess(user.UserId!.Value, user.IsAdmin), Features.AdvancedEvents);
        if (denial != null) return AccessService.Denied(denial);
        var selected = await AnalysisSelection.Resolve(db, id, analysisId);
        if (analysisId.HasValue && selected is null) return Results.NotFound();
        var events = await db.GameEvents.Where(e => e.GameId == id && e.AnalysisJobId == selected).OrderBy(e => e.VideoTimestamp).ThenBy(e => e.Id).ToListAsync();
        return Results.File(Encoding.UTF8.GetPreamble().Concat(Encoding.UTF8.GetBytes(Render(game, events, selected))).ToArray(),
            "text/csv; charset=utf-8", $"basketvision-{id}-{selected}.csv");
    }

    public static string Render(Game game, IReadOnlyList<GameEvent> events, Guid? analysisId = null)
    {
        var csv = new StringBuilder();
        void Row(params object?[] cells) => csv.AppendLine(string.Join(";", cells.Select(Cell)));
        Row("Partita", game.Name);
        Row("Analisi", analysisId);
        Row("Riepilogo squadra", "Punti", "Tiri da specificare", "Categoria", "Segnati", "Tentati", "Percentuale");
        foreach (var team in game.Teams.OrderBy(t => t.Side))
        {
            var shooting = ShotReviews.Shooting(events, team.Id);
            foreach (var category in shooting.Categories)
                Row(team.Name, shooting.Points, shooting.Unspecified,
                    category.Value == 1 ? "Liberi" : $"Da {category.Value}", category.Made, category.Attempted, category.Percentage);
        }
        Row();
        Row("Dettaglio tiri", "Secondi video", "Squadra", "Esito", "Valore", "Stato revisione", "Analisi", "ID evento");
        foreach (var ev in events.Where(e => e.Type is EventType.ShotCandidate or EventType.ShotMade or EventType.ShotMissed))
            Row("Tiro", ev.VideoTimestamp, game.Teams.FirstOrDefault(t => t.Id == ev.TeamId)?.Name ?? "Da attribuire",
                ev.Type == EventType.ShotCandidate ? "Candidato" : ev.Type == EventType.ShotMade ? "Segnato" : "Sbagliato",
                ShotReviews.Value(ev)?.ToString(CultureInfo.InvariantCulture) ?? "Da specificare",
                ev.Status switch { DetectionStatus.Confirmed => "Confermato", DetectionStatus.Corrected => "Confermato e corretto", DetectionStatus.Rejected => "Scartato", _ => "Da revisionare" },
                ev.AnalysisJobId, ev.Id);
        return csv.ToString();
    }

    private static string Cell(object? value)
    {
        var text = value is IFormattable f ? f.ToString(null, CultureInfo.InvariantCulture) : value?.ToString() ?? "";
        // Prevent spreadsheet formulas from user-controlled names, including leading whitespace.
        if (text.TrimStart().FirstOrDefault() is '=' or '+' or '-' or '@') text = "'" + text;
        return "\"" + text.Replace("\"", "\"\"") + "\"";
    }
}
