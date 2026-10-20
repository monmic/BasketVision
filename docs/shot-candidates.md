# ShotDetector: esperimento offline 0.1

## Integrazione applicativa sperimentale

L'analisi può ora ricevere una calibrazione esplicita del ferro e produrre
eventi `ShotCandidate` end-to-end. Nell'interfaccia si abilita la funzione,
si imposta la larghezza del ferro nei pixel originali e si seleziona il centro
direttamente sul video. La calibrazione è limitata all'intervallo DA → A e va
usata solo quando l'inquadratura resta fissa.

I candidati vengono calcolati sulle detection accettate al termine del job,
salvati in `GameEvents` con squadra nulla e mostrati sia nel report Vision sia
nella lista eventi. Restano esclusi dalle statistiche: lo stato di revisione,
la motivazione, la track, la calibrazione e i tre punti di evidenza sono
conservati nei metadata. Pausa e ripresa mantengono i punti nel checkpoint;
la scrittura finale sostituisce gli eventuali candidati dello stesso job per
evitare duplicati. La cancellazione dell'analisi li rimuove insieme agli altri
eventi del job.

Il risultato non classifica segnato/sbagliato e non attribuisce la squadra.
Nessun candidato non implica assenza di tiri: la copertura dipende ancora dal
rilevamento e dal tracking della palla.

## Modelli confrontati su Home vs Away e dataset pilota

Completato il confronto sui 72 frame revisionati, stessa soglia 0,02, ingresso
960, IoU 0,5, due thread CPU. Solo inferenza full-frame, senza tracker, tile o
filtri geometrici: non confrontare direttamente i falsi positivi con la pipeline
completa delle sezioni precedenti.

| Modello | Palle abbinate | Detection non abbinate | Palle perse | Inferenza |
|---|---:|---:|---:|---:|
| yolo26n attuale | 18 | 46 | 54 | 27,30 s |
| Lumos | 17 | 780 | 55 | 9,61 s |
| Universitario | 15 | 60 | 57 | 51,38 s |

Tempi di una singola esecuzione, esclusi warm-up e decodifica. I pesi sono quelli
già descritti nelle fonti del confronto precedente. Report integrali in
`storage/diagnostics/home-vs-away-model-benchmark/`; riepilogo versionabile con
hash dei pesi e quattro soglie in `vision/fixtures/home-vs-away-model-comparison.json`.

La sensibilità alle soglie evidenzia compromessi, non un vincitore universale:
a 0,10 l'attuale ottiene 7 TP/2 FP e l'universitario 9 TP/5 FP; a 0,25 ottengono
3/0 e 4/1 rispettivamente. Lumos mantiene numerosi falsi rilevamenti anche a
0,50 (8 TP/78 FP). Nessuna sostituzione del worker giustificata da questo piccolo
campione, che contiene solo frame positivi ed è stato revisionato durante lo sviluppo.

### Dataset pilota esportato

Implementato `scripts/export_ball_dataset.py`: esporta PNG originali e label YOLO
normalizzate (classe unica `0: ball`), con split per episodio e manifest che
conserva indici frame, provenienza e hash delle annotazioni. Frame esclusi o non
revisionati non diventano label vuote. Rifiuta fonti discordanti, frame non
assegnati, episodi condivisi, sovrapposizioni e output preesistenti.

Dataset locale: `storage/diagnostics/home-vs-away-dataset-v1/`.
Piano in `vision/fixtures/home-vs-away-ball-split-v1.json`:

- Train: tiri 1–3, 41 immagini e 41 box.
- Validazione: tiro 4, 16 immagini e 16 box.
- Test: tiro 5, 15 immagini e 15 box.

Cinque test dell'esportatore superati. Verificati tutti i 72 PNG 854×480, la
corrispondenza tra etichette e annotazioni e l'assenza di frame condivisi.
Il `data.yaml` usa il percorso assoluto del container dove è stato generato;
se si sposta il dataset, aggiornare `path` al nuovo percorso.

È un dataset per un esperimento esplorativo, non pronto per conclusioni di
produzione: nessun negativo verificato e tutti i tiri sono già stati esaminati.
La separazione per episodio evita la condivisione della stessa azione tra split,
ma non elimina il fatto che siano scene della stessa partita già usate nello
sviluppo. Nessun training o deploy avviato.

### Campione aggiuntivo preparato

Pagina `storage/diagnostics/home-vs-away-ball-expansion/index.html`: 20 nuovi
frame, quattro per sequenza a 400–403, 500–503, 520–523, 540–543, 560–563 s.
Piano versionato in `vision/fixtures/home-vs-away-ball-expansion-plan.json`.
Sono esterni ai cinque tiri, selezionati per tempo senza inferire presenza o
assenza della palla; richiedono annotazione prima dell'uso. Non sono stati
inclusi automaticamente nel dataset né dichiarati negativi.
Le esportazioni hanno nomi `home-vs-away-extra-001.json` … `extra-005.json`.
Il prossimo passo sui dati è revisionare questo campione e aggiungere negativi
verificati prima di usare il training per decidere un cambio del modello.

## Copia revisionata delle annotazioni — v1

Creata `vision/fixtures/home-vs-away-ball-annotations-revised-v1.json` preservando
l'originale e registrandone SHA-256. Ridisegnati manualmente 14 box sui ritagli
originali ingranditi senza overlay del modello, includendo la parte visibile e
il blur della palla. Verificati poi visivamente i nuovi rettangoli sovrapposti.
Le coordinate sono approssimate al pixel originale, non copiate dalle detection.
Gli altri 58 box positivi restano quelli dell'utente.

Esclusi gli 8 frame dichiarati vuoti: il controllo visivo non permette di
certificarli come negativi. Anche il ritaglio a 449,8 s presenta una regione
scura compatibile con la palla ma contorni ambigui presso mano e corpo: escluso
invece di aggiungere un box incerto. La copia contiene quindi 72 frame positivi
e 72 box, senza negativi verificati. Non è ancora un dataset completo per training.

Modifiche esplicite e motivazioni in `vision/fixtures/home-vs-away-ball-revision-v1.json`.
Riproduzione senza sovrascrivere file esistenti:

```powershell
py -3.12 scripts/revise_ball_annotations.py vision/fixtures/home-vs-away-ball-annotations.json vision/fixtures/home-vs-away-ball-revision-v1.json vision/fixtures/home-vs-away-ball-annotations-revised-v1.json
py -3.12 -m unittest discover -s scripts -p test_revise_ball_annotations.py
```

Confronto a IoU 0,5 sulla copia revisionata:

| Pipeline | Accettati abbinati | Accettati non abbinati | Palle senza detection accettata |
|---|---:|---:|---:|
| Originale | 5 | 2 | 67 |
| Tracker temporale + filtro camera | 9 | 2 | 63 |
| Tracker sperimentale + ROI ferro | 9 | 2 | 63 |

Prima del tracker: 18 candidati abbinati, 42 non abbinati, 54 palle perse in
tutte le varianti. Con i vecchi box sugli stessi 72 frame, gli abbinamenti erano
4 grezzi e 2 accettati. Il cambiamento deriva dalla revisione del riferimento,
non da nuove inferenze né da un miglioramento del codice. Il riferimento
revisionato mostra quattro abbinamenti accettati in più per il tracker
sperimentale rispetto all'originale, ma non dimostra assenza di regressioni
altrove né risolve la shot detection.

La selezione dei box revisionati è stata guidata dalle discrepanze del modello:
questo resta un confronto diagnostico, non un test indipendente. Nessuna soglia
di valutazione modificata e nessun addestramento/deploy effettuato.
Report con confronto prima/dopo sugli stessi frame:
`storage/diagnostics/home-vs-away-ball-audit/revised-v1-evaluation.json`.
Ritagli senza overlay `refine-0.png` … `refine-2.png`, verifica dei nuovi box
`revised-boxes-0.png` … `revised-boxes-2.png`, nella stessa cartella.

## Revisione visiva delle sovrapposizioni

Esportati ed esaminati tutti gli 80 frame in 20 tavole, con annotazioni verdi e
candidati grezzi originali rossi. Pagina locale:
`storage/diagnostics/home-vs-away-ball-audit/index.html`. Generatore riproducibile:
`scripts/export_ball_annotation_audit.py VIDEO ANNOTATIONS REPORT OUTPUT`, da
eseguire con OpenCV e `evaluate_ball_clip.py` nella stessa cartella.

La revisione distingue due problemi: differenze nell'estensione dei rettangoli
e detection assenti. Sulle 72 palle annotate, 4 hanno una corrispondenza a IoU
0,5; altre 14 hanno sovrapposizione positiva ma inferiore a 0,5; le restanti 54
non intersecano alcun candidato. Nei frame 440,0 e 440,2 s, ad esempio, il modello
localizza la palla ma il rettangolo è più stretto dell'annotazione. Nel terzo
episodio persistono detection sul bordo sinistro mentre la palla è presso il
canestro destro; nei passaggi presso tabellone e retina sono frequenti le lacune.

Sensibilità della pipeline originale al criterio di abbinamento:

| IoU | Candidati abbinati / non abbinati / palle perse | Accettati abbinati / non abbinati / palle perse |
|---|---|---|
| 0,5 | 4 / 60 / 68 | 2 / 5 / 70 |
| 0,3 | 18 / 46 / 54 | 5 / 2 / 67 |
| 0,1 | 18 / 46 / 54 | 5 / 2 / 67 |

La soglia di valutazione resta 0,5. Il confronto a soglie inferiori è diagnostico:
non rappresenta un miglioramento del modello e non giustifica correggere i box
umani copiando quelli predetti. Il precedente 2/72 misura quindi gli abbinamenti
stretti, non tutte le detection visivamente sulla palla.

Segnalato inoltre il frame 13494 (449,8 s), dichiarato senza palla: nella tavola
la palla sembra visibile accanto alla mano del giocatore vicino al canestro
destro. Va riesaminato prima del training. Le altre assenze in situazioni di
occlusione non sono certificate come negativi dal controllo delle sole tavole.

Esito e lista dei frame da rivedere salvati in
`vision/fixtures/home-vs-away-ball-audit.json`; dettagli geometrici e sensibilità
in `overlaps.json` e `iou-sensitivity.json` nella cartella locale di revisione.
Annotazioni originali preservate. Campione non ancora dichiarato pronto per
training: servono rettangoli coerenti sui bordi visibili e distinzione tra
assenza verificata e occlusione/ambiguità. Nessun cambio al worker.

## Annotazioni complete: cinque episodi su cinque

Validato il quinto episodio: 16 frame, 15 rettangoli palla e un frame dichiarato
senza palla. Sorgente, FPS, indici e coordinate coerenti con il piano.
Copia in `vision/fixtures/home-vs-away-shot-005-ball-annotations.json`.
Sui frame del quinto episodio tutte e tre le varianti hanno 0 palle corrette
accettate, 1 detection accettata non abbinata e 15 palle senza detection
accettata. Prima del tracker: 0 candidati abbinati, 5 non abbinati e 15 palle
senza candidato corrispondente.

Riuniti i cinque episodi, senza duplicati, in
`vision/fixtures/home-vs-away-ball-annotations.json`: **80 frame revisionati,
72 rettangoli palla, 8 frame dichiarati senza palla**. Originali preservati.
Le annotazioni vuote sono interpretate secondo le dichiarazioni dell'utente;
questa acquisizione non include una nuova revisione visiva dei box.

Confronto complessivo sui soli 80 frame, IoU >= 0,5, abbinamento uno a uno:

| Pipeline | Palle corrette accettate | Detection accettate non abbinate | Palle senza detection accettata |
|---|---:|---:|---:|
| Originale | 2 | 5 | 70 |
| Tracker temporale + filtro camera | 2 | 9 | 70 |
| Tracker sperimentale + ROI ferro | 2 | 9 | 70 |

Prima del tracker tutte le varianti hanno 4 candidati abbinati, 60 non abbinati
e 68 palle senza candidato corrispondente. Questo riferimento non mostra
vantaggi delle varianti sperimentali. I mancati abbinamenti possono dipendere
anche dalla precisione dei rettangoli: verificare visivamente sovrapposizioni
e convenzioni di annotazione prima di utilizzare il campione per il training.
Sono conteggi di detection a 5 fps, non metriche di riconoscimento dei tiri
né una misura globale del video.

Report locali in `storage/diagnostics/home-vs-away-ball-review/`:
`shot-005-evaluation.json` e `all-episodes-evaluation.json`.
Acquisizione dei cinque episodi completata; nessuna modifica al worker.
Il riferimento aggregato è destinato anzitutto alla valutazione: non usarlo
contemporaneamente come training e test. Un eventuale fine-tuning richiede
altri dati o una separazione esplicita per sequenza.

## Quarto episodio annotato dall'utente

Validato `home-vs-away-shot-004.json`: 16/16 frame del piano, 16 rettangoli
palla e nessun frame dichiarato senza palla. Sorgente, FPS, indici e coordinate
coerenti. Copia conservata in `vision/fixtures/home-vs-away-shot-004-ball-annotations.json`.
Nessuna nuova revisione visiva delle annotazioni.

Confronto IoU >= 0,5 sui soli frame annotati: tutte e tre le pipeline
(originale, tracker temporale con filtro camera, tracker sperimentale con ROI
ferro) producono 0 palle corrette accettate, 0 detection accettate non abbinate
e 16 palle senza detection accettata. Prima del tracker: 0 candidati abbinati,
4 non abbinati e 16 palle senza candidato corrispondente. Il mancato abbinamento
può includere errori di localizzazione rispetto ai rettangoli dell'utente.
I risultati riguardano il campione a 5 fps, non tutti i frame dell'episodio.

Report: `storage/diagnostics/home-vs-away-ball-review/shot-004-evaluation.json`.
Quattro episodi acquisiti su cinque; nessuna modifica al worker.

## Terzo episodio annotato dall'utente

Validato `home-vs-away-shot-003.json`: 16/16 frame del piano, 12 rettangoli
palla e 4 frame confermati senza palla. Sorgente, FPS, indici e coordinate
coerenti. Copia conservata in `vision/fixtures/home-vs-away-shot-003-ball-annotations.json`.
Le assenze sono dichiarazioni dell'utente; nessuna nuova revisione visiva.

Confronto IoU >= 0,5 sui frame annotati: tutte e tre le pipeline (originale,
tracker temporale con filtro camera, tracker sperimentale con ROI ferro)
producono 0 palle corrette accettate, 2 detection accettate non abbinate e
12 palle senza detection accettata. Prima del tracker: 0 candidati abbinati,
15 non abbinati e 12 palle senza candidato corrispondente.
Un box non abbinato può anche indicare localizzazione imprecisa rispetto
all'annotazione, non necessariamente un oggetto diverso dalla palla.

Report: `storage/diagnostics/home-vs-away-ball-review/shot-003-evaluation.json`.
Tre episodi acquisiti su cinque; nessuna modifica al worker.

## Secondo episodio annotato dall'utente

Validato `home-vs-away-shot-002.json`: 16/16 frame del piano, 13 rettangoli
palla e 3 frame confermati senza palla. Sorgente, FPS, indici e coordinate
coerenti. Copia conservata in `vision/fixtures/home-vs-away-shot-002-ball-annotations.json`.
I frame vuoti sono trattati come assenze dichiarate dall'utente; nessuna nuova
verifica visiva delle annotazioni è stata eseguita.

Confronto IoU >= 0,5 sui soli frame annotati:

| Pipeline | Palle corrette accettate | Detection accettate non abbinate | Palle senza detection accettata |
|---|---:|---:|---:|
| Originale | 0 | 0 | 13 |
| Tracker temporale + filtro camera | 0 | 3 | 13 |
| Tracker sperimentale + ROI ferro | 0 | 3 | 13 |

Prima del tracker: 0 candidati abbinati, 15 non abbinati e 13 palle senza
candidato corrispondente in tutte e tre le varianti. Un box non abbinato può
anche essere una localizzazione imprecisa rispetto al rettangolo annotato:
queste metriche non dimostrano da sole che ogni candidato sia su un altro oggetto.
Report: `storage/diagnostics/home-vs-away-ball-review/shot-002-evaluation.json`.
Due episodi acquisiti su cinque; nessuna modifica al worker.

## Primo episodio annotato dall'utente

Ricevute 16 esportazioni cumulative del tiro 7:14: ciascuna conserva i frame
confermati in precedenza, senza conflitti. `home-vs-away-shot-001 (15).json`
contiene l'intero episodio: 16 frame e 16 rettangoli. Verificati sorgente,
FPS, coordinate normalizzate e corrispondenza esatta al piano di campionamento.
Originali preservati. Copia per regressioni in
`vision/fixtures/home-vs-away-shot-001-ball-annotations.json`.

Valutazione sui soli 16 frame annotati, IoU >= 0,5, abbinamento uno a uno:

| Pipeline | Palle corrette accettate | Detection accettate non abbinate | Palle senza detection accettata |
|---|---:|---:|---:|
| Originale | 2 | 2 | 14 |
| Tracker temporale + filtro camera | 2 | 3 | 14 |
| Tracker sperimentale + ROI ferro | 2 | 3 | 14 |

Prima del tracker tutte e tre le varianti hanno 4 candidati abbinati, 21 non
abbinati e 12 palle senza candidato corrispondente. Il riferimento conferma
il limite del rilevatore su questo episodio; il conteggio dei punti accettati
da solo non misura il miglioramento. Sono metriche rispetto ai box dell'utente,
non una nuova revisione visiva: errori di localizzazione possono produrre una
coppia falso positivo/falso negativo. Nessuna stima globale sui tiri.

Report locale: `storage/diagnostics/home-vs-away-ball-review/shot-001-evaluation.json`.
Per gli altri episodi basta scaricare una volta il JSON dopo aver confermato
tutti i frame: l'esportazione include tutte le annotazioni confermate nella pagina.

## Pagina di annotazione Home vs Away

Creato il pacchetto locale `storage/diagnostics/home-vs-away-ball-review/index.html`.
Aprirlo nel browser: contiene cinque episodi, ciascuno con 16 frame originali
campionati ogni 0,2 secondi, per un totale di 80 frame. Intervalli inclusivi:
433–436, 440–443, 449–452, 455–458 e 472–475 secondi. I frame sono decodificati
sequenzialmente dal video originale per conservarne gli indici esatti.

Disegnare un rettangolo stretto attorno a ogni palla visibile, anche fuori dal
gioco, poi premere **Conferma palle**. Usare **Escludi frame** per posizione
ambigua o occlusione; **Nessuna palla** solo per assenza verificata. I frame
non confermati non vengono esportati come negativi. Nessuna detection del
modello è precompilata come annotazione vera.

Prima di chiudere ogni pagina, scaricare il JSON: i nomi sono distinti,
`home-vs-away-shot-001.json` fino a `home-vs-away-shot-005.json`. Il lavoro
resta in memoria fino all'esportazione. Conservare i file per la successiva
valutazione; non serve rilanciare l'analisi partita. Il campione a 5 fps serve
alla prima revisione, non prova continuità delle traiettorie a 30 fps.

Piano riproducibile: `vision/fixtures/home-vs-away-ball-review-plan.json`.
Generatore: `scripts/prepare_shot_ball_review.py`, con il template
`scripts/ball_review.html` nella stessa cartella. Richiede OpenCV, disponibile
nel container worker. Il generatore rifiuta cartelle di output già esistenti.

```powershell
docker compose cp scripts/prepare_shot_ball_review.py worker:/tmp/prepare_shot_ball_review.py
docker compose cp scripts/ball_review.html worker:/tmp/ball_review.html
docker compose cp vision/fixtures/home-vs-away-ball-review-plan.json worker:/tmp/home-vs-away-ball-review-plan.json
docker compose exec -T worker python /tmp/prepare_shot_ball_review.py /app/storage/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4 /tmp/home-vs-away-ball-review-plan.json /app/storage/diagnostics/home-vs-away-ball-review
```

## Confronto eseguito con due modelli specializzati — 22 settembre 2026

Scaricati e provati due checkpoint pubblici, con revisioni e SHA-256 salvati in
`vision/fixtures/specialist-model-benchmark.json`. Inferenza in container separati,
senza rete, filesystem del container in sola lettura, dati montati in lettura
e scrittura limitata alla cartella dei risultati. Solo classe palla, nessuna
identificazione dei giocatori. Worker applicativo invariato.

Fonti e licenze dichiarate dagli autori:

- [Lumos-88](https://huggingface.co/Lumos-88/YOLO11-fine-tuned-for-basketball-detection): specializzato su riprese da drone, MIT dichiarata; il checkpoint conserva le etichette COCO, palla = `32: sports ball`.
- [446f6e6e79](https://huggingface.co/446f6e6e79/YOLO-basketball-fineTuned): addestrato su una partita universitaria, MIT dichiarata; palla = `0: Ball`. L'autore segnala limiti di generalizzazione.

Le dichiarazioni di licenza delle schede non risolvono da sole gli obblighi
di distribuzione dei modelli base o dei dataset. Nessun peso incluso in Git.

Stessi 22 frame annotati, 12 palle, full-frame 960, confidence 0,02, IoU 0,5:

| Modello | Palle trovate | Falsi rilevamenti | Palle perse | Inferenza CPU |
|---|---:|---:|---:|---:|
| Attuale yolo26n | 4 | 8 | 8 | 4,19 s |
| Lumos | 3 | 222 | 9 | 2,65 s |
| Universitario | 3 | 30 | 9 | 16,05 s |

Controllo aggiuntivo filtrando i box salvati a confidence 0,10 / 0,25 / 0,50:
nessuna evidenza di un vantaggio dei due specialisti sul campione. A 0,50 il
modello universitario e quello attuale hanno entrambi 2 veri positivi e 0 falsi
positivi; Lumos ha 2 veri positivi e 54 falsi positivi. Non è una ricerca di
soglie validata su un insieme di test indipendente, né un benchmark della
pipeline completa. I tempi sono singole misure, esclusi warm-up e decodifica.

Risultati locali in `storage/diagnostics/specialist-benchmark/`:
`lumos-ball-960.json`, `university-ball-960.json`, `threshold-comparison.json`.
Il preliminare `lumos-960.json` filtrava erroneamente la classe person ed è
escluso dal confronto. Aggiunto `--class-name` al benchmark: se l'etichetta non
corrisponde all'indice richiesto, interrompe la prova prima dell'inferenza.
Usare `--class-id 32 --class-name "sports ball"` per Lumos e
`--class-id 0 --class-name Ball` per il modello universitario.

Due test benchmark superati. Nessun sostituto selezionato e nessun deploy:
queste prove non modificano il risultato dei cinque tiri Home vs Away.
Il prossimo sviluppo utile è costruire un riferimento annotato dei passaggi
vicino al ferro su quel video e usarlo per valutazione e fine-tuning con una
separazione per sequenza tra training e test, evitando frame adiacenti nei due set.

## Benchmark dei modelli — 22 settembre 2026

Aggiunto `scripts/benchmark_ball_model.py` per confrontare pesi locali su frame
già annotati, prima dell'integrazione nel worker. Supporta classe palla esplicita
(anche diversa da COCO 32), dimensione d'ingresso e confidence. Registra SHA-256
dei pesi, classe, impostazioni CPU, detection e metriche IoU 0,5 con abbinamento
uno a uno. Nessun download implicito e nessuna scrittura nel database.

Prime prove eseguite sui 22 frame annotati di `test-online-720p-15fps.mp4`
(12 palle annotate), usando `yolo26n.pt`, confidence 0,02 e due thread CPU:

| Ingresso | Palle trovate | Falsi rilevamenti | Palle perse | Inferenza totale |
|---|---:|---:|---:|---:|
| 960 | 4 | 8 | 8 | 4,19 s |
| 1280 | 4 | 11 | 8 | 4,46 s |

Inferenza solo full-frame, senza tile, filtri geometrici o tracker. Questi
conteggi non sono direttamente confrontabili con quelli della pipeline completa.
Tempi di singole esecuzioni, esclusi caricamento, warm-up e decodifica; non sono
stime delle prestazioni in produzione. Il campione è piccolo e diverso dai
cinque tiri Home vs Away: il risultato non cambia lo 0/5 della prova precedente.
L'ingresso più grande non migliora il conteggio dei veri positivi in questo
campione; non è stato attivato nel worker. Nessun modello alternativo è stato
ancora valutato: nel container era disponibile solo `yolo26n.pt`.

Report locali in `storage/diagnostics/model-benchmark-yolo26n.json` e
`storage/diagnostics/model-benchmark-yolo26n-1280.json`.

Esempio riproducibile (il nome di output deve essere nuovo):

```powershell
docker compose cp scripts/benchmark_ball_model.py worker:/tmp/benchmark_ball_model.py
docker compose cp scripts/evaluate_ball_clip.py worker:/tmp/evaluate_ball_clip.py
docker compose exec -T worker python /tmp/benchmark_ball_model.py /app/storage/videos/test-online-720p-15fps.mp4 /app/storage/diagnostics/annotations.json /app/yolo26n.pt /app/storage/diagnostics/model-benchmark-new.json --class-id 32 --imgsz 960
py -3.12 -m unittest discover -s scripts -p test_ball_benchmark.py
```

Due test superati: validazione delle annotazioni e conteggio di duplicati,
assenze revisionate, frame esclusi e frame mancanti. Per un detector specializzato
usare il relativo file di pesi locale e l'indice della sua classe palla.

## Intervento: inferenza mirata vicino al ferro

Aggiunto ed eseguito `scripts/diagnose_rim_roi.py`: usa la calibrazione manuale
per ritagliare una regione larga otto volte il ferro (208 px in questo campione)
e applica il modello palla a `imgsz=640` su ogni frame calibrato. Riporta i box
nelle coordinate originali e li unisce ai candidati esistenti con la stessa NMS
e lo stesso punteggio geometrico del worker. Non abbassa le soglie del tracker.
Il minuto completo viene poi rielaborato dal tracker per conservarne il contesto.
È uno strumento offline: non introduce calibrazione automatica né cambia il servizio.

Prova completata sui cinque episodi: 455 frame, 81,7 secondi di elaborazione
locale escluso caricamento modello, 21 detection ROI grezze, confidence massima
0,1055. Il replay passa da 158 a 159 punti accettati nel minuto. Recupera un
punto sulla palla a 435,533 s (verificato nel ritaglio `rim-roi-gain.jpg`) e
sostituisce con un box quasi identico l'osservazione a 473,133 s. Nessun altro
cambiamento alle coordinate delle detection accettate nel minuto confrontato.

I punti nei cinque intervalli calibrati diventano rispettivamente 30, 10, 15,
6 e 4. **I candidati tiro restano 0/5**: l'ingrandimento locale, con questo
modello, non recupera abbastanza osservazioni per chiudere le traiettorie.
Non è quindi una modifica da attivare nell'analisi partita allo stato attuale.
Il prossimo esperimento deve valutare un modello palla più adatto su frame
annotati vicino al ferro, includendo tabellone, retina e giocatori come negativi;
il solo aumento della risoluzione del ritaglio non ha risolto questo campione.

Artefatti in `storage/diagnostics/home-vs-away-shots/`:

- `rim-roi-raw.json`: candidati aggiuntivi e regione usata; richiede replay prima di leggere gli stati del tracker.
- `rim-roi-replay.json`: risultato del tracker temporale con filtro camera.
- `rim-roi-shots.json`: confronto dei cinque episodi con l'analisi originale.

Esecuzione dell'inferenza nel container worker con gli script diagnostici copiati
in `/tmp/basketvision-camera/scripts` e il modulo `shot_detector.py` nella
sottocartella sorella `vision`; calibrazione copiata in `/tmp/rim-keyframes.json`:

```powershell
docker compose exec -T worker python /tmp/basketvision-camera/scripts/diagnose_rim_roi.py /app/storage/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4 /app/storage/diagnostics/home-vs-away-shots/full-minute/camera-motion-v2.json /tmp/rim-keyframes.json /app/storage/diagnostics/home-vs-away-shots/rim-roi-raw.json
py -3.12 scripts/replay_ball_tracker.py storage/diagnostics/home-vs-away-shots/rim-roi-raw.json --temporal-window --camera-filter --output storage/diagnostics/home-vs-away-shots/rim-roi-replay.json
py -3.12 scripts/diagnose_reviewed_shots.py storage/analysis/a0dca029-f7a0-4819-90b0-603cff2bfe32.json storage/diagnostics/home-vs-away-shots/rim-roi-replay.json vision/fixtures/home-vs-away-rim-keyframes.json --output storage/diagnostics/home-vs-away-shots/rim-roi-shots.json
```

Gli output devono avere nomi nuovi. Verifica: 14 test della logica tiro superati
e compilazione Python dello script riuscita. Nessun deploy effettuato.

## Prova eseguita sui cinque tiri con ferro calibrato

Calibrazione manuale approssimata salvata in
`vision/fixtures/home-vs-away-rim-keyframes.json`: centro e larghezza del ferro
in pixel originali, con keyframe ogni secondo e interpolazione lineare, senza
estrapolazione. Lo script `scripts/diagnose_reviewed_shots.py` normalizza i punti
rispetto al ferro mobile e applica le regole esistenti. Le evidenze restituite
rimangono nelle coordinate del video. Non scrive eventi nel database.

Risultato locale: `storage/diagnostics/home-vs-away-shots/reviewed-shot-results.json`.
Confronto tra analisi originale e replay sperimentale con filtro del movimento
della camera (`camera-motion-final/experimental.json`): **zero candidati su tutti
e cinque gli episodi**, per entrambe le versioni.

| Tiro | Intervallo calibrato (s) | Punti originale / replay | Candidati originale / replay | Evidenza nel replay |
|---|---|---|---|---|
| 7:14 | 433–436 | 24 / 29 | 0 / 0 | La sequenza di avvicinamento si interrompe circa 52 px sopra il ferro; le osservazioni successive non completano il passaggio. |
| 7:21 | 440–443 | 0 / 10 | 0 / 0 | Mancano le osservazioni al ferro; la palla ricompare circa 59 px sotto. |
| 7:30 | 449–452 | 14 / 15 | 0 / 0 | I punti accettati seguono il bordo sinistro dell'immagine, lontano dal canestro: falsi rilevamenti. |
| 7:36 | 455–458 | 0 / 6 | 0 / 0 | La traccia termina circa 50 px sopra il ferro. |
| 7:53 | 472–475 | 2 / 4 | 0 / 0 | Quattro punti vicini al ferro, con escursione verticale di circa 4 px: insufficiente per la soglia di 13 px e il movimento monotono richiesti. |

I conteggi indicano detection accettate dal tracker, non palle verificate.
Queste finestre sono diverse dalle finestre più ampie usate nei confronti sotto.
Variando separatamente il centro del ferro di ±3 px lungo ciascun asse e la
larghezza di ±2 px si ottengono ancora zero candidati in ogni episodio.
Questo controllo non rende esatta la calibrazione né misura l'accuratezza globale:
i keyframe restano approssimati e il movimento tra essi può essere non lineare.
Il tipo di tiro, il contatto e l'esito rimangono annotazioni dell'utente.

Comando per riprodurre la prova (scegliere un nuovo nome di output se esiste già):

```powershell
py -3.12 scripts/diagnose_reviewed_shots.py storage/analysis/a0dca029-f7a0-4819-90b0-603cff2bfe32.json storage/diagnostics/home-vs-away-shots/camera-motion-final/experimental.json vision/fixtures/home-vs-away-rim-keyframes.json --output storage/diagnostics/home-vs-away-shots/reviewed-shot-results.json
py -3.12 -m unittest discover -s scripts -p "test*shot*.py"
```

Verifica: 14 test superati, inclusi interpolazione senza estrapolazione,
invarianza a traslazione/zoom, ripristino delle coordinate delle evidenze e
interruzione delle sequenze escluse dal filtro del movimento.
La prova offline è completata; il riconoscimento automatico dei cinque tiri
non è risolto. Servono osservazioni migliori della palla vicino al ferro e una
regola verificata per le traiettorie brevi come quella delle 7:53 prima di integrare
il detector nell'analisi partita. Nessun deploy effettuato con questo esperimento.

## Annotazioni utente: Home vs Away

Riferimento salvato in `vision/fixtures/shot-review-home-vs-away.json`.
Tempi interpretati come minuti:secondi nel video. Partita locale verificata:
`35b68704-541f-4c6d-b8ab-45228266102a`, file
`storage/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4`.
Analisi associata: `a0dca029-f7a0-4819-90b0-603cff2bfe32`, intervallo
425–485 secondi (7:05–8:05), video 854×480 a 30 fps.
Queste sono annotazioni utente, non risultati del detector.

| Tempo | Tipo di tiro | Contatto | Esito |
|---|---|---|---|
| 7:14 | Da 3 punti | Ferro | Sbagliato |
| 7:21 | Da 3 punti | Airball con tocco retina | Sbagliato |
| 7:30 | Dentro l'area | Ferro | Sbagliato |
| 7:36 | Da 3 punti | Ferro | Sbagliato |
| 7:53 | Dentro l'area | Non specificato | Segnato |

Copertura parziale: gli intervalli non annotati non sono esempi negativi.

Verifica del report completato il 21 settembre 2026: 1800 frame analizzati
per la palla, 1428 candidati grezzi, 91 detection accettate e salvate, 11 tracce
confermate. Conteggi nelle finestre da 2 secondi prima a 3 secondi dopo ciascuna
annotazione (estremi inclusi):

| Tiro annotato | Punti palla accettati nella finestra |
|---|---:|
| 7:14 | 24 |
| 7:21 | 5 |
| 7:30 | 14 |
| 7:36 | 0 |
| 7:53 | 2 |

I cinque punti vicino a 7:21 sono tutti tra 439.000 e 439.133 secondi:
non dimostrano copertura del tiro. I due punti vicino a 7:53 sono a 473.000 e
473.033 secondi e non bastano ai tre punti richiesti dal detector.
Questa verifica misura solo la disponibilità delle osservazioni, non precisione
o richiamo dei tiri.

### Prima verifica visiva e correzione a 30 fps

Estratti quattro fotogrammi per tiro (da un secondo prima a due secondi dopo),
salvati in `storage/diagnostics/home-vs-away-shots/shot-<secondi>.jpg`.
Nei campioni del primo tiro e dell'airball il ferro resta circa nella stessa
posizione. Negli altri episodi la camera si sposta: non è valida una calibrazione
fissa comune all'intero minuto.

Corretto un problema del detector: la durata minima di 80 ms scartava tutte
le terne consecutive regolari a 30 fps (circa 67 ms). Restano i vincoli di tre
osservazioni, gap massimo, spostamento minimo e velocità massima. Il test di
regressione verifica movimento valido, jitter e salti di associazione a 30 fps.
I 10 test passano; non sono una misura dell'accuratezza sul video.

Due prove offline con calibrazione manuale approssimativa dai fotogrammi:

| Intervallo | Centro ferro (px) | Larghezza (px) | Candidati |
|---|---|---:|---:|
| 433–436 s | (258, 174) | 26 | 0 |
| 440–443 s | (257, 174) | 26 | 0 |

I JSON sono nella stessa cartella diagnostica, `shot-434-candidates.json` e
`shot-441-candidates.json`. La stabilità è verificata sui campioni a un secondo,
non su ogni frame: queste sono prove preliminari, non una valutazione definitiva.
Nel primo tiro la traccia termina a 435.467 s, centro (272.1, 122.2), circa 52 px
sopra il ferro: manca il tratto di avvicinamento richiesto dalla regola. Per
l'airball non ci sono punti accettati nell'intervallo 440–443 s.

Prossimo passo: diagnosticare i candidati grezzi e i rifiuti del tracker nei
tratti mancanti, a partire da 435.4–436 s e dal tiro senza punti delle 7:36.
Per gli episodi con camera in movimento serve una calibrazione variabile nel
tempo prima di valutare la shot detection. Nessuna classificazione automatica
segnato/ferro/fuori è stata introdotta.

### Diagnosi dei candidati prima del tracker

Eseguite due prove locali con `scripts/diagnose_ball_clip.py`, risoluzione
originale, `--stride 1`, intervalli 432–437 e 454–459 secondi. Risultati in
`storage/diagnostics/home-vs-away-shots/ball-432-437` e `ball-454-459`:
`custom.json` conserva candidati e motivi di scarto; `candidate-review.jpg`
mostra quattro fotogrammi con rettangoli verdi (accettati) e rossi (scartati).
Il tracker riparte all'inizio di ciascun segmento: non è una riproduzione del
suo intero stato a partire da 425 s. Le prove producono rispettivamente 24 e 0
punti accettati, coerenti con il report nei tratti dei due tiri.

- Primo tiro: dopo 435.467 s mancano candidati sulla palla vicino al ferro nei
  fotogrammi successivi esaminati. A 435.767 e 435.900 s la palla torna tra i
  candidati (verificata visivamente), ma viene scartata con
  `track_not_temporally_confirmed`. Sono quindi presenti sia lacune del
  rilevatore sia perdita di continuità del tracker.
- Tiro delle 7:36: la palla è visibile nei candidati a 456.567, 457.000,
  457.100 e 457.233 s, verificati sulle immagini. La prima osservazione deve
  attendere conferma; le altre vengono scartate come traccia non confermata.
  Numerosi punti intermedi hanno confidence sotto 0.12 e non possono
  aggiornare una traccia non confermata. Zero punti nel report non significa
  quindi che il modello non abbia mai rilevato la palla.

Nel codice attuale basta un frame senza associazione per portare una traccia
confermata in stato `lost`; la riconferma richiede tre hit consecutive. Per una
traccia non confermata i candidati deboli non contano come aggiornamenti.
La priorità successiva è sperimentare offline una conferma su una breve finestra
temporale e una riassociazione controllata dopo brevi lacune, confrontando anche
i falsi positivi già annotati. Non sono state modificate le soglie o la logica
del worker in produzione in seguito a queste due prove.

### Tracker sperimentale con conferma temporale

Implementata una modalità opzionale in `vision/worker.py`:

- `BALL_TRACK_TEMPORAL_WINDOW=true`: tre hit forti nella finestra, invece di tre
  hit consecutive. Le soglie di confidence e score rimangono quelle configurate.
- `BALL_TRACK_CONFIRM_WINDOW_SECONDS=0.2`: durata attuale della finestra di conferma
  (la prima prova sotto usava 0.5 s; vedere la revisione sul minuto completo).
- `BALL_TRACK_RECOVERY_SECONDS=0.1`: intervallo massimo dall'ultima osservazione
  per mantenere la conferma; restano anche il limite di miss e degli update deboli.
- Un update debole deve rimanere vicino alla previsione: al massimo una dimensione
  della detection, con minimo 8 px e limite superiore della distanza base configurata.
  Non può confermare una traccia nuova. I punti mancanti non vengono inventati.

La prima prova riportata sotto usava invece un limite di due dimensioni della
detection. La revisione sul minuto completo ha motivato il limite attuale.

La cronologia temporale è inclusa nei checkpoint. I vecchi checkpoint senza
cronologia vengono letti senza fabbricare hit precedenti. La configurazione è
registrata nel report JSON e i relativi campi frontend sono opzionali;
il backend serve già il report senza trasformazioni.

**Modalità disattivata per default**, anche in Compose: nel controllo con tile
ogni frame è emerso un falso positivo aggiuntivo. La modifica non è stata
deployata né attivata nel worker locale in esecuzione.

Confronto tramite replay degli stessi candidati, con tracker inizializzato
all'inizio di ciascun segmento:

| Campione | Accettate prima | Accettate con esperimento |
|---|---:|---:|
| Home vs Away, 432–437 s | 24 | 36 |
| Home vs Away, 454–459 s | 0 | 9 |

I 9 punti recuperati sul secondo segmento sono tra 456.967 e 457.267 s, sul
tratto di volo già revisionato. I conteggi non misurano accuratezza dei tiri,
e la lacuna vicino al ferro non è risolta. Sul primo segmento si recuperano
anche punti dopo l'interruzione, ma non la continuità necessaria presso il ferro.

Controllo sui 22 frame annotati del video online, IoU >= 0.5:

| Profilo | TP prima → dopo | FP prima → dopo | FN prima → dopo |
|---|---:|---:|---:|
| Tile ogni 3 frame (configurazione corrente) | 1 → 2 | 0 → 0 | 11 → 10 |
| Tile ogni frame (alternativa sperimentale) | 1 → 2 | 1 → 2 | 11 → 10 |

L'aumento di FP nel secondo profilo interessa il frame 195. Il campione è piccolo:
non dimostra assenza di regressioni nel resto del video. Una prima variante con
associazione debole troppo permissiva è stata scartata perché agganciava oggetti
lontani dalla traiettoria. I risultati finali sono nei file `tracker-final-replay.json`
delle quattro cartelle diagnostiche e in
`storage/diagnostics/home-vs-away-shots/tracker-comparison.json`.
Il comportamento con modalità disattivata coincide con il worker precedente su
tutti i candidati dei quattro replay.

Riproduzione senza inferenza o accesso al database, con output nuovo:

```powershell
py -3.12 scripts/replay_ball_tracker.py storage/diagnostics/home-vs-away-shots/ball-454-459/custom.json --temporal-window --output storage/diagnostics/home-vs-away-shots/replay-review.json
py -3.12 scripts/test_ball_tracker.py
py -3.12 scripts/test_shot_detector.py
```

Per una prova locale esplicita su un nuovo job, dopo aver valutato questi limiti,
impostare `BALL_TRACK_TEMPORAL_WINDOW=true` nel `.env` e ricostruire il worker con
`docker compose up -d --build worker`. Ripristinare `false` e ricreare il worker
per tornare alla logica precedente. Non occorre rieseguire inferenza per il
confronto sopra: i candidati salvati sono sufficienti.

### Confronto sull'intero minuto e decisione di attivazione

Rieseguita offline l'inferenza su tutti i 1800 frame di 425–485 s, mantenendo
le soglie del job originale. Il report diagnostico è
`storage/diagnostics/home-vs-away-shots/full-minute/custom.json`. Il tracker
precedente riproduce 91 accettazioni; i due replay usano esattamente gli stessi
candidati. La prova CPU a due thread ha richiesto circa 856 secondi, esclusi
caricamento e warm-up; non misura la durata sulla VM.

La revisione ha portato a due correzioni:

1. Finestra di conferma ridotta da 500 a 200 ms. A 300 ms il falso positivo
   a bordo campo scompariva dal frame annotato 195 ma ricompariva al 197:
   la revisione delle sole annotazioni originarie avrebbe nascosto il problema.
2. Recupero debole limitato a una dimensione della detection, invece di due.
   Il limite precedente permetteva un salto di circa 43 px dalla palla alla
   scarpa a 479.433 s, seguito da altri aggiornamenti sulla scarpa.

Questi casi sono conservati in `vision/fixtures/tracker-background-motion.json`
e `vision/fixtures/tracker-shoe-recovery.json` e coperti dai test del tracker.
I rettangoli negativi sono revisioni dei singoli candidati: non dichiarano
assenza di palla nell'intero fotogramma.

Risultato finale della variante (`full-minute-v4`): **91 → 158 accettazioni**,
68 aggiunte e una rimossa. Conteggi nelle finestre inclusive [-2,+3] secondi:

| Annotazione | Prima | Variante |
|---|---:|---:|
| 7:14 | 24 | 35 |
| 7:21 | 5 | 17 |
| 7:30 | 14 | 15 |
| 7:36 | 0 | 6 |
| 7:53 | 2 | 4 |

Esaminate le 69 differenze su ritagli contestuali e i casi ambigui su frame
completi. La variante scarta la scarpa introdotta dalla prima prova e rimuove
un precedente falso positivo a 464.067 s. Restano però **almeno sei nuove
accettazioni non-palla**: a 428.067 s e nel gruppo 445.767–445.867 s, oltre
al candidato sul bordo del frame a 451.067 s. Cinque ritagli sono rimasti
ambigui e non vengono contati come corretti. Annotazioni della revisione in
`storage/diagnostics/home-vs-away-shots/full-minute-v4/visual-review.json`.

Sul campione online originale di 22 frame, le metriche finali restano quelle
del tracker precedente: TP/FP/FN = 1/0/11 con tile ogni tre frame e 1/1/11
con tile ogni frame. I due punti aggiunti in ciascun video completo (frame
187 e 188) corrispondono visivamente alla palla in mano; non sono inclusi
nel campione annotato originale. Questi dati sono usati anche per scegliere
la variante e non costituiscono un test indipendente.

**Decisione: non attivare su localhost.** La condizione di assenza di nuove
regressioni nel campione non è soddisfatta. La modalità resta opzionale e
disattivata; nessun job, video, evento o statistica è stato modificato.
La sola coerenza temporale non distingue oggetti dello sfondo mossi dalla camera.
La prossima verifica deve aggiungere evidenza visiva/movimento della camera,
usando i negativi individuati, anziché rilassare ancora le soglie. Il risultato
non è una classificazione automatica dei cinque tiri o del loro esito.

Riproduzione del confronto (usare una cartella di output nuova):

```powershell
py -3.12 scripts/compare_ball_trackers.py storage/diagnostics/home-vs-away-shots/full-minute/custom.json --shots vision/fixtures/shot-review-home-vs-away.json --output-dir storage/diagnostics/home-vs-away-shots/comparison-review
```

`scripts/export_tracker_review.py` genera una pagina HTML e tavole di ritagli
da una cartella di confronto, usando OpenCV e il video originale. La revisione
finale è in `storage/diagnostics/home-vs-away-shots/full-minute-v4/review/index.html`.

### Evidenza del movimento della camera per la shot detection

Implementato `vision/camera_motion.py` e collegato al worker tramite
`BALL_CAMERA_MOTION_FILTER` (default `false`). La stima usa feature distribuite,
optical flow avanti/indietro e una trasformazione affine robusta. Richiede almeno
30 inlier, almeno metà delle corrispondenze valide e copertura spaziale;
frame senza texture, salti temporali e stime non affidabili non forniscono
evidenza. Sul minuto di Home vs Away sono valide 1779 stime su 1800 frame.
Questo conteggio non misura l'accuratezza geometrica delle trasformazioni.

Il tracker proietta le osservazioni recenti nella posizione prevista dal
movimento della camera e confronta il residuo con la dimensione della detection.
Una sequenza compatibile con lo sfondo viene marcata con:

- `sceneMotionState=background_consistent`;
- `shotMotionEligible=false`;
- `sceneResidualPx` e `sceneCameraShiftPx` per la revisione.

**La detection resta conservata.** Una prima prova che la scartava eliminava
anche vere palle ferme a bordo campo nel video online: movimento compatibile
con lo sfondo non significa oggetto diverso da una palla. Quella variante è
stata abbandonata. `shotMotionEligible=true` significa soltanto che questa
verifica non esclude il punto; non certifica né un tiro né una palla in gioco.

Il detector offline ignora i punti esclusi e non collega una terna attraverso
un intervallo esplicitamente escluso. Restano necessari la calibrazione del
ferro e i vincoli geometrici/temporali precedenti. La compensazione della
camera non implementa una calibrazione dinamica del ferro.

Risultato finale sul medesimo minuto, rispetto al tracker temporale v4:
158 detection conservate; due punti a 445.833 e 445.867 s, già revisionati come
falsi positivi sul pavimento, esclusi dall'evidenza di tiro. Nei cinque intervalli
annotati restano rispettivamente 35, 17, 15, 6 e 4 punti utilizzabili, gli stessi
della variante v4. Questi punti non sono cinque tiri automaticamente riconosciuti.
Gli altri quattro falsi positivi aggiunti noti non sono risolti da questo controllo.

Nei due profili online restano 28 e 52 detection, con le metriche sui 22 frame
annotati invariate rispetto alla v4. Rispettivamente 16 e 32 osservazioni vengono
marcate come incompatibili con il movimento di tiro, senza essere cancellate:
comprendono sia l'oggetto non-palla a bordo campo sia vere palle ferme.
I risultati finali sono nelle cartelle `camera-motion-final`,
`camera-online-baseline-final` e `camera-online-tiled-final` sotto
`storage/diagnostics/home-vs-away-shots`. Le cartelle `camera-filter-v1/v2` e
`camera-online-baseline/tiled` descrivono le prove precedenti, non la logica finale.

Le cronologie sono serializzabili nei checkpoint; dopo una ripresa il primo
frame senza trasformazione continua azzera l'evidenza di camera, senza scartare
detection. I campi aggiuntivi sono opzionali nel contratto frontend; il backend
continua a servire il JSON senza modifiche. Il Dockerfile include il nuovo modulo.

Verifiche: 18 test tracker (anche casi reali), 11 test shot detector e 4 test
della stima della camera. I casi reali, compresa una vera palla ferma da conservare,
sono in `vision/fixtures/camera-motion-review.json`. Verificati import completo
del worker nel suo ambiente Docker e configurazione Compose. Nessuna nuova
analisi o modifica al database; modalità sperimentali ancora disattivate e
nessun deploy effettuato, perché restano falsi positivi nel campione.

Per arricchire un report diagnostico di candidati senza rieseguire il modello,
in un ambiente Python con OpenCV e NumPy:

```powershell
python scripts/add_camera_motion.py storage/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4 storage/diagnostics/home-vs-away-shots/full-minute/custom.json storage/diagnostics/home-vs-away-shots/full-minute/camera-review-new.json
```

Poi confrontare con un output nuovo:

```powershell
py -3.12 scripts/compare_ball_trackers.py storage/diagnostics/home-vs-away-shots/full-minute/camera-motion-v2.json --camera-filter --shots vision/fixtures/shot-review-home-vs-away.json --output-dir storage/diagnostics/home-vs-away-shots/camera-comparison-new
```

I report originali non contengono automaticamente le nuove informazioni:
il replay le aggiunge a copie diagnostiche. Per usarle in un nuovo job occorrerà
costruire il nuovo worker e attivare esplicitamente il flag. Non è necessario
farlo per riprodurre i confronti offline già salvati.

Il modulo `vision/shot_detector.py` cerca **candidati tiro da verificare** nelle
traiettorie accettate di un report del worker. Non riconosce ancora tiri segnati o
sbagliati, non assegna squadre e non scrive eventi o statistiche nel database.
Non viene ancora eseguito automaticamente dal worker o dalla UI.

## Uso

Usare il JSON completo di un'analisi (`storage/analysis/<analysisId>.json`), non
il file `.request.json` né il report del benchmark `custom.json`.
Su un frame del video originale misurare il centro del **ferro**, non del tabellone,
e la sua larghezza in pixel. L'origine delle coordinate è in alto a sinistra.
Scegliere un intervallo analizzato in cui camera, zoom e posizione del ferro
restano fissi. Dopo un movimento della camera occorre una nuova calibrazione.

Esempio con coordinate **illustrative**, da sostituire con quelle del proprio video:

```powershell
py -3.12 scripts/diagnose_shots.py storage/analysis/ANALYSIS_ID.json --rim 500 200 40 --start 0 --end 20 --output storage/diagnostics/shot-candidates.json
```

Su Ubuntu usare `python3` al posto di `py -3.12`. Nessuna dipendenza esterna.
Il file di output deve essere nuovo: un report esistente non viene sovrascritto.
Le coordinate devono riferirsi alla risoluzione `video.width` / `video.height`
del report, non alle dimensioni del player nel browser.

Ogni candidato contiene timestamp assoluto nel video, intervallo, traccia,
tre punti di evidenza e motivo (`rising_rim_approach` o `descending_near_rim`).
`status=NeedsReview`, `teamId=null`, `outcome=null`: non sono eventi confermati.

## Regole e limiti

- Tre punti consecutivi della stessa traccia confermata; gap massimo 250 ms.
- Movimento verticale di almeno metà larghezza del ferro, prossimità al ferro,
  scarto dei salti di associazione e delle osservazioni duplicate allo stesso istante.
- Segnalazioni distanti meno di un secondo dall'ultima vengono raggruppate:
  può unire un tiro e un tap-in ravvicinati, da distinguere nella revisione.
- Soglie sperimentali: passaggi, rimbalzi, occlusioni e falsi tracking possono
  causare errori. Nessuna probabilità di tiro o percentuale di accuratezza stimata.
- Zero candidati **non significa zero tiri**. Il rilevatore vede solo le detection
  salvate, che possono essere poche o limitate da `MAX_BALL_POINTS`.
- I test sintetici verificano le regole; non dimostrano accuratezza sul basket reale.

## Verifica e passi successivi

```powershell
py -3.12 scripts/test_shot_detector.py
```

Prima dell'integrazione automatica: calibrare il ferro sul campione reale,
annotare gli intervalli dei tiri (le annotazioni della sola palla non bastano),
confrontare candidati con tiri veri e misurare falsi positivi e tiri mancati.
Poi aggiungere calibrazione visuale e timeline di revisione, mantenendo separati
candidati e statistiche confermate. L'esito segnato/sbagliato è uno sviluppo successivo.

## Primo riferimento reale: tiro tra 7 e 8 secondi

Annotazione utente conservata in `vision/fixtures/shot-review-720p.json`:
tiro sbagliato, contatto sul lato esterno del tabellone. Intervallo approssimativo;
il resto del video non è ancora annotato e non va considerato privo di tiri.

Il report locale `eca35d0d-32ae-4f49-ab71-ea1c4c59fbbd` contiene quattro punti
accettati a 7.867, 7.933, 8.000 e 8.067 secondi. Il controllo dei fotogrammi
105, 110, 118 e 125 mostra però un movimento della camera: il ferro non è visibile
nei primi due campioni e cambia posizione tra gli ultimi due. Una posizione fissa
del ferro non è quindi una calibrazione valida per questo evento.

Questo caso non è stato conteggiato come successo né come falso negativo del
rilevatore a camera fissa. Il passo tecnico necessario per supportarlo è una
posizione del ferro aggiornata nel tempo (prima tramite keyframe manuali,
poi eventualmente tramite tracking), con gestione degli intervalli fuori campo.
Le detection disponibili non dimostrano da sole né il tiro né il suo esito.
