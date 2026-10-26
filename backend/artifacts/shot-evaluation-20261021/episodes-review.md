# Cinque episodi aggiuntivi

## Ripresa del 26 ottobre 2026

Preparato `prepare_temporal_review.py`: estrae frame originali ogni 0,1 secondi,
include il timestamp manuale e gli estremi, registra indice frame e timestamp
assoluto nel manifest. Richiede una directory nuova e non modifica calibrazioni,
report o database. Il manifest viene scritto solo a estrazione completata.

Esecuzione dalla cartella backend, con Python dotato di OpenCV:

```powershell
py -3.12 artifacts/shot-evaluation-20261021/prepare_temporal_review.py --video ../storage/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4 --output artifacts/shot-evaluation-20261021/temporal-review
```

Blocco iniziale risolto: estrazione eseguita tramite l'immagine worker locale.
Completati revisione temporale e replay offline. Risultato e stato finale della
coda: [temporal-review-results.md](temporal-review-results.md).
Le calibrazioni fisse operative restano non assegnate: la registrazione temporale
è conservata separatamente come diagnostica approssimata.

Preparati intervalli di quattro secondi centrati sulle annotazioni manuali:

| Episodio | Timestamp manuale | Intervallo (secondi) |
|---|---:|---|
| 1 | 592,85 | 590,85–594,85 |
| 2 | 1175,91 | 1173,91–1177,91 |
| 3 | 1191,56 | 1189,56–1193,56 |
| 4 | 1199,54 | 1197,54–1201,54 |
| 5 | 1207,89 | 1205,89–1209,89 |

Esaminati visivamente i 15 frame originali (inizio, timestamp, fine).
Il ferro cambia posizione in tutti gli episodi: non assegnata una calibrazione
fissa ai quattro secondi. `episodes.json` conserva `calibration=null` e lo stato
di attesa della revisione temporale. Tre frame non certificano la stabilità tra
i campioni e non determinano da soli il momento esatto del contatto col ferro.

`episode-XX-ball.json` contiene inferenze full-frame e tiled, con tracking della
palla a 30 fps. Elaborazione separata dal database applicativo; video montato in
sola lettura e rete disattivata. Non genera eventi di tiro né modifica annotazioni.
`episodes-ball-summary.json` riassume i conteggi dopo il completamento.

Elaborazione completata e verificata: cinque report, 120 frame ciascuno,
600 frame complessivi e timestamp coerenti con gli intervalli richiesti.

| Episodio | Candidati palla grezzi | Detection accettate | Track confermate |
|---|---:|---:|---:|
| 1 | 58 | 9 | 2 |
| 2 | 63 | 7 | 1 |
| 3 | 37 | 2 | 1 |
| 4 | 88 | 0 | 0 |
| 5 | 62 | 0 | 0 |

Le detection accettate possono appartenere a oggetti differenti dalla palla in
azione: questi conteggi non sostituiscono la revisione visiva dei box. Negli
episodi 4 e 5 manca completamente l'evidenza accettata da fornire al detector tiri.
I pesi sono quelli locali `storage/diagnostics/models/yolo26n.pt`; CPU a 2 thread,
confidence iniziale per nuove track 0,12. Le altre impostazioni ball effettive sono
salvate nei report. Il confronto riguarda la pipeline palla, senza inferenza persone.

Passo completato il 26 ottobre: revisione del ferro su frame più fitti e confronto
offline dei candidati, senza riutilizzare la calibrazione del precedente episodio.
Zero candidati nel replay; non è una misura generale di accuratezza.
