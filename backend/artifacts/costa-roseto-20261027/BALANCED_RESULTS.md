# Dataset riequilibrato: ciclo completato, variante non promossa

28 ottobre 2026. [Protocollo](BALANCED_PROTOCOL.md) fissato prima delle immagini
e del fit. Nessun nuovo video o intervento manuale richiesto all'utente.

## Annotazioni e separazione

Dodici frame selezionati a priori, ogni quattro secondi da 15 a 59 s. Otto
nuovi box di palla attiva verificati su frame nativi e contesto ingrandito;
43, 47 e 59 s esclusi per ambiguità mano/occlusione, 39 s è una schermata di
testo. I tre casi incerti non diventano negativi. Box riproducibili nello
script `record_balanced_annotations.py`, congelati prima del training.

Pool: 465 esempi (457 precedenti più 8). Per ridurre le ripetizioni: un solo
esempio per sorgente, classe, secondo e cella del centro 64×64, dando priorità
alle annotazioni. È una riduzione deterministica delle osservazioni vicine,
non una prova di indipendenza o deduplicazione percettiva. Rimangono 180
esempi; 285 esclusi come ripetizioni secondo questa regola.

Validazione Home vs Away: intera sequenza 500–560 s. Dopo l'ispezione dei tagli
Costa, prima del fit, validazione estesa da 48–60 a 44–60 s: l'azione era già
presente a 44/46 s. Guardia 42–44 s esclusa. Nessun riaddestramento sui frame
di validazione, che rimangono controlli di sviluppo già noti da cicli precedenti.

| Destinazione | Esempi |
|---|---:|
| Training | 104 |
| Validazione | 72 |
| Guardia esclusa | 4 |

Training: Home vs Away 44 palle e 10 negativi; Costa 12 palle e 38 negativi.
Ogni combinazione sorgente/classe riceve il 25% della massa della BCE nella
variante. Non si dichiarano quantità equilibrate o nuovi esempi indipendenti:
si riequilibra il peso del fit. Il riferimento usa gli stessi 104 esempi senza
pesi. Backbone congelato, dettaglio 128/pooling 2×2, L2 .01 e soglia .5 invariati.

## Risultati del confronto prefissato

| Controllo | Fit | Palle conservate/perse | Falsi conservati/respinti |
|---|---|---:|---:|
| Validazione Home vs Away | Riferimento | 16 / 0 | 12 / 10 |
| Stessa validazione | Riequilibrato | 16 / 0 | 12 / 10 |
| Validazione Costa | Riferimento | 5 / 1 | 3 / 25 |
| Stessa validazione | Riequilibrato | 5 / 1 | 3 / 25 |
| 97 proposte Costa 60–120 s | Riferimento | 4 / 5 | 25 / 63 |
| Stesse proposte | Riequilibrato | 4 / 5 | 28 / 60 |
| 133 identità Costa, una incerta esclusa | Riferimento | 54 / 14 | 40 / 24 |
| Stesse identità | Riequilibrato | 57 / 11 | 40 / 24 |

I controlli Costa sono sovrapposti e non vanno sommati. Sono identità note,
non recall esaustiva o test su nuove partite. Si recuperano tre osservazioni
palla rispetto al riferimento equo, ma si perdono ancora undici palle note e
aumentano tre falsi nell'altro controllo. Il criterio fallisce; non si cambia
soglia dopo l'esito, non si promuove il riferimento come ripiego.

## Verifiche e costo

12 test passati: pesi sorgente/classe, equivalenza al fit esistente con pesi
uniformi, scelta delle ripetizioni, confini e guardia, criteri di regressione,
pooling e fit semantico. Audit indipendente senza ML verifica selezione,
hash dei crop, provenienza, indici del fit, assenza della validazione dal fit,
massa dei pesi, conteggi e decisione. Nessun dato dei controlli entra nel fit
o nella normalizzazione. Entrambi i classificatori salvati prima dei controlli.

Hash annotazioni:
`c8c60bbaed7ccf16a7986d1822fe8c505cef4ffff5fba4f92f41f20b167bf86b`.
Hash dataset:
`f3d78f8083b7ed2a0b97693847568617e90c290d73e8482a04fadc40904d9303`.
Hash classificatore riequilibrato:
`8c923fded3789e51ce1439d4cbab7e0216e1a88583f1cf2d68cf844af162dbcf`.

Feature e due fit sui 104 esempi: 2,95 s, Docker senza rete e limitato a due
core CPU. Tempo esclusi lettura/export, decodifica, controlli, detector e intero
job: nessuna affermazione sul tempo dell'analisi dell'app.

## Chiusura della coda

Completati annotazioni, riduzione ripetizioni, separazione delle sequenze,
variante unica, confronto e audit. Replay continuo, uso di 240–290 s e
integrazione restavano subordinati al passaggio: non eseguiti. Nessuna modifica
al worker operativo, frontend, backend applicativo, dipendenze, configurazione
o migrazioni. Dataset, modelli e immagini generati ignorati da Git.
Resta aperto il riconoscimento robusto della palla; non si avanza a tiri o
esiti sulla base di questi risultati. Non sono richiesti nuovi caricamenti.
