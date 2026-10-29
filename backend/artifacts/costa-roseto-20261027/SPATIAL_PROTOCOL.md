# Verificatore con disposizione spaziale, 28 ottobre 2026

Ipotesi: la media globale delle feature elimina la disposizione visiva utile a
distinguere palla, scarpe, teste e scritte. Confrontare la media precedente con
un unico pooling 2×2 (1024 feature) sul medesimo backbone congelato e sugli
stessi 409 ritagli verificati. Non aumentare artificialmente l'informazione:
l'ingresso resta il crop nativo portato a 128 pixel dal preprocessing esistente.

Conservare fit, regolarizzazione .01 e soglia .5. Nessuna ricerca di parametri.
Verifica per episodio sul training, poi congelamento del classificatore prima
di valutare i controlli noti: 97 proposte del secondo minuto e 133 identità del
replay (una incerta esclusa dai conteggi). Nessuna etichetta dei controlli entra
nel fit. I controlli sono sovrapposti e non vanno sommati come esempi indipendenti.

Controllare hash dei dati, pixel dei crop e dimensioni native. Per proseguire:
nessuna palla respinta in entrambi i controlli e riduzione stretta dei falsi
rispetto al flusso senza filtro. Se fallisce: niente replay continuo, niente
integrazione, niente uso di 240–290 s. Il costo del verificatore va misurato
separatamente da decodifica, detector e analisi completa.
