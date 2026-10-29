# Audit del minuto 08:20–09:20 — 26 ottobre 2026

Analisi locale `62ad4576-6f50-42b8-929b-91a87b1890b5` del video Home vs Away.
Report operativo completo: 1.800 frame palla, 1.476 candidati grezzi, 96
osservazioni accettate in 92 frame e sette track ID confermati. I 96 box sono
stati tutti controllati, non solo i 12 frame debug esportati dal worker.

Coda dell'audit:

1. Revisione esaustiva dei box accettati: completata.
2. Ricostruzione dei candidati grezzi con stessi pesi e impostazioni: completata.
3. Verifica della riproduzione e confronto della conferma temporale già esistente: completati.
4. Valutazione separata di scarpe eliminate, palle conservate e nuove accettazioni: completata.
5. Preparazione dei ritagli verificati per regressione: completata.

## Riferimento visivo iniziale

| Etichetta del box accettato | Osservazioni |
|---|---:|
| Scarpe | 61 |
| Palla in azione | 31 |
| Candidato minuscolo non classificabile con sicurezza | 4 |

Le quattro tavole `accepted-01.jpg`–`accepted-04.jpg` conservano l'indice di
ogni osservazione e il track ID. Verde significa accettato dal tracker, non
palla certificata. Etichette esplicite in `accepted-reviewed.json`.
Non sono annotati tutti i frame del video: nessuna misura di recall complessiva.

La track 5 contiene 26 scarpe e 21 palle; la track 11 contiene nove palle e
quattro candidati incerti. I track ID non identificano quindi necessariamente
lo stesso oggetto fisico per tutta la sequenza. Questo non dimostra da solo
un bug: occorre ricostruire i candidati intermedi che il report non conserva.

Confidenza mediana: scarpe 0,2043, palle 0,1371; massimi rispettivamente 0,7113
e 0,5406. Alzare una soglia di confidence non separa in generale questi esempi:
diverse scarpe hanno punteggi superiori a quelli delle palle reali.

Gli hash del worker locale e del worker nel container coincidono; i pesi
operativi sono quelli baseline già verificati. Ricostruzione ball-only separata,
senza rete, due core/thread, input in sola lettura, nessun accesso al database.
Report, risultati applicativi e configurazione restano invariati.

## Riproduzione e confronto misurato

La nuova inferenza riproduce esattamente tutti i 1.476 candidati grezzi nel
conteggio e tutte le 96 osservazioni accettate per timestamp, centro, track ID
e confidenza. Report completo grezzo in `raw.json`; 1.800 frame con timestamp
assoluti da 500 a 560 secondi. Il lavoro di ricostruzione è durato 388,49 s,
esclusi caricamento e riscaldamento dei predictor full/tiled; è diagnostica
ball-only su CPU locale, non il tempo end-to-end del job o una previsione VM.

Riutilizzato `scripts/compare_ball_trackers.py` sugli stessi candidati, con
`BALL_TRACK_TEMPORAL_WINDOW=true`, finestra di conferma già prevista 0,2 s e
recupero 0,1 s. Nessuna nuova soglia, nessun filtro camera e nessuna inferenza
aggiuntiva per il confronto. Il flag operativo rimane disattivato.

Revisionate tutte le 53 nuove accettazioni in due ulteriori tavole:
21 scarpe, 16 palle, 16 candidati minuscoli incerti. La variante rimuove tre
scarpe già accettate, ma anche due palle vere a 523,067 e 523,100 s.

| Contenuto dei box accettati, revisione visiva | Baseline | Finestra temporale |
|---|---:|---:|
| Scarpe | 61 | 79 |
| Palla in azione | 31 | 45 |
| Minuscoli/incerti | 4 | 20 |
| **Totale** | **96** | **144** |

La maggiore continuità recupera 14 osservazioni nette della palla, ma accetta
anche 18 scarpe in più e aumenta l'incertezza. Non è una riduzione dei falsi
positivi richiesta da questo audit. Non si attribuiscono automaticamente i
20 box incerti a sfondo o palla. Questi conteggi non stimano il recall sul
video, poiché i frame privi di accettazioni non sono interamente annotati.

Il riferimento di regressione è l'unione di 149 proposte distinte presenti
nei due profili: 82 scarpe, 47 palle e 20 incerti, ognuna legata a frame e
coordinate originali. `evaluate_cohort.py` verifica che i box siano presenti,
separa le perdite di palle dalle scarpe rimosse e segnala le nuove accettazioni
non revisionate. Dopo la revisione completa non restano accettazioni senza
etichetta in nessuno dei due profili.

## Interpretazione e decisione

Il detector assegna a diverse scarpe punteggi elevati. Scarpe che si muovono
coerentemente possono soddisfare il requisito di conferma temporale come una
palla: la continuità geometrica non certifica la classe dell'oggetto.
Il tracker usa posizione e velocità, senza un'identità visiva dell'oggetto;
la persistenza dello stesso ID non garantisce quindi la stessa identità fisica.
Gli esempi della track 5 mostrano questo limite. Non è stata identificata una
correzione di bug che separi in sicurezza le due classi senza altre evidenze.

**Variante non promossa.** Conservati entrambi i risultati: la finestra è utile
come candidato diagnostico per continuità, ma non risolve il problema delle
scarpe e perde due osservazioni corrette. Nessuna riduzione arbitraria delle
soglie né filtro generalizzato vicino ai piedi, che potrebbe eliminare palleggi.

Il prossimo requisito del detector è distinguere questi casi semanticamente.
Preparati `object-examples/manifest.json` e 129 PNG nativi dei soli box
verificati: 82 scarpe e 47 palle. I 20 incerti sono esclusi. Le immagini delle
scarpe sono ritagli dei box, **non** interi frame etichettati come negativi:
fuori dal box può essere presente una palla reale. Sono esempi di classificazione
di proposte, non label YOLO complete del video. Frame vicini sono correlati;
il manifest conserva gruppi temporali e provenienza, senza inventare uno split
train/val/test o avviare training. La validazione futura deve separare sorgenti
o episodi; non utilizzare questi esempi di sviluppo come test cieco.

La coda dell'audit e della singola prova temporale è completata. Nessun intervento
dell'utente è necessario per questa verifica; il risultato non completa la
milestone di tracking né abilita eventi automatici.

## Script, riproduzione e validazione

Gli script locali di questa cartella sono adattatori diagnostici:

- `audit_analysis.py accepted`: tutti i ritagli accettati del report; con
  `--replay <experimental.json> --new-only` produce soltanto le nuove accettazioni.
- `audit_analysis.py infer`: ricostruisce i candidati ball-only, riusando il worker.
- `evaluate_cohort.py`: confronto delle proposte revisionate con controlli di copertura.
- `prepare_object_examples.py`: ritagli nativi dei soli box classificati con sicurezza.

Nel container worker montare la cartella su `/output`, il report operativo su
`/report.json`, i video su `/videos` e i modelli su `/models`; input in sola
lettura, rete disabilitata, `/tmp` temporaneo. Per l'inferenza usare due CPU,
`VISION_CPU_THREADS=2`, `BALL_MODEL=/models/yolo26n.pt` e
`YOLO_CONFIG_DIR=/tmp/ultralytics`. I file già esistenti non vengono sovrascritti.

Con i candidati salvati, dalla cartella backend:

```powershell
py -3.12 ../scripts/compare_ball_trackers.py artifacts/ball-tracking-audit-20261026/raw.json --output-dir artifacts/ball-tracking-audit-20261026/nuovo-confronto
py -3.12 artifacts/ball-tracking-audit-20261026/test_evaluate_cohort.py
py -3.12 ../scripts/test_ball_tracker.py
py -3.12 ../scripts/test_reviewed_shots.py
```

Output principali: `accepted-reviewed.json`, `new-accepted-reviewed.json`,
`combined-reviewed.json`, `complete-comparison.json`, `temporal-window/`,
`object-examples/manifest.json`. Hash di worker, modello e report in `raw.json`.
Tutte le immagini e i report generati restano diagnostica locale, non da committare.

Validazioni: 24 test superati (3 del valutatore, 18 tracker, 3 calibrazione);
ricostruzione esatta del report, replay deterministico, impostazioni della variante,
149 proposte revisionate, 129 PNG e relativi hash verificati. Nessuna modifica a
worker, frontend, API, configurazione applicativa o database; nessuna migrazione
o nuova dipendenza. Non è stata eseguita un'analisi dei tiri sul minuto, poiché
non era richiesta e manca una calibrazione temporale del ferro per il segmento.
