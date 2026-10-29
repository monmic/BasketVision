# Seconda prova: adattamento, non nuovo test fuori sorgente

Il primo confronto congelato è concluso e conservato: il classificatore perde
una delle tre proposte palla baseline. Il modello e i risultati non cambiano.

Per proseguire senza chiedere altre annotazioni all'utente:

- Il blocco [0,60) Costa vs Roseto diventa **sviluppo** per questa seconda prova.
- Aggiungere soltanto le 80 proposte già revisionate (64 baseline e 16 ROI)
  ai precedenti 329 esempi. Etichette sui box, non sui frame interi.
- Conservare la stessa rappresentazione, regolarizzazione e soglia 0.5;
  nessuna ricerca di parametri sul blocco successivo.
- Gruppo Costa-first60 unico nella verifica per gruppi, evitando che crop
  duplicati dello stesso oggetto entrino su entrambi i lati del fold.
- Congelare un nuovo modello con SHA-256 PRIMA di inferire il blocco [60,120).
- Controllo ai secondi 60,62,...,118, scelti prima di vedere questi frame.
- Questo è un controllo temporale dello stesso montaggio, NON una nuova
  sorgente indipendente: eventuali replay di azioni vanno segnalati e i numeri
  non dimostrano generalizzazione a nuove partite.
- Verificare separatamente anche il controllo 720p precedente, mai incluso
  nel training. È già stato usato in sviluppo per altri confronti e non è cieco.
- Non promuovere il modello per la sola riduzione dei falsi positivi se elimina
  proposte reali. Non avviare inferenza d'esito o statistiche con questi dati.
