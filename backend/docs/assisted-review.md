# Revisione assistita — MVP

**Direzione superata:** l'utente ha chiarito che il riconoscimento deve essere
automatico. L'annotazione manuale resta uno strumento facoltativo di verifica,
raccolto in sezioni chiuse nell'interfaccia; non è il percorso principale né
la soluzione proposta per ottenere gli eventi dal video. La scelta descritta
sotto documenta la consegna precedente.

Scelta prodotto del 26 ottobre 2026: rendere utilizzabile il percorso assistito
per i tiri prima di proseguire con il riconoscimento automatico degli eventi.

## Percorso disponibile

1. Crea o seleziona una partita e carica un video locale.
2. Premi **Inizia revisione assistita**. Non serve una precedente analisi CV.
3. Porta il video sul tiro e premi **Aggiungi tiro dalla posizione del video**.
   Il video si ferma; indica squadra, valore (libero, 2 o 3 punti) ed esito.
4. Salva, correggi o scarta i tiri nella timeline. Punti e percentuali si
   aggiornano usando solo eventi confermati o corretti.
5. Ricaricando la pagina si ripristina la sessione indicata nell'URL.
   **Riprendi revisione assistita** riapre gli stessi dati senza duplicarli.
6. Esporta il CSV se la relativa funzionalità è inclusa nell'abbonamento.

Le sessioni assistite usano il contenitore di eventi esistente (`AnalysisJob`)
con `IsManualReview=true`, stato Completed e nessuna prenotazione di minuti.
Il worker elabora soltanto i job Pending: la revisione non avvia CV.
Restano necessari proprietà della partita, video caricato ed entitlement
AdvancedEvents. Nessun cambiamento ai piani o alle quote delle analisi CV.

Analisi CV e diagnostica sono sezioni espandibili e dichiarate sperimentali.
L'eliminazione di una sessione elimina anche i suoi tiri confermati; il dialogo
di conferma lo esplicita. Non elimina partita o video.

## Coda di questa consegna

- [x] Sessione assistita persistente senza attesa del worker.
- [x] Inserimento dalla posizione video, correzione, scarto e timeline ordinata.
- [x] Ripristino sessione via URL; squadra e valore riutilizzati nel prossimo tiro.
- [x] Feedback di salvataggio e recupero del report senza ripetere l'inserimento.
- [x] Statistiche confermate ed export con controllo delle capability.
- [x] Build, test backend e verifica browser desktop/mobile con API isolate.

Questa coda implementativa è completata. Il riconoscimento automatico di tiri,
canestri e squadre resta fuori da questa consegna e non è dichiarato disponibile.
La coda diagnostica CV precedente resta chiusa senza promuovere varianti.

## Validazione e rilascio

- `npm run build` nel frontend (TypeScript, Vite, prerender pubblico/private).
- Build .NET 8 e test mirati AuthorizationTests, ShootingTests, ReportExport.
- Esito locale: build frontend e backend riuscite, 29 test superati includendo
  AdminDashboardTests; verifica browser superata anche su localhost:5173.
- `tests/assisted_review_smoke.py` contro il frontend compilato, con Playwright
  già disponibile nell'ambiente di sviluppo. Usa fixture API isolate e non
  modifica partite reali. Verifica apertura, timestamp, inserimento, refresh,
  correzione, scarto, errore report, CSV e viewport mobile.
- Migrazione additiva `20261026160000_ManualReview`: colonna booleana
  `AnalysisJobs.IsManualReview`, default false per i job esistenti.
  Applicata dal normale avvio API; nessuna nuova configurazione o dipendenza
  applicativa. Per il rilascio servono le immagini aggiornate API e web.
