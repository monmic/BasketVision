# Roadmap attiva: riconoscimento automatico

Il percorso richiesto è **video → riconoscimento → eventi proposti → report**.
L'utente non deve individuare e classificare manualmente ogni tiro.
La revisione manuale precedente resta disponibile come verifica facoltativa.

## Ultimo avanzamento

[Esperimento completo e riproduzione](../artifacts/automatic-recognition-20261026/README.md).

- Due nuovi modelli confrontati sui riferimenti esistenti.
- Ritaglio guidato dal detector del canestro, senza calibrazione manuale, provato
  su 690 frame: 124 osservazioni palla verificate contro 42 della baseline,
  conservando tutti i frame palla precedenti ma aggiungendo 67 box falsi.
- Un candidato tiro recuperato con geometria del ferro revisionata, soltanto
  per valutare le traiettorie. Nessun riconoscimento automatico degli esiti.
- Varianti di associazione/temporali controllate e non promosse per regressioni.
- 329 esempi semantici verificati preparati; nessun training o test cieco inventato.
- Analisi CV riportata in primo piano nell'interfaccia locale; inserimento
  manuale raccolto in sezioni chiuse. Funzionalità sperimentali dichiarate tali.

La coda di questa prova è completata. Il prodotto non è ancora pronto per
riconoscere in modo affidabile tiri, segnato/sbagliato e squadre.

## Prossimo ciclo

Il nuovo video **Costa vs Roseto** è stato ricevuto e usato nel ciclo del
27 ottobre: [prova, risultati e riproduzione](../artifacts/costa-roseto-20261027/README.md).
La dipendenza dal caricamento di una nuova sorgente è risolta.

Completati verifica del modello congelato sui dati precedenti, contesto canestro,
adattamento sul primo minuto e controllo sul secondo, controllo di regressione
720p e confronto continuo su 1798 frame. Il verificatore adattato mantiene
soltanto 2 delle 9 proposte palla revisionate nel campione del secondo minuto.
Il prototipo di tracking conserva 65 osservazioni palla ma anche 41 falsi;
nei riferimenti fissi perde 3 delle 4 osservazioni palla della baseline.
Nessuna variante è stata promossa nel worker operativo.

La coda sperimentale del verificatore è esaurita. I risultati non rendono ancora
affidabili tiri, esiti o squadre. I 409 ritagli semantici verificati sono utili
al filtro ma non costituiscono un dataset di detection completo: le annotazioni
per frame sono state preparate nel pilot successivo descritto sotto.
Il tratto da 120 secondi alla fine era escluso dal ciclo del verificatore;
il pilot usa poi i campioni 120–170 s. Nessuna annotazione manuale dei tiri
è richiesta all'utente per usare il prodotto.

Poi: discriminazione palla/sfondo/scarpe/teste, verifica automatica del contesto
canestro, traiettorie ed eventi. I risultati non vanno promossi sulla sola
crescita dei conteggi o sui campioni usati durante lo sviluppo.

## Pilot detector completato

[Dataset, training e risultati](../artifacts/costa-roseto-20261027/DETECTOR_RESULTS.md).
Preparati 22 frame con annotazioni della palla attiva, 5 casi ambigui esclusi.
Eseguiti training CPU, diagnosi e singola ripetizione senza il warm-up dei bias,
poi composizione con il verificatore congelato. Nuovo tratto Costa 120–170 s
controllato inizialmente fuori dal training; dopo la prima prova rimane un
controllo noto di sviluppo per le varianti successive. Nessun uso nel training.

Il detector senza warm-up recupera 2 box corretti contro 1 della baseline su
questo campione, ma aumenta i FP da 11 a 113 a confidence .02 e IoU .5.
La composizione semantica perde tutte le palle del campione. Nessuna integrazione.
Completata la coda del pilot; il limite per un ciclo successivo è ampliare i dati
di training, soprattutto negativi verificati di gioco e sorgenti diverse.
Non servono annotazioni dei tiri da parte dell'utente nell'app.

## Dataset ampliato: ciclo completato

[Dati, training e confronti](../artifacts/costa-roseto-20261027/EXPANDED_RESULTS.md).
Risolta la mancanza di negativi di gioco nel pilot: 75 immagini di training,
49 box palla, 23 ritagli negativi verificati da Costa e Home vs Away; 21 frame
di validazione distinti. Conservati i controlli precedenti e aggiunti sei
campioni successivi Costa a 180–230 s, di cui cinque valutabili e uno ambiguo.

Training CPU completato in 866 s. Nei quattro controlli esclusi dal training,
a confidence .02 i FP calano da 341 del pilot a 177, ma la baseline ne fa 38.
Il modello perde quattro oggetti prima riconosciuti; sul 720p passa da 4 TP
della baseline a 1. La variante non supera il controllo fissato prima della
prova. Nessuna promozione o replay continuo di un modello già in regressione.

La coda di questo ciclo è esaurita: export e verifica dei dati, training,
confronto sui controlli, controllo successivo e decisione completati. Il limite
resta riconoscere/localizzare la palla e preservare qualità fra sorgenti, non
soltanto aggiungere negativi. Nessuna richiesta di annotazione dei tiri all'utente.

## Conservazione del detector e controllo temporale: ciclo completato

[Prove e risultati](../artifacts/costa-roseto-20261027/PRESERVED_RESULTS.md).
Addestrati soltanto i 486 parametri finali di classificazione sul dataset
precedente. Verificata la conservazione di tutti gli altri pesi/buffer e degli
output densi della regressione. Nei controlli statici non si perdono più oggetti
baseline, ma aumentano i falsi; la selezione dei punteggi sulla validazione
riduce i falsi e perde due palle deboli nei controlli, quindi non è promossa.

Il controllo più stretto sui soli colpi forti conserva le quattro palle forti
campionate e riduce i falsi da 10 a 6. Provato poi su tutti i 1798 frame di
Costa 60–120 s, mantenendo identico il flusso di proposte e riusando le feature
del predictor palla isolato, senza secondo passaggio CNN. Il replay conserva
53 delle 68 osservazioni palla note e ne perde 15: prototipo respinto.

Completata la coda di questo ciclo, incluse le verifiche indipendenti dei dati,
l'audit del modello e il controllo temporale. Le accettazioni 1344→586 non sono
un miglioramento sufficiente: eliminano anche palle reali. L'ultimo tratto
240–290 s resta escluso dalla prova. Nessun rilascio o modifica ai job nell'app.

## Recupero tramite continuità: prova mirata completata

[Protocollo e risultati](../artifacts/costa-roseto-20261027/MOTION_RESULTS.md).
Ricostruite le 15 osservazioni perse e i dintorni delle rispettive tracce:
11 rigetti all'avvio, quattro alla conferma. Replay causale sui medesimi
1798 frame con sostegno da una traccia baseline continua e in movimento,
usando soltanto criteri statici già presenti, senza ottimizzazione di soglie.
Il recupero conserva 54 palle note contro 53 del filtro, ma riapre 20 falsi
(28 contro 8). Variante respinta; 28 test passati. La continuità da sola
non risolve il riconoscimento visivo. Coda mirata completata: il controllo
240–290 s rimane subordinato a una variante che superi prima questi controlli.
Nessuna modifica al prodotto, configurazione o migrazione.

## Disposizione delle feature: ciclo completato il 28 ottobre

[Risultati e audit](../artifacts/costa-roseto-20261027/SPATIAL_RESULTS.md).
Conservare quattro zone delle feature, anziché la sola media, migliora il
verificatore a parità di 409 crop, backbone e soglia: sulle 97 proposte mantiene
3 palle su 9 (prima 2) e 7 falsi (prima 9); sulle identità note mantiene 46
palle su 68 (prima 38) e 18 falsi (prima 23). Controlli sovrapposti, non sommabili.
Perde ancora palle reali e non viene integrato. Audit dei dati e dieci test
passati. I crop palla misurano solo 10–19 pixel sul lato corto nel campione di
proposte: l'ingrandimento non ricrea dettaglio. Coda del confronto completata,
nessun uso del tratto 240–290 s o modifica alla configurazione operativa.

## Dettaglio e contesto sui video disponibili: ciclo completato

[Dataset e risultati](../artifacts/costa-roseto-20261027/CONTEXT_RESULTS.md).
Esportati 457 esempi unici con due viste (409 precedenti più 48 positivi,
un duplicato dei 49 box eliminato), senza usare val/test del detector.
Confrontati fit sul solo dettaglio e dettaglio più contesto triplo, con due
fold che escludono una partita intera e controlli Costa 60–120 s separati.
Il contesto conserva 45 palle su 68 contro 49 del dettaglio e peggiora anche
nei fold per partita: non promosso. Audit di 914 crop e 11 test passati.
Coda della prova completata, dati riutilizzabili, nessun nuovo video richiesto.
240–290 s rimane riservato; nessuna modifica operativa o migrazione.

## Annotazioni e pesi riequilibrati: ciclo completato

[Protocollo, dati e confronto](../artifacts/costa-roseto-20261027/BALANCED_RESULTS.md).
Dodici nuovi frame del primo minuto ispezionati: otto palle annotate,
tre incerti esclusi e una schermata di testo. Pool ampliato a 465 esempi;
riduzione deterministica delle ripetizioni a 180, con 104 train, 72 validazione
e quattro nella guardia. Validazione per sequenza separata prima del fit,
con estensione Costa a 44–60 s dopo l'ispezione dei tagli.
Il fit con pesi uguali per sorgente/classe conserva 57 palle note su 68 contro
54 del riferimento, ma aumenta i falsi sulle 97 proposte da 25 a 28.
Non passa il criterio prefissato. 12 test e audit indipendente passati.
Coda completata senza replay continuo o uso di 240–290 s; nessuna integrazione,
configurazione o migrazione. Nessun nuovo video richiesto.

## Adattamento dell'ultimo blocco visivo: ciclo completato il 29 ottobre

[Protocollo, training e audit](../artifacts/costa-roseto-20261027/ADAPTER_RESULTS.md).
Stessi 104 esempi train e 72 validazione. Addestrati soltanto C2PSA e head,
con blocchi precedenti e tutti i buffer congelati. Dieci epoche prefissate;
checkpoint scelto alla prima epoca dalla sola BCE di validazione, prima dei
controlli. Il riferimento congelato mantiene 57 palle note su 68, l'adattato
54: la riduzione di alcuni falsi non compensa la regressione.
Otto test passati; audit sul checkpoint ricaricato verifica tutti i 244
tensori e riproduce gli score di validazione e controlli. Variante respinta,
coda completata, nessun replay continuo, uso di 240–290 s o modifica operativa.
