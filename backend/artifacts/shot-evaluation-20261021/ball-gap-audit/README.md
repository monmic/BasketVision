# Audit della copertura palla — 26 ottobre 2026

## Coda autorizzata

1. Audit dei candidati mancanti/scartati e delle interruzioni: completato.
2. Prova mirata: confronto offline `BALL_TILE_STRIDE=3` contro `1`, completato.
3. Misura di copertura, associazioni e costo CPU sugli stessi sei intervalli: completata.
4. Replay dei candidati tiro, senza modifica delle soglie o dei dati applicativi: completato.

## Audit iniziale

Revisionate sei tavole (79 frame) e selezionati sei frame con palla visibile per
episodio: 36 osservazioni mirate. Frame ambigui/tagliati non vengono usati come
esempi di palla assente. Questo campione non è un riferimento esaustivo di tutte
le palle: non misura precision né falsi positivi complessivi.

| Stato della palla in azione | Frame selezionati |
|---|---:|
| Detection accettata | 4 |
| Box corrispondente presente ma scartato dal tracker | 10 |
| Nessun box corrispondente nei candidati salvati | 22 |

Motivi dei dieci scarti: cinque candidati deboli non possono iniziare una traccia,
quattro osservazioni appartengono a tracce non confermate, una avvia una traccia
ancora da confermare. Abbassare solo le soglie del tracker non recupererebbe i
22 frame senza box della palla. Assenza nei candidati significa assenza **dopo**
confidence/NMS; non prova che il modello non abbia prodotto proposte sotto soglia.

Gli indici dei box corrispondenti sono espliciti in `reviewed-gaps.json`.
La selezione a 0,1 s può coincidere con una fase della cadenza tile: i conteggi
descrivono solo i frame selezionati, non la copertura media su tutti i frame.

Per l'episodio originale, il report operativo conservava solo le detection
accettate. Recuperati candidati grezzi tramite inferenza ball-only in container
senza rete; le 24 detection accettate riproducono esattamente timestamp, centro,
track ID e confidenza del report. Il replay del tracker sui candidati di tutti
i sei episodi riproduce le 42 accettazioni già note. I cinque motivi di scarto
mancanti nei vecchi report risultano sotto la soglia di aggiornamento: il
riscontro è registrato separatamente, senza correggere i report originali.

## Vincoli della prova

Stesso video, intervalli, modello, soglie, dimensioni di inferenza e tracker;
solo la cadenza tile cambia. CPU limitata a due core/thread. Tempi locali,
non predizioni di prestazioni sulla VM. Modello riscaldato prima del confronto;
tempi includono seek/decode/inferenza/tracking, escludono caricamento del modello.
I due profili vengono eseguiti in sequenza: una singola prova non misura la
variabilità termica o del carico host. Nessuna configurazione operativa modificata.

## Risultato del confronto

Elaborati 690 frame per profilo (1.380 complessivi) negli stessi sei intervalli.
Le liste complete dei candidati della baseline riproducono esattamente gli
output precedenti, inclusi centro, timestamp, track ID, confidenza e accettazione.

| Episodio | Tempo baseline / variante (s) | Accettate baseline / variante | Massima sequenza continua baseline / variante | Candidati tiro baseline / variante |
|---|---:|---:|---:|---:|
| Originale | 37,43 / 32,37 | 24 / 29 | 24 / 24 | 0 / 0 |
| 1 | 26,67 / 42,44 | 9 / 9 | 5 / 5 | 0 / 0 |
| 2 | 25,70 / 45,35 | 7 / 9 | 5 / 7 | 0 / 0 |
| 3 | 26,20 / 44,43 | 2 / 2 | 1 / 1 | 0 / 0 |
| 4 | 24,02 / 49,25 | 0 / 0 | 0 / 0 | 0 / 0 |
| 5 | 22,54 / 53,79 | 0 / 0 | 0 / 0 | 0 / 0 |
| **Totale** | **162,56 / 267,62** | **42 / 49** | — | **0 / 0** |

Costo osservato +64,6%; il primo episodio presenta tempi invertiti rispetto agli
altri, compatibili con variabilità host/inizializzazioni residue. Il riscaldamento
prima del timer riguarda la chiamata full-frame: non garantisce la completa
inizializzazione di tutte le forme tiled. Questi tempi sono una singola misura
locale, non un benchmark di produzione né una stima precisa del rallentamento.

I sette nuovi box accettati sono stati controllati visivamente:
cinque seguono un passaggio prima del tiro originale, due allungano l'avvicinamento
nel secondo episodio aggiuntivo. Non sono stati persi i 42 box già accettati;
non sono emersi oggetti estranei nei sette nuovi box. Questo non certifica tutte
le associazioni delle tracce né misura i falsi positivi dei 103 candidati grezzi
aggiuntivi, che non sono stati tutti annotati.

Negli stessi 36 frame revisionati:

| Stato | Baseline | Tile ogni frame |
|---|---:|---:|
| Detection accettata della palla in azione | 4 | 5 |
| Box della palla presente ma scartato | 10 | 9 |
| Nessun box corrispondente | 22 | 22 |

La modifica recupera una conferma, non risolve i vuoti di detection osservati.
Il replay usa `scripts/diagnose_reviewed_shots.py`, con le geometrie riviste del
ferro interpolate fra i campioni, e mantiene tutte le regole del detector tiro.
Nessun candidato nei due profili; nessun evento o risultato segnato/sbagliato scritto.

**Decisione: variante non promossa.** Il piccolo guadagno di tracking non risolve
il collo di bottiglia vicino al ferro e richiede più elaborazione. Non si procede
con altre soglie o varianti arbitrarie nella prova limitata a una modifica.
La coda autorizzata di audit, singola prova, benchmark e replay è esaurita.
Non serve alcun intervento dell'utente per chiudere questa verifica.

## File e riproduzione

Tutti i file sono nella cartella `backend/artifacts/shot-evaluation-20261021`:

- `audit_original_raw.py`: recupera il report grezzo originale (nuova inferenza).
- `build_gap_audit.py`: tavole dei candidati; `--profile every-frame` mostra la variante.
- `review_ball_gaps.py`: selezione e corrispondenze visive esplicite dei 36 frame.
- `benchmark_tile_cadence.py`: entrambi i profili, impostazioni effettive e tempi per fase.
- `build_tile_delta_boards.py`: tutti i nuovi box accettati, senza selezione di quelli favorevoli.
- `compare_tile_cadence.py`: confronto e replay usando il detector esistente.

Gli script con OpenCV si eseguono nel container worker con rete disattivata,
cartella diagnostica su `/output`, video su `/videos` e modelli su `/models`,
questi ultimi due in sola lettura. Per l'inferenza usare `--cpus 2`,
`VISION_CPU_THREADS=2`, `BALL_MODEL=/models/yolo26n.pt`, `YOLO_CONFIG_DIR=/tmp/ultralytics`,
filesystem del container in sola lettura e `/tmp` temporaneo.
Le directory/file di output devono essere nuovi. Il benchmark non modifica la
configurazione del container operativo e usa solo il modello palla isolato.

Senza nuove inferenze, dalla cartella backend:

```powershell
py -3.12 -c "import sys; sys.path.insert(0,'artifacts/shot-evaluation-20261021'); from compare_tile_cadence import compare; print(compare()['totals'])"
py -3.12 ../scripts/test_ball_tracker.py
py -3.12 ../scripts/test_ball_benchmark.py
py -3.12 ../scripts/test_shot_detector.py
```

Output principali: `reviewed-gaps.json`, `raw-reason-summary.json`,
`reviewed-every-frame.json`, `tile-cadence/comparison.json` e
`tile-cadence/new-accepted-reviewed.json`. I dati generati restano locali.

Validazione: 32 test esistenti superati (18 tracker, 2 benchmark, 12 detector),
frame e impostazioni dei profili verificati, riproducibilità del confronto verificata.
Modificati esclusivamente script/documentazione/artifact di questa diagnostica.
Nessuna migrazione, dipendenza o configurazione applicativa aggiunta.
