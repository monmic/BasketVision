# Conservazione della geometria preaddestrata

Seguito del [protocollo congelato](PRESERVED_PROTOCOL.md). Ipotesi: ridurre
le regressioni fra sorgenti limitando l'adattamento ai soli output di classe.
Non vengono cambiate soglie CV, modelli operativi, eventi o statistiche nell'app.

## Diagnosi della prova precedente

Confrontato il detector espanso con un trasferimento a classe singola della
stessa YOLO26n originale. Nei livelli 0–9 tutti i parametri e i buffer sono
identici; nei livelli 10–22 cambiano 135 tensori di parametri e 90 buffer di
normalizzazione. Cambiano anche 27 tensori del ramo di regressione e 24 suoi
buffer. Il massimo scarto assoluto di questi buffer è 2,46875.

Questi valori dimostrano che la geometria e le feature potevano variare;
non dimostrano da soli quale componente abbia causato le palle perse. La nuova
prova elimina questa variabilità invece di compensarla modificando le soglie.

## Vincolo verificato

Addestrabili soltanto peso e bias degli ultimi sei classificatori convoluzionali:
tre scale per il ramo one-to-many e tre per il ramo one-to-one. Congelati tutti
gli altri moduli e tutte le statistiche BatchNorm, incluse quelle della testa.
Un callback del trainer verifica che l'elenco effettivo dei tensori addestrabili
sia quello previsto e che nessuna BatchNorm resti in training.

Test eseguito con loss di detection reale, backward e passo AdamW: soltanto
i tensori consentiti cambiano, nessun gradiente sugli altri parametri e nessuna
variazione dei buffer. Il trasferimento iniziale mantiene esattamente coordinate
e confidenze della baseline su tre riferimenti reali precedenti (Costa 779,
Costa 2697, 720p 45).

Gli stessi 75 campioni di training e 21 di validazione della prova espansa;
nessuna nuova annotazione, crop o frame di controllo aggiunto al training.
Inizializzazione originale, 15 epoche, input 640, batch 2, AdamW .001, seed
20261027, nessun warm-up o augmentazione, CPU Docker limitata a 2 core.
Il miglior checkpoint viene selezionato soltanto sulla validazione.

## Riproduzione

Riutilizzati training, benchmark e controllo di accettazione già presenti.
Montaggi come nel ciclo espanso: dossier in `/experiment`, YOLO26n originale
in `/model.pt`, rete disabilitata, `--cpus 2`,
`YOLO_CONFIG_DIR=/tmp/ultralytics`; dati/modelli sorgente in sola lettura.

1. `preserve_detector_geometry.py`: diagnosi dei tensori, elenco dei moduli da
   congelare e copia iniziale a classe singola in `detector-preserved/initial.pt`.
2. `test_preserved_detector.py`: due test ML effettivi nel container, senza
   download: passo di training e trasferimento dei tre riferimenti reali.
3. `train_detector_pilot.py --preserve-geometry`: usa il dataset espanso congelato
   e scrive soltanto in `detector-preserved/`; non riparte dal modello fallito.
4. `audit_preserved_detector.py`: confronta ogni tensore del checkpoint con
   l'inizializzazione e verifica che sei output densi della regressione, su input
   sintetico identico, restino esattamente uguali. La prova riguarda i box per
   posizione della griglia, non i box scelti dopo classificazione/ordinamento.
5. `benchmark_detector_pilot.py --preserve-geometry`: richiede l'audit prima
   dell'inferenza. Confronta baseline, vecchio pilot e variante `preserved`;
   gli stessi frame dei sette gruppi del benchmark espanso. Servono anche i
   montaggi `/scripts`, `/old-dataset`, `/old-annotations.json`,
   `/online-annotations.json` e `/online.mp4` descritti nel ciclo precedente.
6. `decide_expanded_detector.py --preserve-geometry`: stesso controllo per
   entrambe le confidence .02 e .12, IoU .5, perdite degli oggetti già trovati
   e regressioni per sorgente. Nessuna scelta di soglia sui controlli.

Tutti i frame di questi gruppi sono ormai controlli noti di sviluppo, compresi
i cinque frame valutabili a 180–230 s. I sei campioni 240–290 s, fissati nel
protocollo, si consumano soltanto se passa il controllo precedente. I dati
diagnostici, i pesi e i log restano esclusi da Git. Nessuna nuova dipendenza,
configurazione applicativa o migrazione.

## Training completato e conservazione effettiva

Durata **450,594 s** (7 min 31 s), escluso caricamento iniziale, inclusi training,
validazione e salvataggio. CPU Docker limitata a 2 core. Il tempo non descrive
un job di analisi video o le prestazioni attese sulla VM.

486 parametri addestrabili in 12 tensori di peso/bias; nel checkpoint 11 tensori
sono effettivamente cambiati e 697 restano identici. Nessuna modifica fuori
dall'elenco consentito, compresi tutti i buffer BatchNorm. Verificati anche i
sei output densi dei rami di regressione: identici a parità di input sintetico.

- Dataset SHA256:
  `b65c3544f2b5296211454f740ce0fdc766348a697950ac6ca1adb427a7381f98`.
- Checkpoint selezionato SHA256:
  `c7367539ec4e04e9f3d388a7cf924986364f357408114577b9e3d8f10095f0cd`.
- Inizializzazione a classe singola SHA256:
  `456a3a7128a02d01ff2e2b278135d29ee580e20e7bb89aee38541c1398e96143`.

## Controlli del detector

Metriche **TP / FP / FN**, IoU .5 uno a uno, stessi frame nativi a input 960.
I FP includono anche box di palle vere localizzati male. Le quattro sorgenti
di controllo sotto sono escluse dal training; sono già note nello sviluppo.

| Confidence | Controllo | Baseline | Soli classificatori |
| --- | --- | --- | --- |
| .02 | Costa 120–170 s | 1 / 11 / 3 | 1 / 19 / 3 |
| .02 | HVA shot-005 | 2 / 3 / 13 | 2 / 9 / 13 |
| .02 | 720p | 4 / 8 / 8 | 5 / 13 / 7 |
| .02 | Costa 180–230 s, 5 valutabili | 0 / 16 / 5 | 0 / 29 / 5 |
| .12 | Costa 120–170 s | 0 / 4 / 4 | 0 / 5 / 4 |
| .12 | HVA shot-005 | 1 / 0 / 14 | 1 / 0 / 14 |
| .12 | 720p | 3 / 2 / 9 | 5 / 3 / 7 |
| .12 | Costa 180–230 s | 0 / 4 / 5 | 0 / 7 / 5 |

**Nessun oggetto della baseline perso** a entrambe le confidence, nei quattro
controlli. Risolta questa regressione campionaria della prova espansa, ma non
il problema dei falsi: 70 contro 38 a .02, 15 contro 10 a .12. Il detector
standalone è respinto dal controllo fissato prima della prova.

## Selezione dei punteggi soltanto sulla validazione

Valutata una trasformazione monotona dei punteggi senza altri training o ritocchi
dei pesi. Sui soli 21 frame di validazione, enumerati i confini dei punteggi;
richiesti conservazione di ogni oggetto baseline, nessuna regressione FP/FN per
sorgente e meno FP totali. Scelta poi congelata prima di applicarla ai controlli:

- soglia grezza debole: **.09283159673213959**, riportata a .02;
- soglia grezza forte: **.46353983879089355**, riportata a .12.

Interpolazione lineare monotona fra (0,0), questi due punti e (1,1). Non sono
probabilità calibrate. La selezione sulla validazione riduce i FP deboli da 15
a 7 e i forti da 4 a 2 conservando i relativi oggetti baseline.

Sui controlli, però, la trasformazione perde due palle deboli: Costa frame 3596
e HVA frame 14184. Anche questa modalità è respinta. Non si cambia la soglia
sui controlli per recuperarle. La ricerca dei punteggi è riproducibile in
`check_preserved_operating_points.py`; `selection.json` viene scritto prima
della valutazione dei controlli. Questi ultimi restano dati noti, non un test cieco.

## Uso limitato all'evidenza forte

Provata separatamente una possibilità più stretta: mantenere tutto il flusso
debole della baseline e usare il nuovo classificatore soltanto come requisito
per iniziare/confermare tracce. Una proposta baseline forte (confidence ≥ .12)
deve avere un box del classificatore sopra la soglia forte scelta sulla
validazione, con IoU ≥ .5. Nessuna nuova proposta generata per il tracker.

Nei controlli campionati, i quattro oggetti forti baseline restano presenti;
i falsi forti passano da 10 a 6 (Costa 4→2, HVA 0→0, 720p 2→1, Costa
successivo 4→3). Questo controllo di fattibilità passa; i due modi standalone
precedenti restano respinti. Serve il replay temporale, perché conservare
un oggetto nel singolo frame non garantisce la conferma della sua traccia.

Il punteggio ausiliario usa le feature del solo predictor palla isolato, senza
un secondo passaggio CNN e senza toccare il predictor persone. Verificata
l'equivalenza con il modello separato su frame intero, ritaglio senza proposte
e ritaglio con proposte; box/confidenze entro 1e-4 pixel/1e-6 di tolleranza.
Le uscite originali della baseline restano identiche e gli hook vengono rimossi.
Il predictor effettivo usa il ramo NMS/one-to-many: lo strumento si collega al
modello fuso attivo di AutoBackend e mantiene lo stesso NMS del detector.

Test: `test_preserved_score_hook.py`. Replay isolato:
`benchmark_preserved_tracking.py`, seguito da `evaluate_preserved_tracking.py`.
Usano il worker montato in `/app`, gli script in `/scripts` e il video Costa in
`/video.mp4`, in sola lettura. Prima rigenerare la copia AST con
`prepare_tracker_prototype.py`; il file `vision/worker.py` operativo non cambia.

## Replay continuo: regressione rilevata

Elaborati tutti i **1798 frame nativi da 60 a 120 s**, con timestamp assoluti,
stesso passaggio full-frame/tiled e due tracker indipendenti. Confrontate tutte
le proposte raw con la baseline del ciclo precedente: geometria, confidence,
quality score e sorgente coincidono per ogni frame. Il tracker baseline riproduce
anche le stesse 1344 osservazioni accettate. Il controllo cambia soltanto
l'idoneità dei colpi forti, non elimina le proposte deboli dal flusso.

| Verifica | Baseline | Con evidenza forte ausiliaria |
| --- | ---: | ---: |
| Box accettati complessivi, identità non tutte revisionate | 1344 | 586 |
| Osservazioni palla baseline già verificate | 68 | 53 conservate |
| Osservazioni non-palla note nel sottoinsieme revisionato | 64 | 8 conservate |
| Nei riferimenti fissi: palla | 4 | 3 |
| Nei riferimenti fissi: non-palla | 23 | 8 |
| Nei riferimenti fissi: incerto | 1 | 0 |

**15 osservazioni palla vere perse**: frame 2338, 3129–3139 e 3538–3540.
Non sono 15 palle distinte o 15 eventi. Sei osservazioni accettate soltanto
dal nuovo tracker non hanno revisione di identità completa; non sono conteggiate
come veri positivi. Il sottoinsieme noto non è un'annotazione esaustiva dei
1798 frame, quindi non si dichiarano recall globale o accuratezza dei conteggi.

Nei record di rigetto delle 15 perdite, 11 sono bloccate all'avvio come evidenza
debole e 4 restano in tracce tentative non confermate. Il problema è quindi
visibile anche nello stato temporale, non soltanto nella soglia del report.

La riduzione dei falsi campionati non compensa le perdite di palle, incluse
osservazioni in volo. Il passaggio dei controlli statici sull'evidenza forte
non si trasferisce alla conferma/continuità temporale. **Anche questo prototipo
è respinto**; nessun ritocco della soglia o del numero di hit per adattarlo
alle traiettorie appena osservate. I campioni 240–290 s restano non consumati.

Tempi del replay accoppiato, CPU Docker quota 2:

- totale: 300,404 s, caricamento/warm-up esclusi;
- full-frame 176,438 s, tiled 115,462 s, decodifica 8,089 s;
- associazione evidenza 0,016 s e aggiornamento dei due tracker 0,294 s;
- calcolo ausiliario e trasformazione box 4,586 s, **già inclusi** nei tempi
  del detector, non da sommare nuovamente.

Un solo passaggio CNN e due tracker: questi sono tempi diagnostici accoppiati,
non due benchmark indipendenti di job completi né una previsione della VM.
Il costo ausiliario è misurato, ma non si afferma un'accelerazione operativa.

## Esito della coda e validazione

Completati diagnosi, test di conservazione, training, audit del checkpoint,
controlli raw, selezione dei punteggi sulla validazione, controllo forte e replay
temporale. L'esito finale resta **nessun rilascio**. Il vincolo di conservazione
del detector ha eliminato la perdita di oggetti nei campioni statici; la
discriminazione dei falsi e la conferma temporale restano insufficienti.
Non è necessario un intervento dell'utente per sbloccare questa verifica.

37 test mirati passati nel ciclo: 2 ML di conservazione, 1 di equivalenza hook,
4 dei punteggi, 3 valutazione, 4 decisione, 5 contratti dell'evidenza semantica,
18 tracker. Ricostruite le metriche dei sette gruppi con
`audit_preserved_controls.py`; verificati hash, split e tutti i 117 campioni
esportati tramite l'audit del dataset precedente. Sintassi Python e whitespace
verificati. Risultati e pesi restano esclusi da Git.

Nessuna modifica a worker operativo, API, frontend, configurazione applicativa
o database; nessuna migrazione o dipendenza aggiunta. Il lavoro successivo dovrà
affrontare l'evidenza temporale senza perdere palle reali; non basta promuovere
il nuovo classificatore o ridurre i conteggi delle tracce.
