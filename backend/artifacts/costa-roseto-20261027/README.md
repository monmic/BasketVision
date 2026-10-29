# Costa vs Roseto: verifica del riconoscimento automatico, 27 ottobre 2026

29 ottobre: [adattamento dell'ultimo blocco visivo](ADAPTER_RESULTS.md) completato.
Training controllato e audit del checkpoint confermano una regressione sulle
palle note; nessuna integrazione nell'app. Le prove seguenti sono lo storico.

Ultimo ciclo: [annotazioni e pesi riequilibrati](BALANCED_RESULTS.md).
Otto nuovi box, ripetizioni ridotte, validazione per sequenza separata e
confronto congelato: variante respinta, nessuna modifica al worker operativo.

Ultima prova: [dettaglio + contesto con i video esistenti](CONTEXT_RESULTS.md).
457 esempi unici esportati in due viste; il classificatore con contesto
non supera i controlli. Dataset pronto per riuso, nessuna modifica al worker.

Aggiornamento 28 ottobre: completati il [recupero tramite movimento](MOTION_RESULTS.md)
e il [verificatore con feature spaziali](SPATIAL_RESULTS.md). Quest'ultimo
migliora entrambi i controlli visivi ma perde ancora palle reali; nessuna
integrazione nel worker. I cicli seguenti sono conservati come storico.

**Ciclo più recente:** [conservazione della geometria e prova temporale](PRESERVED_RESULTS.md).
Il training dei soli classificatori conserva i box e gli oggetti dei controlli
statici. Il filtro forte provato nel replay perde però 15 delle 68 osservazioni
palla già verificate: anche questa variante resta fuori dal worker operativo.

**Ultimo ciclo:** [dataset ampliato e negativi di gioco](EXPANDED_RESULTS.md).
75 immagini di training da due sorgenti, 23 ritagli negativi verificati,
confronto di tre modelli e sei nuovi campioni temporali. Anche questa variante
è respinta per regressioni e palle perse; il worker operativo resta invariato.

**Aggiornamento:** completato anche il [pilot di training del detector](DETECTOR_RESULTS.md)
con annotazioni complete per 22 frame, due run CPU e controlli su tre video.
I risultati restano insufficienti per l'integrazione. Le sezioni seguenti
documentano il ciclo precedente del verificatore semantico.

Esperimenti isolati sul nuovo caricamento. Nessuna modifica al worker operativo,
ai risultati nel database o alle statistiche dell'utente. Nessuna annotazione
richiesta all'utente. I file generati e i pesi sono esclusi da Git.

## Sorgente e separazione dei dati

- Game: `ad0b3783-9ef0-49b9-8645-a8fac9540389`.
- Video locale: durata 291,307 s, 854×480, 29,970027 fps, 8730 frame.
- SHA256: `5b71235ed085ed2a3547262e56886e7fcd56353f8436bce9be035f6551ec40d8`.
- Il video è un montaggio con introduzione, scritte sovrapposte e tagli di gioco.
  Non si possono assumere possesso o traiettorie continui attraverso i tagli.
- Prima prova: modello congelato sui 329 ritagli Home vs Away precedenti;
  controllo fuori sorgente a 0,2,…,58 secondi. Vedi [protocollo](PROTOCOL.md).
- Seconda prova: dopo il primo controllo, aggiunti 80 ritagli revisionati del
  primo minuto (5 proposte palla, 75 negative). Congelati 409 esempi e modello
  prima di esaminare 60,62,…,118 secondi. Vedi [protocollo](ADAPTATION_PROTOCOL.md).
  È una separazione temporale sulla stessa sorgente; il montaggio può ripetere
  azioni. Non è un secondo test indipendente fuori sorgente.
- La parte da 120 secondi alla fine non è stata usata in questo ciclo.

## Risultati delle proposte campionate

Identità delle singole proposte controllata visivamente, anche sui frame nativi.
Non sono annotazioni esaustive: questi numeri non misurano recall globale,
accuratezza degli eventi o precisione geometrica IoU.

| Prova | Proposte palla mantenute / presenti | False proposte mantenute / presenti |
| --- | ---: | ---: |
| Verificatore originale, primo minuto | 2 / 3 | 19 / 61 |
| Verificatore adattato, secondo minuto | 2 / 9 | 9 / 88 |
| Detector specializzato in ROI canestro, primo minuto | 2 / 3 della baseline | 14 false aggiunte |

Le 9 proposte palla del secondo minuto corrispondono a 8 frame: due box
descrivono la stessa palla sfocata. Il verificatore riduce lo sfondo ma perde
troppe palle; non viene integrato come filtro rigido.

Il detector del canestro trova correttamente il contesto in tutti i 23 frame
di gioco campionati nel primo minuto e non supera la soglia 0,25 nei 7 frame
di introduzione. È una verifica campionaria del box del canestro, non la
calibrazione del piano del ferro necessaria per determinare segnato/sbagliato.
Il ritaglio automatico non recupera nuovi frame palla rispetto alla baseline
su questa sorgente. Il profilo rimane quello precedente, senza nuove soglie.

Sul precedente controllo 720p di 22 frame, valutato con IoU 0,5 e abbinamento
uno a uno, baseline TP/FP/FN = 4/8/8; verificatore originale 4/3/8;
adattato 4/2/8. Controllo conservato senza training, ma già noto nello sviluppo:
non sostituisce il risultato negativo sui dati nuovi.

## Prova continua del tracker, da 60 a 120 secondi

1798 frame nativi, stesse proposte full-frame/tiled, stessi parametri e due
tracker separati. Nel prototipo, evidenza semantica negativa impedisce nascita
e conferma di nuove tracce, ma può aggiornare una traccia già confermata con
il limite esistente degli aggiornamenti deboli. Nessuna soglia CV modificata.

- Baseline: 1344 box accettati. Prototipo: 106. Il conteggio non misura qualità.
- Revisionati **tutti i 106** box del prototipo: **65 palla, 41 falsi**, fra cui
  lettere rosse delle scritte. Sono osservazioni ripetute, non 65 palle o eventi.
- Nei 30 frame di riferimento prestabiliti, baseline: 4 box palla, 23 falsi,
  1 incerto. Prototipo: 1 palla. Si perdono 3 osservazioni palla corrette.
- Decisione: anche questo prototipo è respinto. Nessun rilascio operativo.

Revisione riproducibile: `review_track_gate.py` genera 4 tavole e un manifest;
`record_track_review.py` registra le identità senza derivare le etichette dai
punteggi del classificatore. L'osservazione incerta resta esplicita.

## Risorse e provenienza

CPU limitata a 2 core Docker, rete disabilitata, video/modelli montati in sola
lettura. Il tempo totale del confronto continuo è 307,672 s, esclusi caricamento
modelli e warm-up: full-frame 170,979 s, tiled 111,362 s, verificatore 23,426 s,
decodifica 1,438 s, tracking 0,302 s. Detector condiviso fra due tracker, senza
pipeline persone: non sono tempi di un job completo né previsioni per la VM.

Backbone congelato YOLO26n, prime 11 sezioni, media spaziale delle feature,
ritagli letterbox RGB 128. Regressione logistica L2 0,01, soglia fissa 0,5;
punteggi non calibrati. Cross-validation per episodio completo, senza dividere
i ritagli Costa del primo minuto fra train e validation dello stesso fold.

- Classificatore originale SHA256:
  `f354cac27250c4df3e0f0119f72dad7d8df5c3381f295e2a2e066076f5f35473`.
- Classificatore adattato effettivamente valutato:
  `4c0fdcb8d8fbb7190942ef2b5d2e3cdaf83046b8d29e80ec75e97d57178364ff`.
- La prima serializzazione adattata conteneva una nota ereditata errata sulle
  sorgenti: corretta e rigenerata prima di ogni valutazione adattata; fit numerico
  invariato. Usare soltanto `adapted-training-corrected/classifier.json`.
- Detector canestro/palla Attalla e dipendenza dill: stessi hash/profilo della
  [prova precedente](../automatic-recognition-20261026/README.md).
- Un peso MobileNet scaricato per esplorazione non è stato usato né valutato.

## Riproduzione e verifiche

Gli script ML richiedono l'immagine worker esistente (torch, OpenCV, Ultralytics),
non nuove dipendenze nel servizio. Usare output nuovi: vari script rifiutano di
sovrascrivere risultati già esistenti. Montaggi convenzionali: questo dossier
in `/experiment`, video in `/video.mp4`, YOLO26n in `/model.pt`, vecchi 329
esempi in `/examples`, worker in `/app`, script repository in `/scripts`.
Il benchmark continuo importa `worker` da `/app`; attivare `VISION_CPU_THREADS=2`
e impostare `YOLO_MODEL` e `BALL_MODEL` a `/model.pt` per usare i pesi locali.

1. `semantic_verifier.py WEIGHTS EXAMPLES OUTPUT`: training e CV per episodio.
2. `benchmark_source.py VIDEO WEIGHTS CLASSIFIER OUTPUT [--start 60]`:
   30 riferimenti e proposte full-frame con punteggi congelati.
3. `prepare_candidate_review.py`, `record_review.py`, `benchmark_context.py`:
   controllo prima prova; `prepare_adaptation.py` prepara il secondo dataset.
4. `prepare_candidate_review.py --adapted` e `record_adapted_review.py`:
   controllo seconda prova; `check_previous_control.py`: controllo regressioni.
5. Sul filesystem repository, `prepare_tracker_prototype.py` genera una copia
   isolata del worker. Poi nel container `benchmark_track_gate.py`,
   `review_track_gate.py` e `record_track_review.py`. Il worker reale non cambia.
6. `verify_artifacts.py`: hash di tutti i 409 ritagli, bounds, split, modello.

Validazioni: 4 test del verificatore nel container, 5 contratti del prototipo,
18 test tracker tramite replay AST e 4 test tracker del worker, tutti passati.
Controllati sintassi degli script, hash/split dei dati e whitespace del diff.
Nessuna migrazione o modifica di configurazione operativa.

## Esito del ciclo

Completati training congelato, controllo fuori sorgente, adattamento con holdout,
contesto canestro, controllo precedente e replay continuo. Nessuna variante
supera i controlli per l'integrazione. Il limite successivo è la qualità del
detector palla e la discriminazione delle scritte; non si risolve moltiplicando
i conteggi del tracker o affidando all'utente la classificazione dei tiri.
Un ulteriore ciclo di addestramento del detector richiede un dataset di frame
annotati esaustivamente: i ritagli di proposte qui raccolti non sono quel dataset.
