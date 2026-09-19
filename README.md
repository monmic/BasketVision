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

## Deploy production/demo su Oracle Cloud

Il file **`docker-compose.prod.yml` è autonomo**: non combinarlo con `docker-compose.yml`. Usa il progetto Docker `basketvision-prod`, una rete e volumi dedicati. Lo sviluppo locale mantiene i propri file, porte, credenziali e dati. Questi comandi sono da eseguire sulla VM Ubuntu; la preparazione del repository non effettua deploy remoti né modifiche DNS.

### Architettura e risorse

Solo Caddy pubblica **80/tcp e 443/tcp**. `/api/*` e `/auth/*` vanno direttamente ad `api:8080`; gli altri percorsi vanno a `web:80`. Non ci sono rewrite: gli endpoint backend includono già quei prefissi. Il frontend usa richieste relative `/api/...` e `/auth/...`, senza localhost. `VITE_API_URL`, se usato in sviluppo, rappresenta l'origine del server, non il prefisso: non impostarlo a `/api`, altrimenti si otterrebbe `/api/api/...`.

PostgreSQL, API, web e worker non pubblicano porte host. La rete bridge consente l'uscita verso Internet, necessaria per ACME e il primo download dei pesi; non è una rete Docker `internal: true`. Caddy ha un IP privato fisso e l'API accetta `X-Forwarded-For/Proto` solo da quell'IP. CORS ammette esclusivamente `https://basketvision.it` e `https://www.basketvision.it`. I cookie di autenticazione sono Secure/HttpOnly. Il web è read-only con directory temporanee scrivibili; API, worker, database e Caddy mantengono le scritture necessarie. Tutti i servizi hanno restart `unless-stopped` e log JSON ruotati a 10 MB × 3 file per container.

**1 GB RAM + 4 GB swap è una configurazione sperimentale per questa pipeline.** Il worker è unico e processa un job alla volta; non usare `--scale worker=2`. I piani possono consentire più job in coda, ma questo non crea processi CV aggiuntivi. Modelli, risoluzioni, stride e soglie restano quelli locali; cambia solo la directory persistente dei pesi. Nessun limite RAM rigido viene imposto, per non causare OOM artificiali. PyTorch, le due istanze YOLO e le build possono comunque esaurire memoria/swap o rendere la VM poco reattiva. Non è garantito il funzionamento del carico CV su 1 GB: iniziare con pochi secondi di video e monitorare. Lo stack può servire come demo di interfaccia anche lasciando il worker fermo (`dc stop worker`).

### 1. Prerequisiti VM

Usare Ubuntu LTS supportata, una VM con IP pubblico raggiungibile, subnet pubblica con route verso Internet Gateway, accesso SSH e spazio disco per immagini Docker, video, swap e backup. Verificare l'architettura con `uname -m`: eventuali immagini compilate altrove devono essere per la stessa architettura. Controllare prima le risorse:

```bash
uname -m
free -h
swapon --show
df -h
```

Se lo swap non è già configurato e `/swapfile` non esiste, predisporre i 4 GB previsti (non sovrascrivere uno swap esistente):

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 2. Docker Engine e Compose

Installare Engine e il plugin Compose dal [repository ufficiale Docker per Ubuntu](https://docs.docker.com/engine/install/ubuntu/), seguendo anche la rimozione di eventuali pacchetti in conflitto prevista dalla guida. Su una VM nuova:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git openssl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
```

I comandi successivi assumono un utente autorizzato a usare Docker; altrimenti anteporre `sudo`. L'accesso al gruppo `docker` equivale a privilegi amministrativi sull'host.

### 3–5. Repository e configurazione separata

```bash
git clone <URL_REPOSITORY> BasketVision
cd BasketVision
umask 077
cp .env.production.example .env.production
chmod 600 .env.production
nano .env.production
```

Compilare `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `AUTH_SIGNING_KEY` e le quattro variabili seed Admin/Demo. Generare segreti distinti con `openssl rand -hex 32`; le password Identity devono includere maiuscola, minuscola, numero e simbolo ed essere lunghe almeno 12 caratteri. Ad esempio il comando `printf 'Aa1!'; openssl rand -hex 24` produce una password casuale con quei requisiti. Non copiare le credenziali del `.env` locale e non committare `.env.production`.

Usare nomi DB/utente semplici (lettere, cifre, underscore). Le password sono passate separatamente, senza concatenarle in un URI: caratteri speciali vengono gestiti dal connection-string builder .NET e dalle variabili libpq `PG*` del worker. Se si usano `$` o `#` nel file env, seguire la sintassi di quoting dotenv; i valori esadecimali generati evitano questa ambiguità.

Se `172.30.80.0/24` collide con reti Docker/VPN esistenti, cambiare insieme `PROD_SUBNET`, `PROD_DYNAMIC_RANGE` e `CADDY_IPV4`. Il range dinamico deve essere contenuto nella subnet; l'IP del proxy deve essere nella subnet ma **fuori dal range dinamico**, libero e diverso dal gateway. Questo impedisce che Docker assegni l'IP fidato a un altro servizio prima dell'avvio di Caddy. `COMPOSE_PARALLEL_LIMIT=1` evita build simultanee tra servizi. Ogni comando deve usare **`--env-file .env.production`**, anche `ps` e `logs`, per non leggere il `.env` di sviluppo. Per comodità, dalla root del repository:

```bash
dc() { docker compose -f docker-compose.prod.yml --env-file .env.production "$@"; }
dc config --quiet
```

`config` senza `--quiet` mostra i segreti risolti: non pubblicarne l'output. Il seed crea gli account al primo avvio e non cambia password/ruoli esistenti. Cambiare `POSTGRES_PASSWORD` nel file dopo l'inizializzazione non cambia automaticamente la password nel database: una rotazione va coordinata con PostgreSQL. Analogamente, modificare le variabili seed non reimposta le password Identity.

### 6–7. DNS e accesso Oracle

Configurare manualmente:

- Record A `basketvision.it` → `PUBLIC_IP_VM`.
- Record A `www.basketvision.it` → `PUBLIC_IP_VM`, oppure CNAME `www` → `basketvision.it`.
- Non lasciare record AAAA verso un IPv6 non raggiungibile dalla VM.
- Nella Security List/NSG applicata alla VNIC: ingress stateful **80/tcp e 443/tcp** da Internet; **22/tcp soltanto dagli IP amministrativi**. Nessuna regola per 5432, 5433, 8080 o 5173.
- Verificare anche il firewall Ubuntu e mantenere le regole di sistema Oracle. Non svuotare indiscriminatamente iptables. Consentire uscita DNS/HTTPS per immagini, dipendenze, pesi e certificati.

Oracle applica controlli sia alla rete sia all'host: vedere [Security Lists](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securitylists.htm) e [firewall nelle immagini Ubuntu OCI](https://blogs.oracle.com/developers/enabling-network-traffic-to-ubuntu-images-in-oracle-cloud-infrastructure).

Caddy avvia il server anche prima della propagazione DNS, ma il certificato pubblico diventerà disponibile solo quando la validazione del dominio riuscirà. Le porte 80/443 devono raggiungere Caddy e il DNS dei due nomi deve essere corretto. I tentativi ACME vengono ripetuti automaticamente; non cancellare i volumi dei certificati per forzarli. Prima di quel momento il redirect HTTP può già funzionare mentre HTTPS/login non sono ancora utilizzabili. Riferimento: [HTTPS automatico Caddy](https://caddyserver.com/docs/automatic-https).

### 8. Primo avvio

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Sulla VM piccola è preferibile compilare esplicitamente in sequenza, prima di avviare i processi:

```bash
dc build api
dc build worker
dc build web
dc up -d --no-build
```

Una singola build può comunque superare la RAM disponibile. Se succede, compilare le immagini su una macchina più capiente della stessa architettura, trasferirle con `docker image save`/`docker image load` e avviare con `--no-build` (i tag predefiniti sono `basketvision-prod-api`, `basketvision-prod-worker`, `basketvision-prod-web`). Non vengono introdotti servizi managed né un registry obbligatorio.

Il worker production usa `vision/Dockerfile.prod`: PyTorch **CPU**, con torch 2.14.0, torchvision 0.29.0 e Ultralytics 8.4.154, le versioni rilevate nel runtime locale durante la preparazione. Si evitano le dipendenze CUDA/NVIDIA scaricate dal Dockerfile generico, senza cambiare algoritmo o modelli. Il Dockerfile locale non cambia. La scelta dell'indice CPU segue le [istruzioni ufficiali PyTorch](https://pytorch.org/get-started/locally/). Le build verificate localmente sono Linux amd64; una VM ARM richiede una build e una verifica dedicate sulla propria architettura.

PostgreSQL diventa healthy prima dell'API; l'API esegue migrazioni e seed prima di ascoltare; worker e web aspettano l'API. La prima analisi può scaricare `yolo26n.pt`, poi conservato nel volume `model_cache`. Per gli accessi iniziali usare le email/password definite nel file production. L'Admin scavalca le quote; il DemoUser parte da Free. Il database production è nuovo: i video e i job locali non sono copiati automaticamente.

### 9–11. Stato, log e test

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f --tail=100
dc logs --tail=100 caddy api worker
dc exec web wget -qO- http://api:8080/health
curl -I http://localhost
curl -I -H 'Host: basketvision.it' http://localhost
curl -I https://basketvision.it
curl -fsS https://basketvision.it/api/health
curl -i https://basketvision.it/api/games
```

Il test HTTP con `Host: basketvision.it` deve mostrare il redirect a HTTPS; `localhost` da solo non verifica il virtual host del dominio. Dopo DNS/certificati, frontend e `/api/health` devono rispondere; `/api/games` senza Bearer token deve restituire **401**. Nel browser verificare login, upload di un breve video, range DA/A, avvio, pausa/ripresa, completamento e Vision Debug. Durante il test:

```bash
docker stats --no-stream
free -h
swapon --show
df -h
docker system df
sudo journalctl -k --since '1 hour ago' | grep -Ei 'oom|out of memory|killed process'
```

Un container avviato non dimostra che la VM possa sostenere un'analisi. Se lo swap cresce continuamente o interviene l'OOM killer, fermare il worker e aumentare le risorse prima di usarlo stabilmente.

### Persistenza, spazio disco e backup minimo

I volumi del progetto sono:

| Volume (prefisso `basketvision-prod_`) | Contenuto |
|---|---|
| `postgres_data` | PostgreSQL, utenti, piani e job |
| `storage_data` | `/app/storage/videos` e `/app/storage/analysis`, inclusi checkpoint e debug |
| `caddy_data`, `caddy_config` | Certificati/chiavi TLS e stato Caddy |
| `api_keys` | Chiavi Data Protection ASP.NET |
| `model_cache` | Pesi YOLO e impostazioni Ultralytics |

Su Docker Linux rootful i volumi risiedono normalmente sotto `/var/lib/docker/volumes`; usare `inspect` per il percorso effettivo, senza modificarli a mano:

```bash
docker volume ls --filter label=com.docker.compose.project=basketvision-prod
docker volume inspect basketvision-prod_postgres_data basketvision-prod_storage_data
dc exec api du -sh /app/storage/videos /app/storage/analysis
df -h
docker system df
```

Prima di aggiornamenti o backup coerenti, mettere in pausa i job dall'interfaccia e attendere il checkpoint: il solo `docker stop` non sostituisce la pausa applicativa. Per un backup minimo del DB, eseguire con una shell Bash sulla VM:

```bash
umask 077
mkdir -p backups
backup_date=$(date -u +%Y%m%dT%H%M%SZ)
dc exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "backups/database-$backup_date.dump"
test -s "backups/database-$backup_date.dump"
```

Il dump da solo non include i video. Per una copia coordinata DB/storage, dopo pausa e checkpoint fermare le scritture, eseguire il dump precedente e archiviare il volume:

```bash
dc stop caddy worker api
# Eseguire qui il dump PostgreSQL precedente, con db ancora acceso.
docker run --rm -v basketvision-prod_storage_data:/source:ro -v "$PWD/backups:/backup" alpine:3 sh -c 'tar -czf /backup/storage.tar.gz -C /source .'
dc start api worker caddy
```

Conservare copie separate e protette anche di `.env.production`, Caddyfile e dei volumi delle chiavi/certificati. Copiare i backup fuori dalla VM e provare un ripristino su un database separato. Le copie storage possono essere grandi: controllare lo spazio prima di crearle. Non usare `down -v` o `docker volume prune` sul server con dati da conservare.

### 12. Aggiornare, fermare e riavviare

Prima dell'update: pausa/checkpoint dei job, backup DB e storage, nota della revisione corrente. Poi:

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
dc ps
dc logs --tail=100 api worker caddy
```

Con 1 GB può essere necessario fare una finestra di manutenzione: `dc stop`, build sequenziali, poi `dc up -d --no-build`. Riprendere i job dall'interfaccia dopo la verifica; non cambiare manualmente il loro stato nel DB. Le migrazioni richiedono un backup: tornare a un'immagine precedente non annulla una migrazione.

```bash
dc stop                         # ferma, conserva container e volumi
dc start                        # riavvia i container esistenti
dc restart caddy                # riavvia solo il proxy
dc down                         # rimuove container/rete, conserva i volumi
dc up -d --no-build              # ricrea usando immagini già compilate
```

Non usare `restart` per applicare nuove variabili environment: usare `up -d`, che ricrea i servizi modificati. La configurazione locale continua a usare `docker compose up --build` e il proprio `.env`.

### Verifiche della configurazione production

Verificati localmente: Compose e Caddyfile validi; build API, frontend TypeScript e worker CPU; 20 test backend (inclusi proxy fidati e password DB con caratteri speciali) e 4 test tracker. Uno stack temporaneo separato, con TLS interno e porte loopback alternative, ha verificato routing Caddy, frontend read-only, `/api/health`, 401 anonimo, login, cookie Secure, refresh, logout e connessione worker tramite `PG*`. I modelli originali si caricano dal volume cache e completano inferenza full-frame/tiled su CPU. Il processo di inferenza minimo ha raggiunto circa 459 MiB RSS sul computer di test: non è una misura del picco dello stack o di un'intera analisi. La VM Oracle da 1 GB e l'emissione dei certificati pubblici restano da verificare dopo il deploy; nessun DNS o server remoto è stato modificato.
