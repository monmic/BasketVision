"""Generate report and learning curves for the crop experiment."""
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=Path('/output')
report=json.loads((p/'comparison.json').read_text())
with (p/'train/results.csv').open() as f:
    history=[{k.strip():float(v) for k,v in r.items()} for r in csv.DictReader(f)]
best=max(history,key=lambda r:r['metrics/mAP50-95(B)'])
fig,axes=plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
epochs=[r['epoch'] for r in history]
for split,label in [('train','Train: originali + ritagli'),('val','Val: fotogrammi interi')]:
    axes[0].plot(epochs,[r[split+'/cls_loss'] for r in history],label=label)
axes[0].set(title='Loss: distribuzioni diverse tra train e val',xlabel='Epoca',ylabel='Classification loss')
for metric in ['mAP50(B)','mAP50-95(B)']:
    axes[1].plot(epochs,[r['metrics/'+metric] for r in history],label=metric)
axes[1].axvline(best['epoch'],color='gray',linestyle=':')
axes[1].set(title='Validazione su 16 fotogrammi interi',xlabel='Epoca',ylabel='AP')
for ax in axes:
    ax.grid(alpha=.25)
    ax.legend()
fig.savefig(p/'learning-curves.png',dpi=150)
plt.close(fig)

lines=['# Addestramento con ritagli — 11 ottobre 2026','',
    'Il modello recupera due palle nella validazione, ma aumenta i falsi positivi e non',
    'recupera palle nel test a confidenza 0.02. La prova non giustifica una sostituzione',
    'del modello attivo. Arresto anticipato dopo 15 epoche; checkpoint selezionato all’epoca 7.','',
    '## Risultato sui fotogrammi completi','',
    'Confidenza 0.02, IoU 0.5, inferenza full-frame a 960, senza tracker.',
    'TP = palle abbinate; FP = detection non abbinate; FN = palle perse.','',
    '| Split | Originale TP / FP / FN | Modello selezionato TP / FP / FN |',
    '|---|---:|---:|']
for split in ['train','val','test']:
    values=[]
    for name in ['baseline','pilot']:
        m=report['models'][name][split]['0.02']
        values.append(f"{m['tp']} / {m['fp']} / {m['fn']}")
    lines.append(f'| {split} | {values[0]} | {values[1]} |')
lines+=['','I conteggi train usano solo i 41 fotogrammi originali, non i ritagli aggiunti.',
    'Il confronto a quattro soglie è in `comparison.json`; box e confidence nei file `*-predictions.json`.',
    'Il baseline è quello già misurato, con gli stessi pesi, fotogrammi e parametri di inferenza.','',
    '## Dati e protocollo','',
    '41 fotogrammi train, ciascuno usato intero e in due ritagli larghi 256 e 512 pixel,',
    'con proporzioni del video e posizione della palla variabile (seed 42). Totale 123 immagini,',
    'ma sempre 41 osservazioni originali: le 82 copie derivate non sono dati indipendenti.',
    'Nessun ritaglio ricavato dai 16 frame val o dai 15 test. Nessun nuovo negativo inferito.',
    'Split per episodio: tiri 1–3 per training, tiro 4 per validazione, tiro 5 per test.',
    'Tutti i rettangoli nei ritagli derivano dalle annotazioni esistenti; nessuna label suggerita dal modello.',
    'Verificati 82 ritagli, dimensioni PNG, coordinate e provenienza; cinque test di geometria superati.',
    'I box tagliati parzialmente provocano un errore, non vengono ignorati.','',
    'YOLO26n, classe originale 32 sports ball, struttura a 80 classi conservata.',
    '708 tensori iniziali verificati identici al pretrained. Input train 640, batch 8,',
    'AdamW lr 0.0001, primi 10 layer congelati, massimo 20 epoche, patience 8, seed 42.',
    'Mosaic/mixup disattivati; dettagli completi in `train/args.yaml`.',
    'La validazione del trainer usa immagini complete a imgsz 960, con padding rettangolare',
    'a 576×992 verificato in `validation-input-audit.json`. La selezione usa mAP50-95.',
    'L’inferenza finale usa imgsz 960 e lo stesso percorso del baseline.',
    'Non sono stati scelti parametri o checkpoint dai risultati del test.',
    f"Epoche completate: {len(history)}. Massimo mAP50-95 registrato: {best['metrics/mAP50-95(B)']:.5f}, epoca {int(best['epoch'])}.",'',
    '![Curve di apprendimento](learning-curves.png)','',
    '![Controllo di originali e ritagli](crop-preview.jpg)','',
    '## Revisione dei cambiamenti','',
    'Verificati visivamente i due recuperi in validazione: frame 13716 e 13734,',
    'con IoU circa 0.57 e 0.73. Nessuno dei quattro abbinamenti originali è perso.',
    'Nel test rimangono gli stessi due abbinamenti. Al frame 14214 compare un candidato',
    'vicino alla palla, ma IoU circa 0.46: resta un errore alla soglia invariata 0.5.',
    'Nello stesso ritaglio compare anche una detection su una testa, coerente con',
    'la necessità di controllare i falsi positivi; questa tavola non classifica tutti gli errori.',
    '`changed-frames.json` conserva gli elenchi completi di recuperi, perdite e casi invariati.',
    'I ritagli seguenti servono solo alla revisione visiva; le predizioni sono full-frame.',
    '![Confronto dei casi cambiati](changed-frames.jpg)','',
    '## Ultimo checkpoint: solo diagnosi, non selezione','',
    '| Split completo | TP | FP | FN |','|---|---:|---:|---:|']
for split in ['train','val']:
    m=report['lastDevelopment'][split]['0.02']
    lines.append(f"| {split} | {m['tp']} | {m['fp']} | {m['fn']} |")
lines+=['','## Limiti e riproduzione','',
    'Campione piccolo della stessa partita, già esaminato più volte; il test è esplorativo,',
    'non indipendente. Nessun negativo verificato. Le prestazioni sulle altre 79 classi',
    'non sono validate e possono degradare: il checkpoint riguarda solo il detector palla.',
    'Questa prova cambia anche dimensione di training e batch rispetto alla precedente:',
    'non permette di attribuire causalmente ai soli ritagli ogni differenza osservata.',
    'Non sono stati modificati worker, contratti, database o modello attivo.','',
    'Eseguire `run_experiment.py` nell’immagine worker, rete disattivata, repository read-only',
    'su `/repo` e una nuova cartella su `/output` con i file Python di questo esperimento.',
    'Lo script riusa verifiche e scorer di `../ball-pilot-20261011/run_experiment.py`.',
    'Dopo il training, `preview_crops.py` e `summarize.py` generano le tavole e questo report.',
    '`review_changes.py` genera il confronto visivo tra predizioni originali e nuovo modello.',
    'Dataset e pesi generati restano locali e sono esclusi da Git tramite `artifacts/.gitignore`.',
    'Versioni e hash dei modelli in `comparison.json`; provenienza dei ritagli in `crop-manifest.json`.','']
(p/'README.md').write_text('\n'.join(lines),encoding='utf-8')
print('Report and curves saved')
