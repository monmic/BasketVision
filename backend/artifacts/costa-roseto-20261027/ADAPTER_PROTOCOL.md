# Adattamento dell'ultimo blocco visivo — 29 ottobre

Coda: contratti del prototipo, training limitato, controllo della conservazione
dei pesi, confronto sui controlli e decisione. Solo artefatti offline.

Usare gli stessi 104 esempi train e 72 validazione del dataset riequilibrato,
senza cambiare selezione, etichette o split. Inizializzare dal classificatore
riequilibrato congelato. Preprocessing 128 e pooling 2×2 invariati. Normalizzazione
delle feature congelata ai valori del training precedente; soglia .5 invariata.

Addestrare soltanto C2PSA (blocco 10 del backbone) e classificatore lineare.
Blocchi 0–9 congelati. Tutte le BatchNorm in eval, buffer congelati. Cache dei
prefissi solo per risparmiare calcolo, nessuna seconda rete nel prodotto.
AdamW: LR blocco 1e-5, LR head 1e-4, weight_decay=0; BCE pesata per sorgente/classe
e L2 .01 della head come nel fit precedente, clip grad norm 1, batch16,
10 epoche, seed20261029, nessuna augmentation o ricerca di iperparametri.

Checkpoint selezionato con minima BCE pesata sui soli 72 esempi di validazione,
includendo epoca0 fra le possibilità; in caso di parità tenere il precedente.
Nessun riaddestramento sulla validazione. Congelare il checkpoint selezionato
prima di caricare i controlli Costa 97 proposte e 133 identità note.

Riferimento: classificatore riequilibrato precedente, senza adattamento.
Per autorizzare replay: nessuna palla persa sui controlli, riduzione stretta
dei falsi dal flusso senza filtro e nessuna regressione palle/falsi rispetto
al riferimento su ciascun controllo e sorgente di validazione. Nessun rilascio
automatico. Se fallisce: audit e chiusura, senza ritocchi o uso di 240–290 s.
Misurare training/score CPU separatamente dal tempo completo dell'app.
