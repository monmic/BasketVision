# Costa vs Roseto — protocollo fissato prima della valutazione

- Sorgente nuova: partita `ad0b3783-9ef0-49b9-8645-a8fac9540389`.
- Nessun job applicativo esistente; diagnostica isolata, senza scritture nel DB.
- Sviluppo/training: soltanto i 329 ritagli Home vs Away già revisionati.
- Verificatore sperimentale: backbone COCO yolo26n congelato, feature su crop
  letterbox 128, media spaziale; classificatore logistico lineare con L2 0.01,
  soglia standard 0.5. Nessuna ricerca di soglie sul nuovo filmato.
- Verifica interna per episodio intero, mai split casuale di frame vicini.
- Congelare e identificare con SHA-256 il classificatore prima della prima
  valutazione Costa vs Roseto; nessuna annotazione Costa entra nel training.
- Primo controllo fuori sorgente: [0,60) secondi. Riferimento visivo ai secondi
  pari 0,2,...,58, selezionati prima di vedere il video o le predizioni.
- Il resto del video non viene usato per scegliere modello o soglie in questa
  prova; rimane disponibile per un successivo test congelato.
- Confronto baseline e verificatore sugli stessi candidati e sugli stessi frame;
  misurare separatamente palla conservata, errori rimossi ed eventuali perdite.
- Il verificatore non crea nuove detection: nessun aumento di recall dichiarato.
  Non promuoverlo se elimina evidenze reali necessarie al tracking/tiri.
- Annotazioni predisposte durante lo sviluppo dall'assistente, distinguendo
  frame/box incerti; nessuna richiesta di annotazione all'utente.
- Questa prova non certifica riconoscimento automatico di segnato/sbagliato,
  squadre o accuratezza sull'intera partita. Nessuna modifica operativa prima
  del confronto, nessuna nuova dipendenza applicativa.
