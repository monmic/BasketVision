# Prova del ritaglio centrato sul ferro — 26 ottobre 2026

Coda autorizzata:

1. Riutilizzare `scripts/diagnose_rim_roi.py` sui sei intervalli con geometrie riviste.
2. Riprodurre il tracker senza modificare modello o soglie.
3. Controllare gli stessi 36 frame e tutti i nuovi box accettati; verificare eventuali perdite.
4. Confrontare continuità, candidati tiro e costo CPU; documentare la decisione.

Inferenza aggiuntiva su ritaglio con raggio pari a quattro larghezze del ferro,
`imgsz=640`, confidence invariata 0,02, modello locale yolo26n. I candidati del
ritaglio sono uniti alla baseline full-frame/tiled e il tracker viene riprodotto
dall'inizio di ogni intervallo. La baseline è quella già riprodotta esattamente
nella prova precedente: tile ogni tre frame, nessuna nuova soglia.

Le posizioni del ferro derivano dalle sovrapposizioni già revisionate e restano
approssimate; interpolazione fra i campioni, senza estendere gli intervalli.
Non è un test di tracking automatico del ferro o un nuovo job applicativo.

Due core/thread CPU, rete disattivata, video/modelli/script sorgenti in sola lettura,
nessun accesso al database. Il tempo ROI è misurato come lavoro aggiuntivo su
candidati baseline salvati: la somma con il vecchio tempo baseline è una stima,
non una misura completa accoppiata della pipeline. Nessun modello/person tracker caricato.

## Risultato: variante non promossa

Tutti e quattro gli item della coda sono completati. Inferenza su 690 frame,
replay del tracker e confronto sui sei episodi eseguiti. Le 42 osservazioni
accettate coincidono esattamente con la baseline per frame, timestamp, centro,
track ID e confidenza: nessuna aggiunta o perdita. Continuità invariata e zero
candidati tiro in entrambi i profili.

| Episodio | Frame ROI | Costo ROI aggiuntivo (s) | Accettate baseline / ROI | Sequenza continua baseline / ROI | Candidati tiro baseline / ROI |
|---|---:|---:|---:|---:|---:|
| Originale | 90 | 16,35 | 24 / 24 | 24 / 24 | 0 / 0 |
| 1 | 120 | 24,40 | 9 / 9 | 5 / 5 | 0 / 0 |
| 2 | 120 | 25,69 | 7 / 7 | 5 / 5 | 0 / 0 |
| 3 | 120 | 23,95 | 2 / 2 | 1 / 1 | 0 / 0 |
| 4 | 120 | 24,80 | 0 / 0 | 0 / 0 | 0 / 0 |
| 5 | 120 | 20,76 | 0 / 0 | 0 / 0 | 0 / 0 |
| **Totale** | **690** | **135,96** | **42 / 42** | — | **0 / 0** |

La baseline precedente richiedeva 162,56 s; aggiungere i 135,96 s ROI porta a
una **stima** di 298,52 s, circa +84%, non a un tempo end-to-end misurato.
Il costo aggiuntivo comprende seek/decode e inferenza del ritaglio; esclude
caricamento/riscaldamento del modello, serializzazione JSON e replay separato
del tracker. Host locale CPU-only, singola esecuzione, nessuna previsione sulla VM.

## Revisione della qualità

Controllate tutte le 39 proposte ROI su due tavole, senza selezionare solo i
risultati favorevoli:

- 13 box mostrano la palla in azione. Nove risultano eliminati/sostituiti dalla
  NMS durante l'unione con la baseline; quattro sopravvivono ma non possono
  avviare una traccia perché deboli.
- 26 box sono falsi rilevamenti su sfondo fisso (16 nell'originale, 10
  nell'episodio 4). Nessuno genera un'osservazione accettata aggiuntiva.
- Dopo l'unione/NMS i candidati complessivi passano da 461 a 467: il numero
  di proposte ROI non è il numero di detection aggiuntive della pipeline.

Le etichette e lo stato dopo l'unione sono espliciti in
`roi-candidates-reviewed.json`. I box delle tavole grezze sono tutti verdi per
mostrarne la posizione: il colore non significa che siano accettati dal tracker.
Questa revisione certifica il contenuto dei 39 box osservati, non l'assenza di
tutte le palle nei frame né la precision/recall globale del modello.

Le sei tavole degli stessi 36 frame dell'audit sono state ricontrollate:

| Stato della palla in azione | Baseline | ROI |
|---|---:|---:|
| Detection accettata | 4 | 4 |
| Box corrispondente scartato | 10 | 10 |
| Nessun box corrispondente nei candidati salvati | 22 | 22 |

Il raggio di quattro larghezze non garantisce che tutta la traiettoria sia
inclusa, soprattutto nella parte alta della parabola. Non si attribuisce
quindi ogni detection mancante al solo modello. L'esito riguarda esattamente
questo ritaglio, queste geometrie approssimate e questo modello; non esclude
che altre strategie ROI possano funzionare. Nessuna ricerca di ulteriori soglie
o scale è inclusa nella presente prova.

**Decisione:** il ritaglio provato aumenta il costo senza migliorare la copertura
accettata o i candidati tiro; non viene integrato nel worker. La coda della prova
è esaurita. Non serve un intervento dell'utente per questa verifica. Non è
dimostrato il requisito di tracking necessario per avanzare ai tentativi di tiro.

## Riproduzione e validazione

`run_rim_roi_trial.py` adatta i report già disponibili ai tre strumenti esistenti:
`scripts/diagnose_rim_roi.py`, `scripts/replay_ball_tracker.py` e
`scripts/diagnose_reviewed_shots.py`. Non contiene un secondo algoritmo di ROI
o un tracker parallelo. Le geometrie sono salvate in `calibration.json`; gli
input copiati aggiungono dimensioni e identità del video e cambiano solo il
percorso dei pesi verso `/models/yolo26n.pt`, non il file del modello.

Modalità, dalla cartella backend:

```powershell
py -3.12 artifacts/shot-evaluation-20261021/run_rim_roi_trial.py prepare
py -3.12 artifacts/shot-evaluation-20261021/run_rim_roi_trial.py compare
```

`prepare` crea una directory nuova; `compare` richiede gli output inferiti.
Gli output esistenti sono protetti dalla sovrascrittura. Per l'inferenza usare
la modalità `infer --scripts /scripts` dentro l'immagine worker, montando gli
script del repository su `/scripts` e il sorgente vision su `/vision` in sola
lettura; questa cartella diagnostica su `/output`, video su `/videos`, pesi su
`/models`, con i vincoli CPU/rete sopra indicati. Inizializzare
`BALL_MODEL=/models/yolo26n.pt`, `VISION_CPU_THREADS=2` e
`YOLO_CONFIG_DIR=/tmp/ultralytics` con `/tmp` temporaneo.

Riutilizzati anche `build_gap_audit.py --profile rim-roi` per le tavole dei 36
frame e `build_tile_delta_boards.py --raw-roi` per tutte le proposte. La modalità
`--roi` di quest'ultimo verifica le nuove accettazioni: lista vuota.

Output principali: `comparison.json`, `timings.json`, `replayed-XX.json`,
`reviewed-frames.json`, `roi-candidates-reviewed.json`, `new-accepted.json`.
Hash di modello, script e baseline in `provenance.json`.

Validazioni: 35 test esistenti superati (18 tracker, 2 benchmark, 3 calibrazione
temporale, 12 detector tiro); controllati frame, risoluzione, impostazioni,
coordinate, 42 accettazioni identiche, riproducibilità del replay e corrispondenza
dei 36 frame revisionati. Nessun evento/report operativo/database modificato.
Nessuna migrazione, nuova dipendenza o configurazione applicativa.
