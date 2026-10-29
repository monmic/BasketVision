# Dettaglio + contesto: ciclo completato con i video esistenti

28 ottobre 2026. [Protocollo](CONTEXT_PROTOCOL.md) fissato prima della prova.
Nessun nuovo video o intervento manuale richiesto all'utente.

## Dataset verificato

409 proposte revisionate più 49 box positivi dei soli full-frame train del
dataset ampliato. Un box coincide con una proposta esistente: 48 esempi nuovi,
**457 identità uniche**. Home vs Away: 369 esempi (211 palle, 158 negativi).
Costa: 88 (13 palle, 75 negativi), tutti prima di 60 s. Nessun val/test del
detector trasferito nel training. I negativi si riferiscono al centro proposto,
non all'assenza di qualsiasi palla nell'intero contesto.

Esportate due viste per esempio, 914 PNG ignorati da Git: dettaglio e contesto
triplo ritagliato ai bordi. I 409 dettagli coincidono pixel per pixel con i
crop precedenti. Verificati hash dei video, manifest, full-frame train e crop.
Il dataset resta riutilizzabile anche se questo classificatore fallisce.

Manifest: `e03ca068e3d38a01d3315bccc473808c78ec0b739dada5ee06a34ab5c0215547`.

## Confronto sugli stessi dati ampliati

Backbone congelato, preprocessing 128, pooling 2×2, L2 .01 e soglia .5.
Dettaglio: 1024 feature; dettaglio + contesto: 2048. Entrambi i fit finali
congelati prima di leggere i controlli. Nessuna scelta di parametri sui risultati.

| Controllo | Metodo | Palle conservate/perse | Falsi conservati/respinti |
|---|---|---:|---:|
| 97 proposte Costa | Dettaglio | 4 / 5 | 12 / 76 |
| Stesse proposte | Dettaglio + contesto | 4 / 5 | 10 / 78 |
| 133 identità Costa, una incerta esclusa | Dettaglio | 49 / 19 | 37 / 27 |
| Stesse identità | Dettaglio + contesto | 45 / 23 | 37 / 27 |

Controlli noti di sviluppo e sovrapposti, non sommabili né recall esaustiva.
Il dettaglio sui dati ampliati mantiene più palle rispetto al ciclo precedente,
ma anche più falsi: non dimostra ancora un miglioramento utile nel prodotto.

## Verifica escludendo un'intera partita dal fit

| Partita esclusa | Metodo | Palle conservate/perse | Falsi conservati/respinti |
|---|---|---:|---:|
| Home vs Away (fit sui soli 88 Costa) | Dettaglio | 48 / 163 | 12 / 146 |
| Home vs Away | Dettaglio + contesto | 46 / 165 | 4 / 154 |
| Costa (fit sui soli 369 Home vs Away) | Dettaglio | 10 / 3 | 22 / 53 |
| Costa | Dettaglio + contesto | 9 / 4 | 23 / 52 |

Ogni sorgente è interamente esclusa dal proprio fit di verifica. Entrambe
erano già state osservate nei cicli precedenti: non è un nuovo test cieco.
La differenza di dati fra sorgenti (13 contro 211 positivi) limita il confronto.
Il contesto non risolve la generalizzazione in questa prova; non dimostra
che ogni uso possibile del contesto sia inutile. Nessun ritocco di scala/soglia.

Classificatore dettaglio:
`428025d268564e1b8e42b237140d6560aaf21a9073b91ee11ecf3966541d5d18`.
Classificatore dettaglio + contesto:
`12e0e378060aa26938522f6288f5665259e8cc37296270e15e8a8c07a4b0db7c`.

## Verifiche e decisione

Docker senza rete, CPU limitata a due core. Feature dei 457 esempi, due fold
per sorgente e fit finali: 6,61 s esclusi export/decodifica. Feature e score
condivisi sui controlli: 0,96 s per 97 coppie e 1,10 s per 133. Sono esclusi
detector e intero job: nessuna affermazione sul tempo completo del prodotto.

11 test passati: viste native, bordi, criteri di ammissione, regressione per
sorgente, pooling e fit esistente. Audit indipendente senza ML ricomputa
conteggi e decisione, verifica 914 crop, provenienza dei 49 box, duplicato,
dimensioni dei classificatori e composizione dei fold.

Variante respinta. Coda completata: export, confronto, verifica per partita,
controlli temporali, audit. Replay continuo e controllo 240–290 s erano
condizionati al passaggio dei controlli: non eseguiti. Nessuna modifica al
worker operativo, app, database, dipendenze, configurazione o migrazioni.
Resta aperto il riconoscimento robusto: non si avanza a tiri/esiti con questi
classificatori. I dati locali sono pronti per un distinto protocollo di
addestramento senza richiedere nuovi video all'utente.
