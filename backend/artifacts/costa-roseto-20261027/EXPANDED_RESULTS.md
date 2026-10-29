# Detector ampliato: dati di gioco e due sorgenti

Seguito del [protocollo fissato prima del training](EXPANDED_PROTOCOL.md).
Il worker operativo e i risultati nel database non vengono modificati.

## Dataset

| Split | Immagini | Box palla attiva | Ritagli negativi di gioco |
| --- | ---: | ---: | ---: |
| Training | 75 | 49 | 23 |
| Validazione | 21 | 21 | 0 |
| Controlli già noti esportati | 21 | 19 | 0 |

Training: 11 frame Costa del pilot, 41 frame Home vs Away degli episodi
shot-001/002/003, 12 ritagli Costa e 11 HVA. Restano anche i tre negativi
dell'introduzione Costa. I ritagli sono contesti di proposte errate del modello
del pilot: non si dichiara assente la palla nell'intero frame di provenienza.

Estratti 24 ritagli soltanto dai frame di training, in ordine di confidenza del
modello precedente, limitando a due ritagli per frame e quattro per episodio
HVA. Zona di ogni palla annotata esclusa con margine 16 pixel. Revisionati tutti
i ritagli nativi, indipendentemente dal punteggio; uno scartato per oggetto
ambiguo tra le mani di una persona sullo sfondo. Nessuna annotazione negativa
derivata soltanto dalla mancata rilevazione del detector.

Validazione: i 5 frame Costa precedenti più 16 HVA dell'episodio shot-004.
Controlli esclusi da training e mining: 6 frame Costa 120–170 s, 15 HVA di
shot-005 e 22 del video 720p. Sono dati già esaminati durante lo sviluppo.
Nessun hash immagine duplicato nell'export; nessun episodio HVA condiviso fra
training, validazione e controllo.

## Campioni successivi

Scelti 180,190,200,210,220,230 secondi di Costa prima dell'ispezione. Annotati
sui frame nativi senza proposte del detector; cinque palle visibili, un caso
ambiguo escluso, non negativo. Box ricontrollati in contesti ingranditi.
SHA256 annotazioni congelate prima della selezione del checkpoint:
`c0d63db13003fccaf2ff74785886a44cd456ac1a3dc39e5007d1adecffdb3a2a`.
Lo stesso montaggio può contenere replay e sequenze correlate: questo controllo
successivo non è un test su una sorgente completamente indipendente.

## Riproduzione

Riutilizzati exporter/conversione YOLO, training e benchmark del pilot. Docker
CPU limitata a 2 core, rete disabilitata; video, modello e vecchio dataset montati
in sola lettura. Nessun download o nuova dipendenza.

1. `prepare_detector_negatives.py`: dossier in `/experiment`, vecchio dataset in
   `/old-dataset`, annotazioni HVA revisionate in `/old-annotations.json`.
2. Ispezionare le due tavole e i 24 PNG; `record_detector_negative_review.py`
   registra le 23 approvazioni e l'esclusione. `export_expanded_detector.py`
   con gli stessi montaggi e script repository in `/scripts`.
3. `prepare_detector_frames.py --fresh-expanded`: video Costa in `/video.mp4`;
   controlla l'hash della sorgente. `record_expanded_fresh_annotations.py` e
   `review_detector_annotations.py --fresh-expanded` preparano la revisione.
   Dopo la revisione, `record_expanded_fresh_annotations.py --freeze` salva
   la versione finale in `detector-expanded/fresh/reviewed.json`.
4. `train_detector_pilot.py --expanded`: YOLO26n in `/model.pt`, dossier in
   `/experiment`. Riparte dal modello originale, non da quello fallito.
   Stesse 15 epoche, input 640, batch 2, freeze 10, AdamW .001, seed 20261027,
   nessun warm-up e nessuna augmentazione della prova precedente.
5. `benchmark_detector_pilot.py --expanded`: montaggi come nel benchmark
   precedente, più tutti gli artefatti locali del dossier. Confronta baseline,
   pilot stabile ed espanso sugli stessi input, confidence .02/.12, IoU .5.
   Il checkpoint viene verificato tramite hash prima dell'inferenza.
6. `audit_expanded_detector.py`: hash dataset, immagini, label esatte, parent
   di ogni ritaglio, esclusione palle, separazione delle sorgenti/frame/split,
   annotazioni successive e checkpoint. `test_detector_negatives.py` protegge
   l'esclusione delle palle e dei margini durante il mining.
7. `decide_expanded_detector.py`: applica il controllo fissato nel protocollo,
   su entrambe le confidence, senza nascondere regressioni di una sorgente nella
   media. `eligibleForContinuousReplay` non è un'autorizzazione al rilascio.

Gli script rifiutano di sovrascrivere gli output congelati. Tutti i dataset,
immagini, log, modelli e report generati sono esclusi da Git nella directory
`detector-expanded/`. Nessuna modifica di configurazione applicativa o migrazione.

## Training e provenienza

Training completato in **866,065 secondi** (14 min 26 s), caricamento iniziale
escluso, training/validazione/salvataggio inclusi, CPU Docker limitata a 2 core.
Non è una stima del tempo di analisi video o delle prestazioni della VM.
Checkpoint selezionato dalla validazione, congelato prima di valutare i controlli.

- Dataset SHA256:
  `b65c3544f2b5296211454f740ce0fdc766348a697950ac6ca1adb427a7381f98`.
- Pesi selezionati SHA256:
  `41e727cbefe5deb1424d30e3fd37b19806cf58707f09d34413ceda8c9d20702b`.
- Inizializzazione: stessa YOLO26n del pilot,
  `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.

Il log originale, il CSV delle 15 epoche, la configurazione effettiva e i
checkpoint restano nella directory locale ignorata da Git. Non si confronta
l'AP di validazione con quello del vecchio pilot: il set è cambiato da 5 a 21
frame. Il confronto corretto usa le stesse immagini per tutti e tre i modelli.

## Risultati sullo stesso campione

Metriche **TP / FP / FN**, matching uno a uno IoU ≥ .5, inferenza full-frame
960. I FP includono anche box di palle vere localizzati male. Nessun tracking,
ritaglio guidato dal canestro o filtro semantico in questo confronto: si isola
l'effetto del detector. Il pilot è la variante precedente senza warm-up.

Confidence .02, fissata prima del training:

| Controllo | Baseline | Pilot precedente | Espanso |
| --- | --- | --- | --- |
| Costa 120–170 s, 6 frame | 1 / 11 / 3 | 2 / 113 / 2 | 1 / 27 / 3 |
| HVA shot-005, 15 frame | 2 / 3 / 13 | 3 / 62 / 12 | 6 / 91 / 9 |
| 720p, 22 frame | 4 / 8 / 8 | 6 / 42 / 6 | 1 / 25 / 11 |
| Costa 180–230 s, 5 frame valutabili su 6 | 0 / 16 / 5 | 1 / 124 / 4 | 1 / 34 / 4 |
| Costa validazione, 5 frame | 1 / 15 / 4 | 5 / 143 / 0 | 3 / 48 / 2 |
| HVA validazione, 16 frame | 4 / 0 / 12 | 0 / 29 / 16 | 7 / 127 / 9 |

Sui quattro controlli esclusi dal training, i FP totali passano da 341 del pilot
a 177 dell'espanso, ma la baseline ne fa 38. La crescita dei TP aggregati da
7 a 9 rispetto alla baseline nasconde la perdita di quattro oggetti già
riconosciuti: Costa frame 3596, 720p frame 43/45/180. La migliore copertura
HVA non compensa la regressione sulla sorgente 720p.

Confidence .12, già presente nel worker come soglia per nuove tracce:

| Controllo | Baseline | Pilot precedente | Espanso |
| --- | --- | --- | --- |
| Costa 120–170 s | 0 / 4 / 4 | 2 / 16 / 2 | 0 / 3 / 4 |
| HVA shot-005 | 1 / 0 / 14 | 1 / 0 / 14 | 3 / 5 / 12 |
| 720p | 3 / 2 / 9 | 3 / 1 / 9 | 1 / 1 / 11 |
| Costa successivo | 0 / 4 / 5 | 1 / 12 / 4 | 0 / 1 / 5 |

Anche qui i totali nascondono regressioni: baseline ed espanso hanno entrambi
4 TP e 10 FP sui quattro controlli, ma l'espanso perde gli oggetti 720p dei
frame 45 e 180. Non è stata scelta una nuova soglia per migliorare il resoconto.

Nei cinque frame successivi valutabili, il massimo IoU di una proposta espansa
per ogni palla è 0 / .327 / 0 / .561 / 0: quattro palle non superano .5 e tre
non hanno proposte sovrapposte. Ricontrollati gli overlay nativi dei frame 5994
e 6893: restano rilevazioni di dettagli sullo sfondo mentre la palla visibile
non viene individuata. Il limite comprende ancora recall e localizzazione,
non soltanto il rigetto delle scarpe.

## Esito e verifiche

Il controllo automatico fissato dal protocollo respinge il modello su entrambe
le confidence: oggetti precedentemente rilevati persi, regressioni di sorgente
e nessuna riduzione dei FP rispetto alla baseline. `productionRelease=false` e
`eligibleForContinuousReplay=false` in `evaluation/decision.json`. Il replay
continuo era condizionato al passaggio di questi controlli e non viene avviato.

Completata la coda: negativi revisionati → export/audit → training → confronto
dei controlli → campioni successivi → decisione documentata. **Nessuna variante
integrata nell'app**, nessun job/evento/statistica scritto nel database.
Dataset più ampio disponibile per un ciclo successivo; non dimostra ancora
riconoscimento affidabile dei tiri, degli esiti o delle squadre. Aumentare i
negativi da soli non ha risolto la perdita di palle e la regressione sul 720p.

22 test mirati superati: 4 mining negativi, 4 annotazioni, 3 valutazione,
5 export, 2 benchmark esistente, 4 decisione. Audit dei 117 file immagine,
label, parent dei ritagli, split, 6 campioni successivi e checkpoint; sintassi
Python e whitespace verificati. Nessuna nuova dipendenza, configurazione
operativa o migrazione. Non sono stati eseguiti ulteriori training per adattare
il modello ai risultati del nuovo controllo.
