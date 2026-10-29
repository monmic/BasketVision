# Disposizione delle feature: ciclo completato, nessuna integrazione

28 ottobre 2026. [Protocollo](SPATIAL_PROTOCOL.md) fissato prima del training.
Confronto isolato del verificatore dei ritagli: pooling 2×2 invece della media
globale, stesso backbone YOLO26n congelato, ingresso 128, stessi 409 esempi,
stesso fit, regolarizzazione .01 e soglia .5. Nessuna modifica al detector o
al filtro temporale operativo. Non è un confronto diretto con il diverso
classificatore ausiliario dell'esperimento sulle tracce.

## Esito sui controlli noti esclusi dal training

| Controllo | Metodo | Palle conservate/perse | Falsi conservati/respinti |
|---|---|---:|---:|
| 97 proposte, 9 palle | Media globale | 2 / 7 | 9 / 79 |
| Stesse proposte | Quattro zone | 3 / 6 | 7 / 81 |
| 133 identità, una incerta esclusa | Media globale | 38 / 30 | 23 / 41 |
| Stesse identità | Quattro zone | 46 / 22 | 18 / 46 |

I due controlli si sovrappongono; non si sommano. Le identità non costituiscono
annotazione esaustiva di tutti gli oggetti o recall globale. Sono controlli di
sviluppo già noti, non un nuovo test cieco. Nessuna loro etichetta entra nel fit.
La rappresentazione spaziale migliora i conteggi ma perde ancora palle reali:
non supera il criterio fissato. Nessun replay continuo o uso di 240–290 s.

## Dati e riproducibilità

Hash manifest training:
`3733f338314c003a4f09290acaa225c2a72a5e5ad0dcf6b465d1ebc2c63c7045`.
Hash classificatore congelato prima di caricare i controlli:
`65c5033211f0204f0530a685db41d0c6a3b9b7badbefa3a681a05be0fa425961`.

Verificati hash di tutti i 409 crop, separazione temporale Costa (<60 s nel
training, 60–120 s nei controlli), dimensioni e ricomputazione indipendente
dei conteggi. Il ramo a media riproduce tutte le decisioni storiche sulle 97
proposte; scarto massimo del punteggio 0,0000021 dovuto agli arrotondamenti
float32 dei batch, entro tolleranza 0,00001. Nessun cambiamento della soglia.

Nei crop palla il lato corto misura 10–19 pixel sulle proposte (mediana 13,
7 su 9 sotto 16) e 11–18 sulle identità (mediana 14, 49 su 68 sotto 16).
Ingrandire a 128 non ricrea dettaglio nativo. Questi dati descrivono un limite
del materiale corrente, senza dimostrare che la risoluzione sia l'unica causa.

CPU Docker limitata a due core, rete disabilitata: feature, otto fold per
episodio e fit finale in 5,79 s. Estrazione condivisa delle feature e score dei
controlli: 0,74 s per 97 crop e 0,60 s per 133. Tempi esclusi decodifica,
detector e intero job; nessuna affermazione sul tempo finale del prodotto.

## Coda e verifiche

Completati: controllo del preprocessing, variante spaziale, verifica per
episodio, congelamento, due confronti e audit indipendente. Dieci test passati
(pooling, crop, fit esistente e conteggio delle identità). Pesi, feature e
report generati sono ignorati da Git. Nessuna dipendenza, migrazione o
configurazione di produzione aggiunta.

Coda di questo esperimento esaurita. Il riconoscimento robusto resta aperto;
questa variante non autorizza eventi o statistiche automatiche. Prima di
un altro training occorre un nuovo protocollo sui dati o sulla rappresentazione:
non ottimizzare ulteriormente questi stessi controlli né consumare il tratto
finale per scegliere parametri.
