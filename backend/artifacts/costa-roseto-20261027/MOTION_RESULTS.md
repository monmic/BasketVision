# Continuità delle tracce: prova completata, respinta

Protocollo fissato in [MOTION_PROTOCOL.md](MOTION_PROTOCOL.md). Nessuna modifica
al worker operativo, modello, configurazione, database o interfaccia.

## Diagnosi

Ricostruiti i dintorni temporali di tutte le 15 osservazioni palla perse:
11 rigetti `weak_candidate_cannot_start_track`, quattro
`track_not_temporally_confirmed`. Il report locale ignorato
`detector-preserved/motion-support/loss-diagnosis.json` registra per ciascuna
identità la stessa traccia baseline nel mezzo secondo precedente e successivo,
hit, velocità, evidenza semantica e accettazioni dei tre tracker.
Il futuro serve esclusivamente alla diagnosi, mai al recupero.

## Unica variante provata

Traccia ombra baseline con almeno sei hit consecutivi e velocità media sopra
12 px/s: valori già presenti nel controllo statico del worker, non ottimizzati
sui risultati. Il sostegno può rendere forte l'evidenza semantica ma non elimina
le normali regole del tracker sperimentale. Nessun nuovo passaggio CNN.

| Identità note accettate | Baseline | Filtro precedente | Sostegno del movimento |
|---|---:|---:|---:|
| Palla | 68 | 53 | 54 |
| Non palla | 64 | 8 | 28 |

1798 frame, 579 candidati sostenuti, 928 accettazioni complessive contro 586
del filtro precedente e 1344 baseline. Recuperata solo l'osservazione 114;
14 osservazioni palla restano perse. Nessuna nuova identità sui riferimenti
fissi; le altre nuove accettazioni non sono dichiarate corrette.
Il moto di una proposta non basta a identificarla come palla: il sostegno
riapre venti falsi già noti. Non si attribuiscono categorie specifiche ai
singoli falsi senza una nuova verifica visiva.

Replay CPU senza inferenza: circa 0,18 s, esclusi caricamento JSON, CNN e video;
non è il tempo di un'analisi dell'app né un confronto di prestazioni del detector.
Queste identità sono controlli di sviluppo noti, non un test cieco o recall
esaustiva. Nessuna ricerca di soglie dopo l'esito negativo.

## Verifica e chiusura della coda

28 test passati: cinque del recupero (inclusi riproduzione del risultato,
uguaglianza del prefisso causale e rigetto per falsi), cinque dei contratti
semantici, 18 del tracker originale. Il replay verifica tutte le accettazioni
della traccia ombra contro la baseline memorizzata.

Completati diagnosi, prototipo isolato e confronto sui falsi. Il quarto item,
controllo su 240–290 s, era condizionato al passaggio dei precedenti: non va
eseguito con questa variante. Coda della prova mirata esaurita. Nessuna
promozione; non serve un intervento dell'utente per annotare o interpretare
risultati nell'app. Resta aperto il riconoscimento visivo robusto della palla:
questa prova esclude la sola continuità/movimento come rimedio sufficiente.
