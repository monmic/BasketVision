# Riconoscimento automatico: detector e contesto canestro

## Obiettivo e decisione

L'utente ha chiarito che BasketVision deve riconoscere gli eventi dal video;
l'annotazione manuale è soltanto uno strumento di verifica. Questa prova riparte
dai sei episodi già esaminati, senza ripetere gli screening locali precedenti.

**Risultato utile, variante non promossa:** il detector specializzato sul ritaglio
automatico recupera la palla, ma introduce falsi tracking di sfondo/teste e non
risolve il riconoscimento dei tiri. Non sono stati cambiati worker operativo,
soglie, eventi, report applicativi o configurazione CV.

## Fonti e riproducibilità

Pesi scaricati dalle fonti degli autori, soltanto per prove locali:

| Modello | Revisione | SHA-256 dei pesi |
|---|---|---|
| [E-BARD YOLOv8n](https://huggingface.co/GabrieleGiudici/E-BARD-detection-models) | `3f4789c4431aa73269f60107a4ba0a5f86b7af8b` | `dfe3534d51bb21024d1a400c37f0c1fbf0c8b96ea9a56a5f3cb5454813bfd641` |
| [Joseph Attalla, ball/hoop](https://github.com/josephattalla/Basketball-Shot-Detection) | `e320817d0f87eceb4093c871de6d29d1adca0006` | `40f3e596652a427ba290b3f72384e49aed12caf1a8ae41beaef4a8fffcf09fa3` |

File E-BARD `BODD_yolov8n_0001.pt`, classi 0 basketball / 1 hoop;
file Attalla `bball_model.pt`, classi 0 ball / 1 hoop. Le classi sono verificate
prima dell'inferenza. Fonti dichiarano rispettivamente CC-BY-4.0 e MIT nel
repository; nessun peso incluso nella distribuzione o nel repository BasketVision.
La scheda E-BARD segnala limiti sugli oggetti piccoli: i risultati pubblicati
dall'autore non sono metriche di BasketVision.

Il secondo checkpoint richiede `dill`: usata la wheel pura 0.4.0 da PyPI,
SHA-256 `44f54bf6412c2c8464c14e8243eb163690a9800dbe2c367330883b19c7561049`,
tramite PYTHONPATH del solo container diagnostico. Nessuna installazione o
dipendenza nuova nel worker applicativo.

Container isolati senza rete né database, video e script di riferimento in sola
lettura, due core e due thread PyTorch, CPU. Inferenza sui frame originali, non
sulle tavole JPEG; niente upload dei video. Nessun training in questa prova.

## Screening sugli stessi frame

Riutilizzato `../shot-evaluation-20261021/compare_specialist_samples.py`, esteso
con modello/classi/output espliciti e raccolta separata dei box canestro.
Full-frame 960, confidence 0.02, warm-up escluso dai tempi; nessun tracking.
Il controllo usa i 22 frame annotati di `test-online-720p-15fps.mp4`, 12 box
palla e dieci frame annotati senza palla; IoU almeno 0.5 e abbinamento uno a uno.

| Profilo | Palla in azione nei 36 frame mirati | TP / FP / FN nel controllo | Inferenza 36 / 22 frame, secondi |
|---|---:|---:|---:|
| Baseline full-frame già salvata | 14 | 4 / 8 / 8 | 3.96 / 2.50 |
| E-BARD full-frame | 0 | 4 / 24 / 8 | 4.67 / 3.08 |
| Attalla full-frame | 14 | 5 / 21 / 7 | 4.94 / 2.87 |
| Attalla, solo ritaglio automatico | 27 | 2 / 3 / 10 | 3.44 / 0.85 aggiuntivi |

Il ritaglio è proposto dal box hoop a maggiore confidenza, se almeno 0.25;
raggio quattro larghezze del box, limitato ai bordi, inferenza ball a 640.
Nessuna geometria manuale entra nella scelta del ritaglio. Il costo della
ricerca hoop full-frame resta aggiuntivo e non è nascosto nel tempo ROI.
I 36 campioni sono osservazioni della palla già esaminati durante lo sviluppo:
questi numeri non sono precision/recall né un test cieco. Nel controllo il
ritaglio isolato perde palle fuori ROI o in assenza di un hoop valido: non è
un sostituto della ricerca full-frame.

Controllati tutti i 36 top box hoop di Attalla su sei tavole a frame intero:
nei primi cinque episodi individuano il canestro, ma nei sei frame dell'ultimo
episodio individuano un cartello sul muro. Un ulteriore box corretto ha confidenza
inferiore a 0.25 e il ritaglio si astiene. Box hoop/net non equivalgono a una
linea fisica del ferro: non usarli per dichiarare un canestro segnato.

## Sei intervalli continui: 690 frame

La prova promettente è stata estesa a tutti i frame degli stessi sei intervalli.
Per ogni frame: inferenza hoop full-frame, ROI automatico ball, unione con i
candidati baseline full-frame/tiled già salvati e NMS/score/tracker esistenti,
con parametri invariati. Riutilizzo dei candidati baseline, non un nuovo job.

| Episodio | Accettate baseline | Palla verificata nella variante | Sfondo | Teste | Candidati tiro baseline / variante |
|---|---:|---:|---:|---:|---:|
| 0 | 24 | 37 | 26 | 0 | 0 / 0 |
| 1 | 9 | 24 | 6 | 0 | 0 / 0 |
| 2 | 7 | 26 | 16 | 0 | 0 / 1 |
| 3 | 2 | 13 | 0 | 0 | 0 / 0 |
| 4 | 0 | 8 | 15 | 4 | 0 / 0 |
| 5 | 0 | 16 | 0 | 0 | 0 / 0 |
| Totale | 42 | 124 | 63 | 4 | 0 / 1 |

Revisionate tutte le 191 accettazioni, su cinque tavole più il frame nativo
36217 per il box che include anche parte della mano. Le etichette certificano
l'oggetto visibile nel box, non l'IoU preciso. Tutti i 42 frame accettati dalla
baseline conservano una palla accettata nella variante: 82 frame palla recuperati,
insieme a 67 accettazioni false. Le tracce possono cambiare oggetto: nell'episodio
4 la track 5 passa dalla palla a una testa. Aumentare i conteggi non risolve
l'identità semantica.

Il candidato a 1175.7 s è sulla traiettoria del tiro dell'episodio 2. Per questa
sola valutazione delle traiettorie è stata riusata la geometria del ferro già
revisionata, interpolata tramite il diagnostico esistente. NON è un risultato
end-to-end automatico: non risolve la localizzazione precisa del ferro, non
misura eventi negativi su tutto il video e non classifica esito o squadra.

Costo misurato aggiuntivo sui 690 frame: **159.53 s**, inclusi decodifica, hoop,
ROI e unione; esclusi caricamento/warm-up, baseline già salvata, replay e tavole.
Sommare i precedenti 162.56 s baseline dà circa 322.09 s (+98%): è una stima,
non una misura accoppiata end-to-end né una previsione della VM.

## Associazione e regressioni

Confrontata offline una modifica mirata all'ordinamento delle associazioni:
distanza assoluta anziché distanza divisa per una finestra crescente con l'età
della traccia. Sui sei episodi mantiene i 124 box palla già verificati e produce
due candidati con geometria revisionata, ma accetta anche una nuova testa.
Sul minuto 500–560 s conserva i conteggi noti (31 palle, 61 scarpe, 4 incerti)
e aggiunge **otto scarpe**, tutte controllate sulla tavola delle differenze.
Correzione non promossa: il problema individuato non giustifica una regressione.
Il prototipo del worker resta ignorato e non sostituisce il sorgente applicativo.

Provata anche la finestra temporale già esistente sui nuovi candidati: due
candidati tiro, ma 54 nuove accettazioni non revisionate e perdita di due box
palla precedenti. Sul minuto riproduce il peggioramento già noto (79 scarpe,
45 palle, 20 incerti). Non promossa; nessuna soglia ricercata o cambiata.

## Esempi e stato della coda

Preparati **329 ritagli nativi di proposte verificate**: 171 palle, 90 scarpe,
63 sfondi e cinque teste. Riutilizzati i 129 esempi precedenti, aggiunti i 191
box della prova e le nove regressioni appena controllate. I 20 incerti del
vecchio audit restano esclusi. Manifest con frame, box, etichetta, episodio,
sorgente e SHA-256. Si tratta di classificazione delle proposte, NON di label
YOLO complete: un frame con una scarpa può contenere anche una palla reale.

Questa coda sperimentale è completata: screening, prova ROI, replay continui,
revisione completa, regressioni, pacchetto semantico e verifica dell'interfaccia.
Tutti gli esempi appartengono a una sorgente già esaminata. Nessuno split
train/val/test inventato, training avviato o miglioramento generale dichiarato.

Il prossimo ciclo deve fissare un riferimento distinto per sorgente prima di
selezionare/addestrare un discriminatore semantico e rieseguire la prova degli
eventi. È stato richiesto il percorso di un altro video locale: non è richiesto
all'utente di classificare tiri o produrre annotazioni nell'app. La preparazione
indipendente dei dati disponibili è completata.

## Script e verifiche

- `screen_automatic_roi.py`: ablation del ritaglio guidato dal modello.
- `replay_automatic_roi.py`: estensione sui sei intervalli continui.
- `review_continuous.py`: confronto con regole tiro invariate e tavole esaustive.
- `record_review.py`: corrispondenze visive esplicite e conservazione dei frame palla.
- `compare_distance_ranking.py`: confronto di associazione e politica temporale.
- `prepare_semantic_examples.py`: ritagli con provenienza, senza training.
- `build_hoop_boards.py` / `build_proposal_board.py`: sovrapposizioni diagnostiche.

32 test esistenti superati (2 benchmark, 18 tracker, 12 shot detector), sintassi
degli script verificata. Build frontend e smoke browser desktop/mobile superati:
analisi CV visibile in primo piano, annotazione manuale raccolta in sezioni chiuse,
salvataggi e dati precedenti preservati. Nessuna migrazione o configurazione nuova.
Pesi, wheel, immagini, JSON e ritagli sono diagnostica locale ignorata da Git.
