# Revisione temporale dei sei episodi — 26 ottobre 2026

## Risultato

Completata la coda diagnostica: estrazione fitta, controllo del ferro, revisione
dei box accettati, replay dei candidati e verifica del riferimento originale.
Docker è nuovamente disponibile; il blocco ambientale precedente è risolto.

Estratti 205 frame dei cinque episodi aggiuntivi e 32 dell'episodio originale.
La quantizzazione al frame più vicino può spostare il campione richiesto fino
a mezzo frame: nel manifest sono registrati gli istanti effettivi, assoluti.
Controllate cinque tavole temporali, i 18 ritagli dei box palla aggiuntivi e
265 sovrapposizioni del ferro sui frame campionati e su ogni detection accettata.
I 18 box mostrano la palla in azione; questo non certifica i candidati grezzi.

| Episodio | Timestamp manuale | Box accettati | Massima sequenza con gap ≤250 ms | Candidati nel replay |
|---|---:|---:|---:|---:|
| Originale | 434,68 | 24 | 24 | 0 |
| 1 | 592,85 | 9 | 5 | 0 |
| 2 | 1175,91 | 7 | 5 | 0 |
| 3 | 1191,56 | 2 | 1 | 0 |
| 4 | 1199,54 | 0 | 0 | 0 |
| 5 | 1207,89 | 0 | 0 | 0 |

Negli episodi 3–5 manca già la continuità minima di tre osservazioni. Nel primo
episodio aggiuntivo la sequenza iniziale riguarda una palla bassa prima del tiro;
le successive osservazioni sono separate da ampi vuoti. Nel secondo episodio
la sequenza in avvicinamento è breve; manca l'evidenza continua vicino al ferro.
Nell'originale l'ultima osservazione è a 435,467 s, prima dell'arrivo al ferro:
con una larghezza corretta la sequenza non soddisfa le regole esistenti.

## Metodo e limiti

Registrazione del tabellone rispetto a un frame di riferimento con template a
cinque scale (0,90–1,10); centro/larghezza iniziali del ferro scelti visivamente.
Le stime sono state controllate sulle tavole sovrapposte. Il primo seed
dell'episodio 4 era troppo a destra ed è stato corretto nella versione v2;
gli output iniziali sono conservati come proposte superate.

Il replay usa solo detection accettate salvate. Per ogni loro frame esiste
una registrazione diretta: nessuna interpolazione dei vuoti. Le coordinate
sono riportate a un riferimento virtuale solidale al ferro e passate al detector
esistente, senza cambiare le sue soglie. Questo è un esperimento offline:
non implementa il supporto della camera mobile nel worker. Le coordinate delle
eventuali evidenze del replay sono virtuali, non pixel del video originale.

Provate 27 varianti per episodio: offset del centro di -4/0/+4 px per asse e
larghezza moltiplicata per 0,8/1/1,2. Tutte producono zero candidati. Questa
sensibilità non certifica la precisione della calibrazione né la qualità generale
del rilevatore. I cinque intervalli offline restano distinti dal job originale:
non diventano retroattivamente parti analizzate di quel job. Nessuna stima di
precision/recall complessiva, nessuna classificazione segnato/sbagliato.

La larghezza originale da 75 px è sovrastimata rispetto ai circa 26 px visibili.
Il precedente candidato abbinato non può quindi essere usato come prova di successo.

## Riproduzione

Dalla cartella backend, in un ambiente con OpenCV e NumPy, usare output nuovi:

1. `prepare_temporal_review.py --video <video> --output <directory nuova>`:
   estrazione fitta, senza inferenza.
2. `build_temporal_boards.py`: cinque tavole e ritagli dei box accettati.
3. `track_review_rims.py`: registrazioni e sovrapposizioni in
   `temporal-review/rim-review-v2`.
4. Per il riferimento originale, usare `--episodes original-episode.json`
   nell'estrazione e `--original-report <report originale>` nella registrazione.
5. `py -3.12 artifacts/shot-evaluation-20261021/replay_temporal_review.py`:
   confronto dei sei episodi, senza dipendenze esterne.

I due script per le tavole/registrazioni sono strumenti locali di questo campione:
si eseguono nel container worker montando questa cartella su `/output`, i video
su `/videos` in sola lettura e, per l'originale, il report su `/original.json` in
sola lettura. Rete disattivata. Percorso video e geometrie sono espliciti negli script.
Gli output esistenti vengono protetti dalla sovrascrittura; il replay finale è
`temporal-review/replay-six-episodes.json`. Per ripeterlo senza scrivere,
importare il modulo e chiamare `evaluate()`.

## Validazione e chiusura della coda

Estrazioni e registrazioni eseguite sul video locale, controlli visivi completati;
replay e sensibilità eseguiti; 12 test esistenti del detector superati.
Nessun modello, parametro del worker, evento, report operativo o database modificato.
Nessuna migrazione/configurazione applicativa. Gli output sono diagnostica locale,
non materiali da promuovere o aggiungere a un commit.

Non restano item azionabili nella coda di confronto dei sei episodi. L'integrazione
automatica e il miglioramento della copertura palla appartengono ai successivi
interventi di sviluppo/benchmark della roadmap, fuori da questa verifica diagnostica.
