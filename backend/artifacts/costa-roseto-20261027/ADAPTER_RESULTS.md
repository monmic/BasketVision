# Adattamento visivo limitato: ciclo completato, variante respinta

29 ottobre 2026. [Protocollo](ADAPTER_PROTOCOL.md) fissato prima del training.
La prova cambia le feature dell'ultimo blocco visivo, mentre i cicli precedenti
addestravano il classificatore su feature congelate. Nessuna modifica al
detector, al tracker operativo o alla configurazione dell'app.

## Dati e training

Stessi 104 esempi train, 72 validazione e quattro esempi nella guardia del
dataset riequilibrato. Nessun nuovo campione, etichetta o split. Preprocessing
128, pooling 2×2 e normalizzazione delle feature invariati. Inizializzazione
dal classificatore riequilibrato del ciclo precedente; soglia .5 invariata.

Addestrati C2PSA (blocco10) e head: 250753 parametri. Blocchi0–9 e tutti i
buffer BatchNorm congelati. AdamW, dieci epoche prefissate, LR blocco1e-5,
head1e-4, weight_decay0, BCE pesata per sorgente/classe e L2 .01 della head,
clip norma1, batch16, seed20261029. Cache del prefisso congelato per ridurre
il calcolo. Nessuna augmentation o ricerca di iperparametri.

Selezionata epoca1 su minima BCE pesata della sola validazione, includendo
epoca0 nel confronto: 0,67072 contro 0,69033 iniziale. Le epoche successive
peggiorano questa misura e non vengono selezionate. Checkpoint congelato prima
di caricare i controlli. La riduzione della BCE non è un miglioramento
sufficiente del riconoscimento: i conteggi della validazione restano uguali.

## Controlli del checkpoint congelato

| Controllo | Modello | Palle conservate/perse | Falsi conservati/respinti |
|---|---|---:|---:|
| Validazione Home vs Away | Riferimento e adattato | 16 / 0 | 12 / 10 |
| Validazione Costa | Riferimento e adattato | 5 / 1 | 3 / 25 |
| 97 proposte Costa | Riferimento | 4 / 5 | 28 / 60 |
| Stesse proposte | Adattato | 4 / 5 | 26 / 62 |
| 133 identità Costa, una incerta esclusa | Riferimento | 57 / 11 | 40 / 24 |
| Stesse identità | Adattato | 54 / 14 | 39 / 25 |

Controlli di sviluppo noti e sovrapposti; non si sommano e non sono recall
esaustiva o prova su nuove partite. Il criterio prefissato fallisce: diminuiscono
alcuni falsi ma si perdono tre ulteriori osservazioni palla note. Nessun
ritocco successivo di soglia o epoca per migliorare questi controlli.

## Verifiche e costo

Otto test passati: inizializzazione equivalente al classificatore precedente,
backward/step sui soli parametri autorizzati con buffer invariati, cache del
prefisso equivalente al forward completo, ripristino, contratti del dataset
riequilibrato e dei suoi criteri di ammissione.

Audit indipendente sul checkpoint ricaricato: 244 tensori controllati,
23 modificati soltanto in blocco10/head; prefisso e 122 buffer invariati.
Verificati hash del dataset e del classificatore iniziale, indici del train
separati dalla validazione, selezione dell'epoca minima, BCE ricalcolata e
score ricalcolati di tutti i 72 esempi di validazione e dei due controlli.
Le decisioni del riferimento sui controlli riproducono il ciclo precedente.

Checkpoint SHA256:
`086dd1f5b389b93ddcd2eded5bcf3b4448183d3c84e48de2dd7be3a4481285fb`.

Docker senza rete, due core CPU. Cache del prefisso train/val e dieci epoche:
5,40 s, esclusi caricamento iniziale dei crop, modello e controlli. Il campo
`pairedScoreSeconds` dei controlli include estrazione/decodifica dei frame,
preprocessing e score dei due classificatori: 2,54 s per 97 crop e 8,47 s per
133. Questi tempi non sono direttamente confrontabili con i soli tempi delle
feature riportati nei cicli precedenti. Sono esclusi detector, tracker e job
completo: nessuna affermazione sul tempo del prodotto.

## Chiusura della coda

Completati contratti, training limitato, audit dei pesi, confronto e decisione.
Nessuna promozione, replay continuo o uso di 240–290 s: tali passi erano
condizionati al passaggio dei controlli. Nessuna dipendenza, migrazione o
configurazione aggiunta; pesi/report/immagini generati ignorati da Git.
Il riconoscimento robusto della palla resta aperto. L'adattamento limitato
provato non giustifica l'avanzamento a tiri/esiti o statistiche automatiche.
