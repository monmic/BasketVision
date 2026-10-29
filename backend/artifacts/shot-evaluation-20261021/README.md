# Confronto diagnostico dei tiri — 21 ottobre 2026

## Aggiornamento del 26 ottobre: confronto precedente superato

Audit successivo completato: [copertura palla e prova della cadenza tile](ball-gap-audit/README.md).
Tile ogni frame non risolve i vuoti di detection nel campione; variante non promossa.

Completata anche la [prova del ritaglio centrato sul ferro](rim-roi-trial/README.md):
nessun guadagno nelle detection accettate o nei candidati tiro; variante non promossa.

Passo successivo: [screening dei modelli locali e preparazione dei casi difficili](specialist-screening/README.md).
Nessun modello promosso; preparata la revisione dei 19 casi condivisi e richiesto
un nuovo video locale per una validazione fuori dalle sorgenti già esaminate.

La verifica visiva su 32 frame dell'intervallo originale e su tutti i frame con
detection accettate mostra un ferro largo circa **26 px**, non 75 px, alla
risoluzione originale 854×480. Le 48 sovrapposizioni controllate sono in
`original-temporal-review/rim-review-v2/episode-00-rim-proposals.jpg`.
La posizione stimata varia da x=254 a x=258, y=173. La geometria è approssimata,
non un'annotazione certificata al pixel. La calibrazione salvata non è stata modificata.

Il candidato a 435,467 s descritto sotto dipende dalla larghezza sovrastimata:
**non costituisce un miglioramento verificato del rilevatore**. `evaluate.py`
continua intenzionalmente a riprodurre il vecchio report e la vecchia calibrazione.
Il nuovo confronto usa `replay_temporal_review.py` e produce zero candidati su
tutti e sei gli episodi, anche nelle 27 varianti di geometria per episodio.

Conclusioni, riproduzione e stato della coda: [revisione temporale](temporal-review-results.md).

## Risultato storico con calibrazione da 75 px

Snapshot in sola lettura degli eventi revisionati della sola analisi
`ce355034-9329-4fff-bfd4-9b9a2c96a033`. Nessun evento o report operativo modificato.

Riproduzione dalla cartella backend:

```powershell
py -3.12 artifacts/shot-evaluation-20261021/evaluate.py
```

Intervallo analizzato e calibrato: 433–436 secondi. Dei sei tiri manuali,
solo quello a 434,68 s ricade nell'intervallo. Gli altri cinque, a 592,85,
1175,91, 1191,56, 1199,54 e 1207,89 s, sono esclusi: non sono falsi negativi.

Il report originale contiene zero candidati: un tiro perso su un solo tiro
valutabile. Il replay del detector corrente sulle stesse 24 detection accettate,
senza nuove inferenze, produce un candidato a 435,467 s. Abbinamento uno a uno
con tolleranza temporale esplicita di 1 secondo: scarto 0,787 s, un tiro abbinato,
zero persi e zero candidati senza corrispondenza nel replay.

Questo non dimostra accuratezza generale. Le annotazioni non certificano tutti
i possibili tiri e i candidati senza corrispondenza non sarebbero automaticamente
falsi positivi. La confidenza del candidato è 0,0344, un punteggio di evidenza
del detector, non probabilità calibrata di tiro. La calibrazione più recente usa
larghezza ferro 75 px; il precedente tentativo da 49 px è un riferimento diverso.
Non confondere il miglioramento del replay con una modifica del report salvato.

Prossimo passo: verificare visivamente la larghezza del ferro e preparare brevi
analisi calibrate attorno agli altri cinque timestamp, tenendo conto degli
eventuali movimenti di camera. Solo dopo sarà possibile misurare la copertura
su più episodi senza contare come errori tratti mai analizzati.
