# Diagnosi delle palle perse e prova di scala

Nessuna delle due varianti migliora il modello attuale sulla validazione.
Il problema osservato è soprattutto l’assenza di candidati, non un piccolo
errore nella posizione del rettangolo. Tutte le misure usano confidenza 0.02
e IoU 0.5, senza tracker.

## Diagnosi sulle predizioni salvate

Nel modello originale e nel checkpoint fine-tuned selezionato, 29 delle 41
palle del train e 12 delle 16 della validazione non intersecano alcun candidato
alla soglia 0.02. Non significa che non esistano punteggi inferiori alla soglia.
Le altre palle sono già abbinate a IoU almeno 0.5. Nell’ultima epoca un caso del
train ha una sovrapposizione insufficiente; 28 non hanno candidati sovrapposti.
Conteggi in `missed-ball-diagnosis.json`.

## Prova sul modello originale

| Profilo | TP | FP | FN |
|---|---:|---:|---:|
| Full-frame 960 | 4 | 0 | 12 |
| Full-frame 1600 | 3 | 1 | 13 |
| Full-frame 960 + quattro tile 960 | 4 | 0 | 12 |

I tile sono quattro ritagli fissi, ciascuno largo e alto il 60% dell’immagine,
ancorati agli angoli. I box vengono riportati alle coordinate originali e
deduplicati con NMS a IoU 0.5. Le annotazioni non determinano i ritagli di
inferenza. Non equivale alla pipeline completa del worker, che aggiunge filtri
e tracking. L’esperimento riguarda solo questi due profili, non ogni possibile scala.

Selezione predefinita: massimo F1 sulla validazione a soglia fissa, con preferenza
per il modello originale in caso di parità. Vince il modello originale: non
sono state eseguite nuove inferenze sul test. I suoi valori in `comparison.json`
sono quelli già salvati. I tempi includono decode e warm-up e non costituiscono
un benchmark controllato di velocità.

## Revisione visiva e decisione

Esaminati i 16 ritagli della validazione in `validation-crops.jpg`. Mostrano
palla in mano, in volo e presso il tabellone, con blur e contorni talvolta poco
distinti. Questa verifica non evidenzia uno spostamento sistematico delle
annotazioni e non sostituisce un audit indipendente delle etichette.
I ritagli di revisione sono centrati sulle annotazioni e **non vengono usati
per misurare la detection**.

Non cambiare risoluzione, soglie o modello attivo sulla base di questi risultati.
La prossima ipotesi da verificare è un fine-tuning con ritagli di training
derivati dalle annotazioni esistenti, mantenendo i pesi della classe 32: più
esempi visivi della palla a scale e contesti differenti. Tutti i ritagli di uno
stesso episodio devono restare nello stesso split. La valutazione deve avvenire
sui frame completi, senza ritagli guidati dal riferimento. Si tratta di una
prova da eseguire, non di un miglioramento già dimostrato.

Dataset piccolo della stessa partita, già esaminato e senza negativi verificati.
Script riproducibili: `experiment.py` e `review.py`, nell’immagine worker con
repository montato read-only su `/repo`, output su `/output` e rete disattivata.
Modello e versioni sono quelli della prova `ball-pilot-20261011`.
Nessuna modifica al worker, al database o al modello attivo.
