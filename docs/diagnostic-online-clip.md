# Diagnostica locale del campione online

Video locale: `storage/videos/test-online.mp4`, 3840×2160, 60 fps, 1220 frame
(20,33 secondi). Analisi online di riferimento:
`e479ff45-989d-418c-980f-979b9354d39a`.

## Errore a 10,17 secondi

La prova locale con il worker CPU production e confidence di nuova track 0,12
riproduce il falso positivo sulla scarpa al frame 610 (10,1667 s).
Il candidato full-frame ha confidence 0,2619, rettangolo
`[1239.1, 1668.4, 1300.0, 1752.4]` in coordinate originali e score 0,09166.
Il tracker lo accetta con `confirmed_track_temporal_association`, dopo cinque
hit nella traccia locale. La scarpa viene riconosciuta anche nei frame vicini,
quindi la sola conferma temporale non elimina questo falso positivo.

Nel frame 610 non compare un candidato sulla palla in gioco. Il passaggio tiled
non è previsto su quel frame dalla cadenza corrente; nei frame 608 e 611 i
passaggi tiled rilevano ancora la scarpa. Al frame 608 compare anche un candidato
debole sulla palla a bordo campo, scartato per score insufficiente.
Non è quindi sufficiente abbassare la soglia di accettazione del tracker per
recuperare la palla in gioco al frame 610.

## Misura preliminare delle prestazioni

Segmento: 9,0–10,5 s, tracker inizializzato all'inizio del segmento.
Tempi di una singola esecuzione locale Docker CPU, esclusi caricamento dei modelli
e warm-up; non sono stime dei tempi sulla VM Oracle né una riproduzione completa
dello stato del job originale.

| Profilo sperimentale | Frame analizzati per la palla | Tempo totale | Decode | Inferenza full | Inferenza tiled | Persone |
|---|---:|---:|---:|---:|---:|---:|
| Originale 4K/60 fps | 90 | 35,96 s | 10,76 s | 11,21 s | 10,35 s | 2,69 s |
| Resize 720p, un frame ogni quattro | 23 | 16,80 s | 10,27 s | 2,72 s | 2,18 s | 0,74 s |

Il resize richiede altri 0,75 s nel secondo profilo. Il decode legge comunque
tutti i frame 4K: saltare l'inferenza non elimina questo costo. Il secondo
profilo campiona anche le persone una volta ogni tre frame selezionati.
L'immagine di ingresso del modello resta configurata come nel worker:
full-frame palla 960, tile 640 e persone 640.

Il profilo originale produce 8 detection accettate nel segmento, quello ridotto
zero. Questi conteggi **non misurano accuratezza** e non dimostrano un miglioramento:
il campionamento modifica sia i candidati sia la conferma temporale.
Nessuna configurazione production è stata cambiata.

## Riproduzione

Da PowerShell nella radice del repository, con immagine production già costruita:

```powershell
New-Item -ItemType Directory -Force storage/diagnostics/models | Out-Null
docker run --rm --name basketvision-ball-diagnostic `
  -e BALL_TRACK_NEW_MIN_CONFIDENCE=0.12 `
  -e YOLO_MODEL=/data/diagnostics/models/yolo26n.pt `
  -v "${PWD}/vision/worker.py:/app/worker.py:ro" `
  -v "${PWD}/scripts:/diagnostics:ro" `
  -v "${PWD}/storage:/data" `
  basketvision-prod-worker python /diagnostics/diagnose_ball_clip.py `
  /data/videos/test-online.mp4 /data/diagnostics/online-clip
```

Lo script non accede al database. Scarica il modello se assente, poi salva JSON
con candidati/motivi di rifiuto, immagini e tempi in `storage/diagnostics/online-clip`.
Le prove successive devono confrontare anche il controllo positivo a 2,87 s,
annotare palle e scarpe su più frame e valutare separatamente rilevatore,
conferma temporale e costo di una copia video preconvertita. Il tempo di
conversione andrà incluso nel confronto complessivo.
