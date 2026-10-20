# Revisione dei 72 fotogrammi — 13 ottobre 2026

Esaminati tutti i 72 fotogrammi a scena intera, senza sovrapporre predizioni,
e gli ingrandimenti della zona della parete. Aggiunti **39 box** per la palla
ferma a bordo campo: 11 train, 14 val, 14 test. Comprendono i due box gia
confermati nell'audit precedente: 37 aggiunte rispetto a quella copia.
Le 72 annotazioni originali della palla in azione sono conservate esattamente.

La copia completa contiene 72 frame e 111 box. Per l'esportazione sono esclusi
conservativamente 21 frame con occlusioni, visibilita parziale o sfocatura nella
zona della palla aggiuntiva. Non sono trasformati in esempi negativi.

| Split | Frame esportati | Box | Frame esclusi |
|---|---:|---:|---:|
| Train | 23 | 34 | 18 |
| Val | 14 | 28 | 2 |
| Test | 14 | 28 | 1 |
| Totale | 51 | 90 | 21 |

Il dataset conserva gli split per episodio e usa la classe COCO 32 `sports ball`,
con la testa a 80 classi dei precedenti esperimenti. Sono annotate solo le palle:
questo export serve agli esperimenti sul rilevatore della palla, non costituisce
un dataset COCO completamente annotato per persone e altre classi.
Non sono stati aggiunti automaticamente i ritagli negativi del precedente audit.

## Risultato sulle predizioni gia salvate

Ricalcolo a confidenza 0.02 e IoU 0.5 sullo **stesso sottoinsieme di 51 frame**.
Il file JSON include anche 0.1, 0.25 e 0.5, il riferimento precedente sugli stessi
frame e il ricalcolo diagnostico sull'intero insieme di 72 frame.

| Modello | Split | Detection abbinate | Detection non abbinate | Palle annotate non rilevate |
|---|---|---:|---:|---:|
| Baseline | Train | 4 | 16 | 30 |
| Con ritagli | Train | 6 | 27 | 28 |
| Baseline | Val | 4 | 0 | 24 |
| Con ritagli | Val | 6 | 11 | 22 |
| Baseline | Test | 2 | 3 | 26 |
| Con ritagli | Test | 2 | 4 | 26 |

Tre detection train per ciascun modello, prima non abbinate, corrispondono alle
palle aggiunte. Le altre aggiunte aumentano il numero di palle non rilevate.
In val/test nessuna delle palle aggiuntive risulta abbinata a questa soglia.
La copertura della palla in azione rimane quella delle predizioni precedenti;
nel test esportato entrambi i modelli ne rilevano 2 su 14 a confidenza 0.02.
Il ricalcolo non dimostra un miglioramento del modello e non giustifica una
promozione del fine-tuning nel worker.

## Artefatti e verifiche

- `review.json`: decisione per tutti i 72 frame, motivazione, split, hash immagini,
  box aggiuntivi in pixel e hash delle tavole esaminate.
- `annotations-reviewed.json`: copia diagnostica completa, 72 frame/111 box.
- `annotations-eligible.json`: sottoinsieme conservativo, 51 frame/90 box.
- `dataset/`: immagini e label YOLO; `data.yaml` per host,
  `data-container.yaml` per un container che monta questa cartella in `/output`.
- `reference-only-comparison.json`: confronti prima/dopo su insiemi identici.
- `verification.json`: verifiche superate, hash label e predizioni usate.
- `board-01.jpg`–`board-12.jpg`: scene intere; `detail-*` e `localize-*`:
  ingrandimenti senza box; `boxes-*`: controllo visivo dei 39 box aggiunti.
- `review_decisions.py`: decisioni manuali riproducibili;
  `export_and_score.py`: export e ricalcolo, rifiuta un dataset gia esistente;
  `validate_export.py`: lettura indipendente delle label esportate.

Verificate conservazione degli originali, limiti dei box, hash delle immagini,
assenza dei 21 frame esclusi dall'export, ricostruzione dei 90 box dalle 51 label,
classe corretta, isolamento degli episodi e copertura delle predizioni salvate.

Limiti: revisione di un solo assistente, box manuali approssimati su immagini
854x480, oggetti piccoli e sfocati. `fullyAudited=false` distingue la revisione
di tutti i frame da una certificazione indipendente dell'esaustivita delle label.
Le metriche sono esplorative: gli stessi cinque episodi dello stesso video sono
gia stati esaminati, incluso il test. Le detection non abbinate non sono tutte
automaticamente falsi positivi certificati. Le palle ferme appartengono al
rilevatore; la loro esclusione dall'analisi dei tiri resta un problema separato.

Questa revisione sostituisce, per i prossimi esperimenti, la precedente copia
parziale con due sole aggiunte. Originali, modello operativo e contratti delle
applicazioni non sono stati modificati. Nessun nuovo addestramento eseguito.
