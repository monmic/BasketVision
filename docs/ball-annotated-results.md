# Valutazione del campione annotato — 20 settembre 2026

Sorgente: `test-online-720p-15fps.mp4`, 1280×720, 15 fps.
Annotazioni utente: 22 frame revisionati, 12 rettangoli palla, 10 frame senza
palla. Riferimento in `storage/diagnostics/annotations.json`, copiato dai Download.
Abbinamento uno a uno con IoU >= 0,5. I risultati assumono che tutte le palle
visibili siano annotate; eventuali omissioni vengono conteggiate come FP.

Pipeline diagnostica locale: intervallo [0,20), 300 frame, due thread PyTorch,
yolo26n, full-frame 960, tile 640, confidence 0,02, nuova track 0,12.
Si cambia solo BALL_TILE_STRIDE da 3 a 1. Tempi esclusi caricamento/warm-up,
non comparabili direttamente con il tempo end-to-end della VM.

| Misura sui 22 frame | Tile ogni 3 frame | Tile ogni frame |
|---|---:|---:|
| Candidati corretti | 4 | 4 |
| Candidati falsi positivi | 5 | 12 |
| Palle senza candidato corrispondente | 8 | 8 |
| Detection accettate corrette | 1 | 1 |
| Detection accettate false positive | 0 | 1 |
| Palle senza detection accettata | 11 | 11 |
| Tempo diagnostico locale, secondi | 118,23 | 187,08 |

Sul video intero le detection accettate salgono da 26 a 50, ma nel campione
annotato non aumenta il numero di palle correttamente accettate: il solo
conteggio non rappresenta accuratezza. Non applicare questa variante in produzione.

Nel riferimento: frame 43 (2,867 s) candidato scartato per confidence di
avvio traccia; frame 45 (3 s) candidato non ancora confermato temporalmente;
frame 120 (8 s) corrispondenza accettata. Sono casi distinti dalle otto palle
che non hanno un candidato corrispondente: abbassare le soglie del tracker
non può recuperare queste ultime.

Il costo dominante è la ricerca palla: baseline 61,07 s full-frame e 39,80 s
tiled, contro 10,74 s persone e 6,37 s decode. Nella variante tiled costa 113,79 s.

Limiti: campione piccolo e scelto in prevalenza al secondo intero; a 15 fps
questi frame cadono sulla stessa fase della cadenza tiled ogni 3 frame.
Integrare frame intermedi prima di generalizzare. Zero FP accettati nel
riferimento non dimostra assenza di FP nel video completo. Le metriche
dipendono anche dalla precisione dei rettangoli manuali.

Artifact locali: `storage/diagnostics/comparison.json`,
`storage/diagnostics/annotated-baseline/custom.json`,
`storage/diagnostics/annotated-tiles-every-frame/custom.json`.

Prossima prova: confrontare la qualità dei candidati con un detector alternativo
o più dettaglio d'ingresso, mantenendo il medesimo riferimento e misurando il
costo. Validare i candidati prima di rilassare la conferma temporale.
