# Alpha: collaudo del percorso automatico

Stato del 29 ottobre 2026: pronto per collaudo **locale** su
http://localhost:5173. Web e worker aggiornati; API e database locali non
ricreati. Non è un rilascio su basketvision.it. Nessuna migrazione, dipendenza
applicativa, piano o configurazione di produzione cambiati.

Questa alpha verifica caricamento, gestione dell'analisi e consultazione delle
rilevazioni sperimentali. Il riconoscimento affidabile di tiri, esiti e squadre
rimane aperto: i risultati non sono statistiche complete della partita.
La revisione manuale è facoltativa, non necessaria per completare il percorso.

## Istruzioni brevi per il tester

1. Accedi con l'account fornito e crea una partita indicando i nomi delle squadre.
2. Seleziona un file video locale e premi **Carica video**. Attendi la conferma
   prima di chiudere o ricaricare la pagina: l'upload deve terminare.
3. Scegli inizialmente un intervallo breve, circa 30 secondi, con **DA/A**.
   Lascia disattivati i candidati di tiro sperimentali; non serve indicare il ferro.
4. Premi **Avvia analisi CV**. Dopo l'avvio puoi ricaricare o lasciare la pagina:
   il job continua in background. Verifica che partita, sessione e intervallo
   vengano ripristinati, e prova pausa/ripresa.
5. A completamento, consulta **Risultato dell’analisi** e apri la diagnostica
   se vuoi esaminare le rilevazioni. I timestamp delle rilevazioni/candidati
   portano al punto corrispondente del video.
6. Se il risultato non si carica, usa **Riprova risultato**: non avvia una nuova
   elaborazione. Un risultato CV privo di eventi confermati non produce una
   tabella di punti/percentuali uguale a zero.

Feedback utile: passaggio in cui ti sei fermato, comportamento atteso e
osservato, browser/dispositivo e ID della sessione presente nell'URL. Per un
problema di rilevazione, indica il secondo del video. Non è richiesto annotare
o classificare tutti i tiri.

## Correzioni consegnate

- Ripristino dei campi DA/A dalla sessione selezionata dopo refresh/cambio job.
- Un job aperto dall'elenco in background seleziona esattamente quella sessione.
- Una risposta di polling tardiva non sostituisce la sessione appena selezionata.
- Errori temporanei del polling visibili, recupero automatico senza job nuovo.
- Stato di caricamento/errore del risultato CV e pulsante di recupero dedicato.
- Riepilogo del risultato visibile senza aprire la diagnostica tecnica.
- Punti/statistiche mostrati soltanto in presenza di eventi confermati oppure
  in una sessione manuale esplicita; i candidati restano nella timeline.
- Upload interrotto recuperabile con file selezionato conservato; messaggio
  distinto se il caricamento è riuscito ma il successivo aggiornamento fallisce.
- Cambio partita/file bloccato durante l'upload; invio analisi disabilitato
  durante la richiesta. Messaggio esplicito sul mantenere aperta la pagina
  durante il caricamento e sulla continuità dell'analisi dopo l'avvio.
- Ripresa worker dal fotogramma successivo a quello già contato: nuovo campo
  checkpoint `nextFrameIndex`, con lettura compatibile dei checkpoint precedenti
  basati su `resumeTimestamp`. Seek per indice con FPS valido, senza cambiamenti
  di soglie, modelli o logica di associazione.

## Verifiche eseguite

- Build TypeScript/Vite, prerender e shell privata noindex: passati.
- `dotnet build BasketVision.sln --no-restore`: passato, zero errori/avvisi.
- 26 test backend mirati: autorizzazioni/ownership/quote, shooting e CSV.
- 5 regressioni checkpoint: analisi nuova, indice esplicito, formato precedente,
  FPS frazionari, più cicli di pausa/ripresa senza ricontare frame.
- 18 test tracker in scripts e 4 in vision: passati.
- `tests/pilot_journey_smoke.py`: upload interrotto e recupero, intervallo,
  refresh, pausa/ripresa, polling interrotto, risultato non disponibile e retry,
  assenza di statistiche certificate dai candidati, timestamp video, job esatto,
  risposta tardiva e layout mobile senza overflow. Fixture isolate, nessun
  caricamento o addebito nel DB dell'utente.
- `tests/assisted_review_smoke.py`: revisione facoltativa, salvataggio,
  correzione/scarto, errore report senza duplicazione, CSV e mobile: passato.
- `tests/pilot_access_smoke.py`: login reale Admin/User attraverso Nginx,
  sessione dopo reload, video autenticato, UI ownership, noindex e logout:
  passato. Nessuna partita/analisi reale creata, modificata o eliminata.
- `tests/pilot_stack_smoke.py`: API corrente, PostgreSQL tmpfs e storage
  separati, video sintetico di 8 s, analisi assoluta [1,7), worker CV reale.
  Pausa riconosciuta dal worker e checkpoint salvato prima della ripresa;
  esattamente 90 frame palla e 30 persone, quota di una sola analisi, 0,1 minuti,
  eliminazione dei risultati conservando il video: passato. È una verifica del
  ciclo di vita, non della qualità del riconoscimento su una partita.

La prova reale ha prima riprodotto 91 frame palla al posto di 90, individuando
il ricontaggio alla ripresa. Il nuovo controllo fallisce con il comportamento
precedente e passa dopo la correzione. I container e le reti temporanei sono
rimossi dal test; i file diagnostici generati sono ignorati da Git.

## Riproduzione

Build frontend con `npm run build`, backend con `dotnet build BasketVision.sln`.
Gli smoke browser richiedono il Playwright già presente nell'ambiente di
sviluppo e un Chromium/Edge (`BASKETVISION_BROWSER` opzionale). Passare l'URL
del frontend compilato come primo argomento; le fixture intercettano solo
le richieste della propria pagina.

Il test stack usa le porte loopback 18080/5544, Docker e le immagini locali
`basketvision-api`, `basketvision-worker`, `postgres:16-alpine`, più i pesi
baseline in `storage/diagnostics/models/yolo26n.pt`. Usa gli assembly backend
appena compilati. `--skip-backend-tests` è utile per ripetere il solo ciclo del
worker quando i test backend sono già passati; il comando normale li include.
La rete temporanea non è `--internal` perché Docker Desktop in questo ambiente
non pubblica le porte loopback in quella modalità. I servizi non accedono al
database o allo storage dell'app.

L'aggiornamento locale del worker riusa il runtime Docker già validato, con
solo i sorgenti applicativi copiati sopra; nessuna reinstallazione di PyTorch
o Ultralytics. Pesi baseline conservati e verificati per hash. I sorgenti nel
normale Dockerfile vision includono la correzione per i successivi rilasci.

## Coda e limiti

- [x] Riprodurre e correggere ostacoli del percorso automatico.
- [x] Distinguere risultato sperimentale, candidati ed eventi confermati.
- [x] Verificare browser desktop/mobile, regressioni e ciclo del worker reale.
- [x] Aggiornare web/worker locali e preparare istruzioni del tester.

Coda del collaudo locale completata. Prima di distribuire a 3–5 tester esterni
servono un ambiente condiviso raggiungibile e account utente dedicati; non
sono stati creati account o inviti e non è stato aggiornato l'ambiente di
produzione. Non c'è registrazione pubblica. Questa preparazione locale non
certifica la qualità degli eventi automatici, ancora insufficiente.
