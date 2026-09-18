# BasketVision CV-02 — Ball Recovery

CV-02 parte da **CV-01.3** e mantiene:

- upload locale
- analisi per intervallo DA → A
- job in background
- pausa / riprendi con checkpoint
- elimina elaborazione

## Obiettivo CV-02

### Aggiornamento CV-02.4 — conferma delle tracce

Il controllo del segmento 11:11–12:12 ha evidenziato falsi positivi durante un'interruzione per fallo, con la palla in mano a un giocatore. La conferma temporale da sola non garantisce che il candidato sia una palla.

CV-02.4 richiede candidati sopra le soglie di nuova track per confermare o riconfermare una traccia. Gli aggiornamenti deboli possono proseguire solo una traccia già confermata, per un massimo di `BALL_TRACK_MAX_WEAK_UPDATES=6` aggiornamenti consecutivi. La soglia finale di accettazione è `BALL_ACCEPTED_MIN_SCORE`; `BALL_TRACK_UPDATE_MIN_SCORE` resta la soglia per l'associazione. La staticità applica una penalità soft, senza escludere automaticamente una palla ferma. I checkpoint conservano il conteggio degli aggiornamenti deboli; quelli precedenti richiedono un candidato forte prima di accettarne altri deboli.

Validazione sul video ancora da eseguire: ricostruire il worker e il frontend con `docker compose up --build`, creare una nuova analisi 00:11:11–00:12:12 e verificare che il report mostri CV-02.4. Confrontare i riquadri con la palla reale, soprattutto a 674,53 s. Una riduzione delle detection non dimostra da sola un miglioramento; controllare anche le palle mancate.

Il test CV-01 sul video 854×480 (00:00:00 → 00:10:22) ha prodotto solo 8 detection palla, 7 frame con palla e 0 track palla. CV-02 separa quindi la pipeline persone dalla pipeline palla.

### Persone

- modello: `YOLO_MODEL` (default `yolo26n.pt`)
- stride: `PERSON_FRAME_STRIDE=3`
- confidence: `PERSON_CONFIDENCE=0.10`
- imgsz: `PERSON_IMGSZ=640`

### Palla

- modello separabile: `BALL_MODEL` (default `yolo26n.pt`)
- stride: `BALL_FRAME_STRIDE=1`
- confidence: `BALL_CONFIDENCE=0.02`
- imgsz: `BALL_IMGSZ=960`
- fallback tiled 2×2 quando il full-frame non rileva la palla
- tiled fallback ogni `BALL_TILE_STRIDE=3` frame palla
- `BALL_TILE_IMGSZ=640`
- semplice linker temporale per assegnare trackId anche prima di avere un detector custom

Il fallback tiled ingrandisce implicitamente gli oggetti piccoli perché ogni porzione di frame viene inferita separatamente.

## Avvio

L'applicazione richiede ora il login. Prima del primo avvio, copiare `.env.example` in `.env` e configurare una chiave JWT casuale di almeno 32 byte e le credenziali seed. In PowerShell è disponibile `./scripts/Initialize-LocalAuth.ps1`: crea il solo `.env` locale con password casuali per `admin@basketvision.local` e `demo@basketvision.local`, senza sovrascrivere file esistenti. Leggere le password localmente da `.env`; non condividerlo né committarlo.

Con HTTP locale usare `AUTH_SECURE_COOKIES=false`; con HTTPS impostare `true`. Il frontend Docker inoltra `/auth` e `/api` all'API sulla stessa origine, preservando cookie, immagini debug e richieste Range del player.

```bash
docker compose down
docker compose up --build
```

Aprire:

- Web: http://localhost:5173
- API: http://localhost:8080
- PostgreSQL host: localhost:5433

## Primo test consigliato (CV-02.3)

Usare lo stesso intervallo già misurato con CV-01 per avere un confronto A/B, oppure 2–3 minuti in cui si sa che ci sono diversi tiri.

Nel pannello **Vision debug — CV-02.3** confrontare soprattutto:

- Raw candidates, accepted detections e rejected candidates
- Raw full-frame e raw tiled (le due inferenze sono indipendenti e poi fuse)
- Confirmed ball tracks (almeno 3 hit consecutive)
- Confidence media/mediana e detection al secondo
- Frame con palla accettata

`BALL_CONFIDENCE` controlla la generazione dei candidati grezzi; `BALL_ACCEPTED_MIN_SCORE` controlla l'accettazione dopo le penalità soft per forma, dimensione e staticità. Se restano quasi nulle, il passo successivo è un `BALL_MODEL` basket-specifico / fine-tuned.

CV-02.3 esporta inoltre campioni JPEG annotati quando `BALL_DEBUG_EXPORT=true`. Il numero massimo e la distanza temporale tra campioni sono regolati da `BALL_DEBUG_MAX_FRAMES` e `BALL_DEBUG_MIN_INTERVAL_SECONDS`. I file mostrano raw candidate in giallo, accepted in verde e rejected in rosso, con track ID, confidence, score finale e motivo della decisione; eliminando l'analisi vengono eliminati anche i relativi asset debug.

Una nuova ball track può partire solo se confidence e soft score superano rispettivamente `BALL_TRACK_NEW_MIN_CONFIDENCE` e `BALL_TRACK_NEW_MIN_SCORE`. `BALL_TRACK_UPDATE_MIN_SCORE` è più permissiva, ma vale soltanto per associare un candidato a una track esistente. Le detection diventano accepted solo dopo la conferma temporale della track.

Il report include anche la diagnostica del person tracker: detection con/senza ID, creazioni, associazioni e fasce di confidence. La variante `person_tracker_diagnostic.yaml` mantiene le soglie TrackTrack predefinite ma usa `gmc_method: none`. Le istanze YOLO person e ball sono separate per impedire alle inferenze tiled della palla di alterare predictor e callback del tracker persone.

## Prestazioni

CV-02 è volutamente più costosa della CV-01. Per velocizzare su CPU:

```yaml
BALL_FRAME_STRIDE: 2
BALL_TILE_STRIDE: 5
BALL_IMGSZ: 768
```

Per massimizzare il recall su un segmento breve:

```yaml
BALL_FRAME_STRIDE: 1
BALL_TILE_STRIDE: 2
BALL_IMGSZ: 960
BALL_CONFIDENCE: 0.02
```

## Modello custom futuro

Quando avremo un detector dedicato alla palla, basterà montare i pesi nel worker e impostare, ad esempio:

```yaml
BALL_MODEL: /app/models/basketball-ball.pt
```

senza modificare API, frontend o gestione job.

## Autenticazione, ruoli e piani

- Identity ASP.NET Core salva utenti, hash password e ruoli in PostgreSQL. I ruoli sono solo `Admin` e `User`; Free/Pro/Advanced sono piani commerciali.
- `POST /auth/login` restituisce un access token JWT (15 minuti). `POST /auth/refresh` ruota un refresh token opaco, conservato solo come hash nel DB e come cookie HttpOnly nel browser; richiede `X-BasketVision-CSRF: 1`. La sessione dura al massimo 7 giorni. `POST /auth/logout` revoca la sessione, compresi i JWT già emessi. `GET /auth/me` espone profilo, piano, subscription, entitlements e utilizzi.
- Il frontend conserva il JWT in memoria, recupera la sessione dopo un reload e usa un cookie HttpOnly solo per le GET di video/debug. Le mutazioni richiedono il Bearer token. `/health` e login/refresh sono pubblici; le API applicative richiedono autenticazione.
- Il seed è opzionale e legge `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD`, `SEED_DEMO_EMAIL`, `SEED_DEMO_PASSWORD`. Non cambia password o ruoli di account esistenti al riavvio. Non c'è registrazione pubblica in questa versione.
- Ogni account seed ha una subscription Free. L'Admin mostra **Unlimited — Admin** e scavalca feature e quote commerciali indipendentemente dal piano, mantenendo validazioni dei file e dei range.
- L'Admin può usare il pannello **Gestione piani utenti** oppure `GET /api/admin/users`, `GET /api/admin/plans` e `PUT /api/admin/users/{id}/subscription` con `{ "planId": "...", "endsAt": null }`. Non sono integrati pagamenti.

I valori iniziali sono in `backend/src/BasketVision.Api/plans.json` e vengono salvati come righe `PlanEntitlements`. Il seed inserisce i piani mancanti, senza sovrascrivere quelli già modificati nel DB. Per nuove installazioni è possibile usare override environment come `Plans__Free__MaxAnalysesPerMonth=4`.

| Entitlement | Free | Pro | Advanced |
|---|---:|---:|---:|
| VideoAnalysis | sì | sì | sì |
| MaxVideoDurationMinutes | 10 | 120 | 180 |
| MaxAnalysesPerMonth | 2 | 20 | 100 |
| MaxConcurrentJobs | 1 | 1 | 3 |
| MaxStorageBytes | 2 GiB | 20 GiB | 100 GiB |
| AdvancedEvents | no | sì | sì |
| ExportCsv | no | sì | sì |
| ExportPdf | no | no | sì |

`AdvancedEvents` protegge gli endpoint eventi/statistiche; Vision Debug e report CV restano disponibili con VideoAnalysis. CSV/PDF sono entitlements predisposti, con stato visibile nell'interfaccia: i generatori di export non sono ancora implementati.

Le analisi avviate sono conteggiate nel mese UTC al momento dell'autorizzazione, anche se falliscono o vengono eliminate. Pausa/ripresa non consuma un'altra analisi; i job Pending/Processing occupano uno slot, quelli Paused no, e la ripresa ricontrolla piano, durata e slot. Un lock PostgreSQL per proprietario rende atomici controllo e prenotazione, anche con richieste simultanee. Gli errori commerciali sono HTTP 403 con `code`, `feature`, `limit`, `current`.

La durata massima riguarda l'intervallo DA/A richiesto, non l'intero file caricato. Il backend legge la durata con ffprobe; se A manca usa la fine reale del video. L'uso distingue minuti richiesti e minuti di analisi completate: questi ultimi vengono consolidati alla lettura di `/auth/me` o all'eliminazione di un job completato. Non viene ancora misurato il lavoro parziale dei job interrotti. Lo storage somma i file video correnti del proprietario; i JPEG debug non rientrano in questa prima quota. Non è possibile sostituire un video con job attivi o in pausa.

## Database e compatibilità

Le migrazioni EF Core sono `LegacyBaseline` (schema CV preesistente) e `AuthPlansOwnership` (Identity, sessioni, piani, subscription, usage e campi video/ownership). L'API usa `Migrate`, non `EnsureCreated`. Per un database CV senza storico migrazioni verifica le colonne delle cinque tabelle esistenti, registra la baseline e applica la migrazione additiva; se trova uno schema diverso si ferma. Un advisory lock serializza la migrazione e il seed tra istanze API.

Prima di aggiornare un database con dati, eseguire un backup PostgreSQL e provarne la migrazione su una copia. Non cancellare il volume con `docker compose down -v`. Le partite precedenti hanno `OwnerUserId = null` e sono accessibili solo agli Admin; non vengono assegnate al DemoUser. Nuove partite e relativi video/job/debug/report sono isolate per proprietario. Nessuna tabella o colonna letta dal worker Python viene rinominata e il worker non conosce piani o ruoli.

## Test

```bash
docker compose build api web worker
docker compose -p basketvision-tests -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tests
```

La suite usa un PostgreSQL Docker separato su tmpfs e HTTP con JWT reali. Verifica quote Free, durata con A omesso, bypass Admin, ownership, 401 anonimi, concorrenza, pausa/ripresa, logout, refresh, assegnazione piani, storage e streaming autenticato. Verifica inoltre l'adozione del vecchio schema e l'idempotenza della migrazione. I test delle quote usano un probe video sostitutivo; ffprobe e la lettura dei video reali vanno verificati anche nello stack completo. Il build frontend include il controllo TypeScript.

Validazione iniziale eseguita: 16 test backend/PostgreSQL, 4 regressioni del tracker nel container Python, smoke browser Admin/Free (login, reload, logout, video e debug), e un upload reale con ffprobe seguito da autorizzazione, pausa/ripresa, completamento CV-02.4, conteggio utilizzi ed eliminazione. Quest'ultimo test usa un database temporaneo separato, senza consumare quote locali. La migrazione è stata provata anche sulla copia del database locale: partita e 6 analisi conservate. Gli script opzionali sono `scripts/smoke_auth.py` (Playwright + Edge, stack locale) e `scripts/smoke_worker.py` (API temporanea sulla porta 18080 e worker/database isolati).

Riferimenti: [JWT bearer in ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/security/authentication/configure-jwt-bearer-authentication) e [migrazioni EF Core](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/).
