# Prova causale di continuità

Usare soltanto i 1798 frame e le proposte già salvate di Costa 60–120 s.
Nessun nuovo training, soglia adattata ai controlli o modifica al worker.

Una traccia ombra baseline può sostenere un candidato semanticamente negativo
solo se il candidato è già accettato dalla baseline, ha almeno il numero
esistente di hit per il controllo statico, altrettanti hit consecutivi, e una
velocità media superiore alla soglia statica esistente. La traccia operativa
del prototipo conserva tutte le proprie regole di avvio/conferma e budget debole.
Evidenza solo presente/passata; nessuna retroaccettazione dei frame precedenti.

Confrontare baseline, filtro precedente e variante sulle identità già riviste.
Per passare: tutte le 68 osservazioni palla baseline conservate, falsi noti
non superiori agli 8 del filtro, nessuna nuova accettazione non verificata sui
riferimenti fissi. Un passaggio autorizza soltanto ulteriore verifica, mai il
rilascio. Se fallisce, non ritoccare le soglie e non usare il tratto 240–290 s.
