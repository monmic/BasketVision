# Dettaglio e contesto con i video disponibili — 28 ottobre

Nessun nuovo video richiesto. Coda: export verificato delle due viste,
confronto dei classificatori, verifica per partita, controlli temporali,
audit e decisione. Il quarto step della roadmap (integrazione) rimane
condizionato alla qualità; 240–290 s escluso finché i controlli non passano.

Training: 409 proposte revisionate esistenti più i box positivi dei soli
full-frame `train` del dataset ampliato (49 box). Non usare val/test, nuovi
negativi non verificati o identità Costa 60–120 s nel fit. Eliminare soltanto
duplicati esatti con stessa sorgente, frame e bounds; conflitti vietati.

Dettaglio: crop originario, preprocessing 128 e pooling 2×2 già provati.
Contesto: rettangolo centrato sul medesimo crop, larghezza e altezza triple,
ritagliato ai bordi, stesso preprocessing e backbone congelato. Concatenare
le due rappresentazioni (2048 feature). Nessun jitter, nuovo backbone,
ricerca del fattore di contesto o modifica della soglia .5 / L2 .01.

Confronto equo: rifare anche il fit solo dettaglio sugli stessi esempi
ampliati. Due fold per sorgente, sempre escludendo una partita intera;
nessun frame o duplicato della sorgente esclusa entra nel fit del fold.
Questi sono controlli di sviluppo, non un nuovo test indipendente.
Congelare entrambi i fit finali PRIMA di leggere i controlli Costa:
97 proposte e 133 identità già note (una incerta esclusa). Non sommarli.

Per autorizzare ulteriori replay: nessuna palla persa nei due controlli,
riduzione stretta dei falsi rispetto al flusso senza filtro, nessuna regressione
di palle/falsi rispetto al solo dettaglio su ciascun controllo e fold per
sorgente. Non scegliere un metodo o ritoccare parametri sui controlli.
Il passaggio non autorizza da solo un rilascio. Se fallisce, completare
l'audit e chiudere questa prova senza consumare il tratto riservato.

Hash di manifest, immagini sorgente e crop esportati; verificare corrispondenza
pixel del dettaglio ai 409 crop precedenti. Misurare feature/fit separatamente
dalla decodifica. Docker CPU 2 core, rete disabilitata, nessun cambiamento
all'applicazione, nessuna dipendenza aggiunta.
