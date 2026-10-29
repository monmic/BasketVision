# Pilot detector: dataset completo per frame e prima prova di training

Seguito del [protocollo congelato](DETECTOR_PROTOCOL.md). Ciclo completato:
estrazione, annotazione, revisione ingrandita, export, training, controllo
inizializzazione, diagnosi del warm-up, singola ripetizione e composizione con
il verificatore precedente. Nessuna variante supera il controllo di integrazione.

## Annotazioni e integrità

27 frame scelti prima di esaminare il tratto nuovo. Annotazioni a immagine intera
della palla attiva in campo, indipendenti dalle proposte del modello. Palle
immagazzinate nelle rastrelliere escluse. Cinque frame con palla occlusa o non
distinguibile sono esclusi esplicitamente; non diventano esempi negativi.

| Split | Frame esportati | Box palla | Frame negativi verificati |
| --- | ---: | ---: | ---: |
| Training, 0–58 s | 11 | 8 | 3 |
| Validazione, 60–110 s | 5 | 5 | 0 |
| Test iniziale, 120–170 s | 6 | 4 | 2 |

Le immagini positive e i box sono stati ricontrollati in 17 ritagli ingranditi;
le immagini negative sono titoli/introduzione. Il dataset è minuscolo e non ha
ancora negativi verificati di gioco: **non è sufficiente per un detector di
produzione**. Le esclusioni possono favorire i risultati sui casi più facili.
Le immagini appartengono a un unico montaggio: split temporale, non prova su
una seconda sorgente indipendente. Nessun hash immagine duplicato fra gli split;
nessuna garanzia di assenza di replay/azioni correlate dal solo hash.

Artefatti locali esclusi da Git in `detector-pilot/`: `frames.json`,
`annotations-draft.json` (annotazioni revisionate congelate), `dataset/manifest.json`,
immagini PNG native, label YOLO, overlay e tavole `annotation-review-00..02.png`.
SHA256 manifest dataset:
`2b30d43d527c475cbbc0e31f1f8caa5b6f1f27386a3bdd08faf911a213e62901`.

## Training e diagnosi

Due run CPU limitata a 2 core, rete disabilitata, seed 20261027. YOLO26n iniziale,
classe singola `sports ball`, backbone primi 10 livelli congelati, 15 epoche,
input 640, batch 2, AdamW lr0=.001, nessuna augmentazione cromatica/geometrica.
I nomi mantengono la corrispondenza della classe preaddestrata, tramite
`cls_remap`; parametri documentati nella [guida Ultralytics](https://docs.ultralytics.com/modes/train/).
Versione eseguita nel container: Ultralytics 8.4.183.

- Primo run: 145,469 s. Il default warm-up dei bias produce lr=0,0725 alla prima
  epoca, molto maggiore del lr0 configurato: rilevazioni eccessive sui controlli.
- Trasferimento senza training controllato su tre immagini: coordinate,
  confidenze e numero proposte identici alla classe 32 della baseline.
- Controllati tutti i 99 buffer BatchNorm dei livelli congelati: nessuno è
  cambiato. Scartata l'ipotesi che il problema fosse un drift di quei buffer;
  il peso diagnostico ripristinato non introduce variazioni né un nuovo modello.
- Singola ripetizione: warmup_epochs=0 e warmup_bias_lr=0, stessi dati e altre
  opzioni. Primo lr dei bias effettivo .001. Durata 147,573 s. Meno falsi, ma
  regressioni ancora presenti. Non è stato eseguito uno sweep di parametri.
- Checkpoint scelti sulla validazione, hash registrato prima delle valutazioni.
  Il test iniziale è già noto quando si decide la ripetizione: per questa e
  per la composizione è soltanto un controllo di regressione, non un test cieco.

SHA256 inizializzazione:
`9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.
Checkpoint primo run:
`71fdc6c874aa45b7d7fa51e9987bd09eeb2b03e200f7c86af24aace247a7a02f`.
Checkpoint senza warm-up:
`dba14f80499e789f1f9fac16858e418e016de1d8ef7a060a00f5d9591f3e1ccb`.

## Confronto detector

Stessi input nativi, inferenza full-frame a 960, CPU, confidence .02,
abbinamento uno a uno IoU ≥ .5 tramite il valutatore esistente.
Numeri **TP / FP / FN**: FP include anche box su palle vere localizzati male,
non soltanto oggetti di sfondo. Queste metriche geometriche non sono equivalenti
alle revisioni di identità delle sole proposte riportate nel ciclo precedente.

| Controllo | Baseline | Primo training | Senza warm-up |
| --- | --- | --- | --- |
| Costa validazione, 5 frame | 1 / 15 / 4 | 4 / 666 / 1 | 5 / 143 / 0 |
| Costa 120–170 s, 6 frame | 1 / 11 / 3 | 1 / 589 / 3 | 2 / 113 / 2 |
| Home vs Away, 15 frame precedenti | 2 / 3 / 13 | 2 / 677 / 13 | 3 / 62 / 12 |
| Controllo 720p, 22 frame precedenti | 4 / 8 / 8 | 6 / 365 / 6 | 6 / 42 / 6 |

Il nuovo detector recupera alcune palle, ma aumenta troppo i falsi. Sui 59 frame
totali, compreso il training, il secondo confronto impiega 11,600 s di inferenza
baseline e 11,442 s per il nuovo modello, esclusi warm-up/caricamento/decodifica.
Campione troppo piccolo per sostenere un miglioramento di prestazioni; nessuna
stima di runtime del job completo o della VM di produzione.

## Composizione con il verificatore semantico

Ultimo controllo senza altri training: nuovo detector senza warm-up più il
verificatore già congelato del primo minuto, soglia semantica fissa .5.
Nessun ritocco alle soglie di inferenza o del tracker. Tutti questi riferimenti
sono ormai controlli noti di sviluppo.

Alla confidence .02, la composizione su Costa 120–170 s fa **0 / 22 / 4**:
respinge tutte le palle corrette recuperate. Anche su Home vs Away resta a
3 / 52 / 12 e sul controllo 720p a 5 / 20 / 7. Non supera il controllo.

Verificata anche confidence .12, soglia già usata per nuove tracce nel worker;
non selezionata sui risultati:

| Controllo | Baseline | Senza warm-up | Con filtro semantico |
| --- | --- | --- | --- |
| Costa validazione | 1 / 4 / 4 | 2 / 16 / 3 | 0 / 3 / 5 |
| Costa 120–170 s | 0 / 4 / 4 | 2 / 16 / 2 | 0 / 0 / 4 |
| Home vs Away | 1 / 0 / 14 | 1 / 0 / 14 | 1 / 0 / 14 |
| Controllo 720p | 3 / 2 / 9 | 3 / 1 / 9 | 2 / 0 / 10 |

Il pareggio dei TP sul 720p senza warm-up nasconde la perdita di due oggetti
prima riconosciuti (frame 45 e 180), compensata da altri recuperi: controllate
anche le identità per frame, non solo i totali. Nessuna variante è promossa.
Non sono stati avviati replay continui di un modello che fallisce già questi
controlli, né consumati altri frame dopo il secondo 170 per aggiustarlo.

## Riproduzione e validazione

Usare nuovi output per ripetere il ciclo: gli script rifiutano di sovrascrivere
dataset, training e benchmark. Comandi da backend; per gli script ML usare il
container worker esistente, `--network none --cpus 2`, `YOLO_CONFIG_DIR=/tmp/ultralytics`.

1. `prepare_detector_frames.py` nel container, dossier in `/experiment`,
   video Costa in `/video.mp4` in sola lettura.
2. `record_detector_annotations.py`, poi `review_detector_annotations.py` nel
   container per ispezionare frame e box, infine `export_detector_pilot.py` dal
   filesystem repository. Il modulo riusa il convertitore YOLO e il validatore
   delle annotazioni esistenti in `scripts/`.
3. `train_detector_pilot.py`, poi `benchmark_detector_pilot.py`. Per entrambi
   dossier in `/experiment`, YOLO26n in `/model.pt`. Per il benchmark montare anche
   script repository in `/scripts`, dataset precedente in `/old-dataset`,
   annotazioni HVA revisionate in `/old-annotations.json`, annotazioni 720p in
   `/online-annotations.json`, video 720p in `/online.mp4`, tutti in sola lettura.
4. `check_detector_initialization.py`, `check_frozen_backbone.py`: diagnosi senza
   fitting. `train_detector_pilot.py --stable-warmup` e
   `benchmark_detector_pilot.py --stable-warmup`: singola ripetizione descritta.
5. `combine_detector_verifier.py` con gli stessi montaggi del benchmark,
   senza bisogno del video 720p (usa i frame diagnostici già estratti).
6. `audit_detector_dataset.py`: verifica selezione, esclusioni, label esatte,
   hash immagini/annotazioni/manifest e checkpoint di entrambi i run.

14 test mirati passati: 4 annotazioni, 3 valutazione del pilot, 5 export YOLO,
2 benchmark esistente. Sintassi Python verificata; dataset e pesi generati
restano esclusi da Git. Nessuna dipendenza, migrazione, modifica alla
configurazione applicativa, al worker operativo o al database.

## Esito e limite successivo

Completata la coda del pilot, compresa la correzione motivata del warm-up e il
controllo della composizione. L'integrazione è respinta dai risultati, non manca
un'approvazione dell'utente. Il dataset completo per frame ora esiste, ma la sua
copertura resta troppo limitata: pochi esempi positivi, nessun negativo di gioco
verificato e una sola sorgente di training. Un successivo ciclo dovrà ampliare
questa copertura e conservare un controllo distinto; non basta aumentare le
epoche sugli stessi 11 frame. L'utente non deve classificare i tiri nell'app.
