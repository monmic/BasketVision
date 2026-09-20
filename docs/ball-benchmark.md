# Confronto offline della palla

## Thread CPU in produzione

`VISION_CPU_THREADS=0` (default) conserva le scelte delle librerie.
Impostare `VISION_CPU_THREADS=2` in `.env.production` per provare due thread
PyTorch sulla A1 a due OCPU. Richiede il worker aggiornato e ricostruito;
Compose passa la variabile al container. Il callback `on_predict_start`
applica il valore dopo l'inizializzazione del backend, anche quando i modelli
persone e palla vengono inizializzati separatamente. Non modifica OpenCV.
Il log `Vision CPU threads: 2` conferma l'applicazione.

Nel benchmark sintetico A1, una inferenza passa da 0,324–0,325 s a
0,251–0,254 s. Non equivale a una misura dell'intero job: confrontare durata
e report del medesimo video dopo la modifica. Per ripristinare il comportamento
precedente impostare 0 e ricreare il container worker.

`scripts/diagnose_ball_clip.py` registra candidati, dimensioni dei frame,
configurazione effettiva e tempi delle fasi. Non accede al database.
Per analizzare una copia già convertita a 720p/15 fps usare `--stride 1`:
il valore indica frame della sorgente, non fps desiderati.

```powershell
docker run --rm `
  -e BALL_TRACK_NEW_MIN_CONFIDENCE=0.12 `
  -e YOLO_MODEL=/data/diagnostics/models/yolo26n.pt `
  -v "${PWD}/vision/worker.py:/app/worker.py:ro" `
  -v "${PWD}/scripts:/diagnostics:ro" `
  -v "${PWD}/storage:/data" `
  basketvision-prod-worker python /diagnostics/diagnose_ball_clip.py `
  /data/videos/test-online-720p-15fps.mp4 /data/diagnostics/baseline `
  --start 0 --end 20 --stride 1
```

Il report è `custom.json`. Usare cartelle diverse per ogni configurazione;
le variabili BALL_* passate al container consentono prove isolate.
Il percorso misura una pipeline diagnostica: non equivale al tempo completo
di un job, esclude caricamento e warm-up e include eventuale scrittura immagini.

## Riferimento manuale

Per annotare con il mouse, generare la pagina offline (nessun upload):

```powershell
docker run --rm `
  -v "${PWD}/scripts:/diagnostics:ro" `
  -v "${PWD}/storage:/data" `
  --entrypoint python basketvision-prod-worker /diagnostics/prepare_ball_review.py `
  /data/videos/test-online-720p-15fps.mp4 /data/diagnostics/ball-review.html
Start-Process storage/diagnostics/ball-review.html
```

La pagina contiene 22 immagini PNG estratte sequenzialmente, una al secondo
più i controlli a circa 2,87 e 10,17 s. Disegnare tutte le palle visibili e
premere **Conferma palle**; usare **Nessuna palla** solo per assenza verificata.
I frame ambigui vanno esclusi. Scaricare `annotations.json` e salvarlo in
`storage/diagnostics/annotations.json`. Solo i frame confermati sono esportati;
le bozze non confermate non contribuiscono alle metriche. Le annotazioni non
sono salvate automaticamente e la pagina non importa sessioni precedenti.

Creare `storage/diagnostics/annotations.json` con questo schema:

```json
{"frames": [{"frame": 0, "boxes": [[0.1, 0.2, 0.15, 0.3]]}]}
```

Le coordinate sopra sono solo un esempio, non annotazioni del video.
Gli indici partono da zero; i rettangoli sono `[x1/W, y1/H, x2/W, y2/H]`.
Annotare tutte le palle visibili secondo lo stesso criterio in ogni frame.
`boxes: []` significa assenza verificata; omettere frame non revisionati o ambigui.
Includere esempi positivi e negativi, specialmente intorno a 2,87 e 10,17 secondi.
Non riutilizzare indici tra video originali e copie con fps diversi.

```powershell
docker run --rm `
  -v "${PWD}/scripts:/diagnostics:ro" `
  -v "${PWD}/storage:/data" `
  --entrypoint python basketvision-prod-worker /diagnostics/evaluate_ball_clip.py `
  /data/diagnostics/annotations.json `
  /data/diagnostics/baseline/custom.json `
  --output /data/diagnostics/comparison.json
```

Si possono passare più report prima di `--output`, relativi alla stessa sorgente
e allo stesso insieme di frame annotati. I report precedenti senza dimensioni
per frame devono essere rigenerati. Un frame annotato non processato causa errore
per evitare confronti su campioni diversi.

Il valutatore restituisce precision, recall, TP, FP, FN e frame con errori,
separatamente per candidati dopo merge (`raw`) e detection accettate.
L'abbinamento è uno a uno con IoU >= 0,5, modificabile con `--iou`;
un duplicato resta falso positivo. Una metrica senza denominatore è `null`.
I risultati descrivono solo il campione revisionato, non l'intera partita.
