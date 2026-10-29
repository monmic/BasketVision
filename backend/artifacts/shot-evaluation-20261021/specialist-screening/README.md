# Confronto detector e preparazione dei dati successivi — 26 ottobre 2026

## Esito

Nessun modello candidato supera la baseline nel campione vicino al ferro e nel
controllo su un secondo video. Nessuna sostituzione nel worker o ulteriore
modifica di soglie. Non si passa al confronto delle traiettorie con un modello
che già perde copertura nel rilevamento grezzo e peggiora il controllo separato.

| Modello | Palla in azione nei 36 frame mirati, revisione visiva | TP / FP / FN sul controllo di 22 frame, IoU ≥0,5 | Inferenza sui 36 frame (s) | Inferenza sui 22 frame (s) |
|---|---:|---:|---:|---:|
| yolo26n baseline | 14 | 4 / 8 / 8 | 3,96 | 2,50 |
| Modello basket university, classe Ball | 12 | 3 / 30 / 9 | 32,21 | 18,38 |
| Ultimo fine-tuning locale corretto | 14 | 4 / 11 / 8 | 3,67 | 2,40 |

Lo specialista guadagna tre osservazioni della palla, ne perde cinque e ne
condivide nove con la baseline. Entrambi mancano 19 osservazioni; il fine-tuning
mantiene esattamente gli stessi 14 abbinamenti visivi della baseline.
La proposta dello specialista sul frame 17824 è grossolana: l'abbinamento visivo
non certifica un box preciso o un IoU sufficiente.

## Protocollo e limiti

Frame esatti decodificati dal video originale, conservati in memoria e condivisi
fra baseline e specialista nella stessa esecuzione. Il fine-tuning viene
controllato separatamente sugli stessi indici e sorgenti. Nessuna inferenza su
JPEG diagnostici. Full-frame 960, confidence 0,02, due core/thread CPU effettivi,
senza tile, tracking, persone o database. Warm-up prima del timer per modello
e video; tempi di sola inferenza, esclusi decodifica, caricamento e tavole.
Singola misura locale: la piccola differenza temporale del fine-tuning non
dimostra un'ottimizzazione. Il costo dello specialista è circa 8× sul campione
mirato; non equivale al costo di un job completo.

Classi controllate esplicitamente: 32 `sports ball` per baseline/fine-tuning,
0 `Ball` per il modello university. Hash dello specialista confrontato con
`vision/fixtures/specialist-model-benchmark.json`; pesi già locali, nessun download.

I 36 frame sono un audit della palla in azione già osservato durante lo sviluppo:
non sono annotazioni esaustive di tutte le palle e non producono una misura di
precision/recall. Revisionate 18 tavole (sei per modello), con indici espliciti
dei candidati corrispondenti. Il campione vicino al ferro include anche frame
della sorgente usata nel vecchio training: nessuna pretesa di test indipendente.

Il controllo usa i 22 frame e le annotazioni utente esistenti di
`test-online-720p-15fps.mp4`, con il valutatore già presente
`scripts/evaluate_ball_clip.py`. TP/FP/FN assumono complete quelle annotazioni.
È un altro video, ma è già stato esaminato per precedenti confronti: non è
un holdout nuovo. La baseline qui è full-frame, quindi non va confusa con i
conteggi della pipeline full-frame + tile + tracker degli esperimenti precedenti.

## Passo concreto preparato

[Apri la revisione dei 19 casi difficili](hard-cases-review.html).

La pagina riusa `scripts/ball_review.html`, contiene PNG dei 19 frame originali
in cui baseline e specialista mancano la palla e funziona senza server o upload.
Nessun box è precompilato. Annotare tutte le palle visibili, comprese quelle a
bordo campo; escludere i frame ambigui e scaricare il JSON prima di chiudere.
Il nome dell'export è `home-vs-away-hard-near-rim.json`.
Questi sono esempi difficili per sviluppo, non un futuro test cieco. Non sono
stati assegnati automaticamente a train/val/test o usati per riaddestrare.

Esistono inoltre cinque pagine da quattro frame già preparate in
`storage/diagnostics/home-vs-away-ball-expansion/index.html`: 20 frame non ancora
annotati dello stesso video. Nessun riferimento nuovo importato o inventato.
Il file caricato `10aa4924-7d80-493b-b765-60743e01797e-70def432488846b68f50335ca6e4521f.mp4`
ha lo stesso SHA-256 del controllo 720p: non è una nuova sorgente indipendente.

## Coda e dipendenza esterna

- Screening sul campione vicino al ferro e sul secondo video: completato.
- Controllo dell'ultimo checkpoint locale: completato, nessun miglioramento.
- Preparazione del pacchetto dei casi difficili e verifica dei dati disponibili: completate.
- Replay delle traiettorie con un candidato migliore: non avviato, gate del detector non superato.
- Nuova validazione fuori dalle sorgenti già esplorate: in attesa del percorso
  di un altro video locale, idealmente 30–60 secondi con alcuni tiri e sequenze
  senza tiro. Richiesta all'utente inviata; nessuna approvazione generica richiesta.

L'aggiunta del nuovo video consentirà di preparare un riferimento distinto e
fissare lo split per sorgente/episodio prima di un nuovo ciclo di training o
selezione. Le annotazioni complete dei casi difficili restano da verificare
prima di qualsiasi export per training. Le attività indipendenti dello
screening e della preparazione sono terminate; questa verifica non completa
la milestone di tracking e non giustifica l'inferenza di eventi/statistiche.

## Riproduzione e verifiche

`compare_specialist_samples.py` esegue il confronto isolato e le tavole; con
`--corrected-checkpoint` aggiunge il checkpoint locale senza sovrascrivere i
risultati precedenti. Dentro il container worker: questa cartella diagnostica
su `/output`, video su `/videos`, modelli su `/models`, script su `/scripts`,
annotazioni controllo su `/control-annotations.json`; per il fine-tuning anche
il file dei pesi su `/corrected.pt`. Tutti gli input in sola lettura, rete
disattivata, `--cpus 2`, `/tmp` temporaneo e `YOLO_CONFIG_DIR=/tmp/ultralytics`.

`review_specialist_screening.py` conserva le corrispondenze visive e
`prepare_failure_review.py` costruisce la pagina con la UI esistente. Output
protetti dalla sovrascrittura. Nessuna dipendenza aggiunta.

Output principali: `*-near-rim.json`, `*-control.json`, `summary.json`,
`fine-tuned-summary.json`, `visual-review.json`, `fine-tuned-visual-review.json`,
`hard-cases-plan.json`, `provenance-and-readiness.json` e `final-provenance.json`.

Verificati 174 frame inferiti (58 per modello), identità degli indici, classe,
hash, due thread effettivi, metriche del controllo ricalcolate, corrispondenze
visive e 19 PNG nella pagina di annotazione. Due test focalizzati del benchmark
superati; sintassi degli script verificata. Nessuna migrazione, configurazione,
modifica del worker o dei dati applicativi.
