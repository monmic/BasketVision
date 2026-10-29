# Dati riequilibrati e annotazioni Costa — 28 ottobre

Coda autorizzata: annotare nuovi frame, ridurre ripetizioni, separare sequenze,
training di una variante, verifica e audit. Nessun nuovo video o modifica all'app.

Selezione prima delle immagini: Costa 15,19,23,27,31,35,39,43,47,51,55,59 s.
Box della sola palla attiva verificati sul frame nativo; dubbi esclusi, nessun
negativo assegnato a interi frame di gioco. Riutilizzare i 457 crop verificati.
Nessun controllo 60–120 s, val/test del detector o 240–290 s nel fit.

Conservare solo dettaglio, backbone congelato, pooling 2×2, L2 .01, soglia .5.
Ridurre ripetizioni tenendo un solo esempio per sorgente, classe, secondo
assoluto e cella spaziale 64×64 del centro; priorità ai box annotati anziché
proposte, poi indice stabile. Nessuna selezione sulla predizione.

Validazione prima del training: Home vs Away mantiene fuori l'intera sequenza
500–560 s, Costa mantiene fuori 48–60 s, con guardia 46–48 s esclusa dal fit.
Non riaddestrare sui dati di validazione. Se l'ispezione dei tagli rivela che
un'azione attraversa il confine Costa, estendere l'esclusione prima del fit.
Ispezione pre-fit: il blocco 48–60 attraversa la stessa azione già presente
a 44 e 46 s. Validazione Costa estesa a 44–60 s, guardia 42–44 s.
Sequenze della stessa partita non dimostrano generalizzazione fra partite.

Variante unica: pesare ciascuna combinazione sorgente/classe allo stesso modo
nella BCE. Riferimento equo: stesso fit non pesato, stessi dati ridotti.
Nessun tuning sulla validazione o sui controlli. Congelare entrambi i modelli
prima di caricare i controlli noti Costa 97 proposte e 133 identità (una incerta).
Per proseguire: nessuna palla persa nei controlli, falsi strettamente ridotti
dal flusso senza filtro e nessuna regressione rispetto al riferimento su
ciascuna sorgente di validazione e su ciascun controllo. Passaggio autorizza
solo ulteriore verifica temporale, mai rilascio automatico.

Se fallisce, niente ricerca di altre soglie, niente uso del tratto finale.
Completare audit, conservare il dataset e documentare la coda conclusa.
