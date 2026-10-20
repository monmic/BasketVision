"""Create a readable report and learning curves from the completed experiment."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parent
comparison = json.loads((root / 'comparison.json').read_text())
audit = json.loads((root / 'previous-transfer-audit.json').read_text())
transfer = json.loads((root / 'actual-transfer.json').read_text())
with (root / 'train/results.csv').open() as stream:
    history = [{k.strip(): float(v) for k, v in row.items()} for row in csv.DictReader(stream)]
best = max(history, key=lambda r: r['metrics/mAP50-95(B)'])
epochs = [r['epoch'] for r in history]
fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
for split, label in [('train', 'Addestramento'), ('val', 'Validazione')]:
    axes[0].plot(epochs, [r[split+'/cls_loss'] for r in history], label=label)
axes[0].set(title='Errore di classificazione', xlabel='Epoca', ylabel='Loss')
axes[0].legend()
axes[1].plot(epochs, [r['metrics/mAP50-95(B)'] for r in history], label='mAP50-95')
axes[1].plot(epochs, [r['metrics/mAP50(B)'] for r in history], label='mAP50')
axes[1].axvline(best['epoch'], color='gray', linestyle=':', label='Massimo mAP50-95')
axes[1].set(title='Qualita sulla validazione (16 immagini)', xlabel='Epoca', ylabel='AP')
axes[1].legend()
for axis in axes:
    axis.grid(alpha=0.25)
fig.savefig(root / 'learning-curves.png', dpi=150)
plt.close(fig)

lines = [
    '# Fine-tuning palla — 11 ottobre 2026', '',
    'Il trasferimento dei pesi è ora verificato, ma il fine-tuning non recupera più palle',
    'a confidenza 0.02: il checkpoint selezionato mantiene 4 TP su 16 in validazione',
    'e 2 TP su 15 nel test. Nel test i falsi positivi passano da 3 a 2.',
    'Il risultato non giustifica la sostituzione del modello in uso.', '',
    'Esperimento offline sulle annotazioni esistenti: 41 immagini train, 16 val, 15 test.',
    'Gli split contengono episodi distinti della stessa partita, già esaminata durante lo sviluppo.',
    'Il test è esplorativo, non indipendente. Non sono presenti negativi verificati.', '',
    '## Trasferimento dei pesi', '',
    f'La configurazione precedente (`nc=1`, nome `ball`) rendeva incompatibili {len(audit["incompatibleShapes"])} tensori su {transfer["tensors"]}.',
    'La riduzione da 80 classi a una cambia anche la larghezza di parti della testa;',
    'il nome `ball` non corrisponde a `sports ball` nel remapping automatico.',
    'Questo spiega una perdita di inizializzazione preaddestrata, ma non prova da solo la causa di ogni errore precedente.', '',
    'La nuova prova mantiene tutte le 80 classi e rimappa le sole label della copia del dataset da 0 a 32.',
    f'Prima del training sono stati verificati identici tutti i {transfer["tensors"]} tensori del modello.',
    'Le annotazioni originali e i file del dataset di partenza non sono stati modificati.', '',
    '## Protocollo', '',
    '20 epoche; YOLO26n; input 960; batch 4; CPU; primi 10 layer congelati; AdamW lr 0.0001;',
    'warmup bias lr 0; seed 42; mosaic/mixup disattivati; scale 0.2 e translate 0.05.',
    'Dettagli completi in `train/args.yaml`. Selezione del checkpoint esclusivamente sulla validazione.',
    'Il confronto comprende train, val e test; il train misura apprendimento, non generalizzazione.',
    'Nessuna scelta di parametri o soglie effettuata sui risultati del test.',
    f'Versioni: Ultralytics {comparison["versions"]["ultralytics"]}, Torch {comparison["versions"]["torch"]}.', '',
    '## Confronto a soglie fisse', '',
    'Inferenza full-frame, classe 32, senza tracker; abbinamento univoco a IoU 0.5.',
    'TP: palle abbinate; FP: detection non abbinate; FN: palle perse.', '',
    '| Split | Confidenza | Originale TP / FP / FN | Fine-tuning TP / FP / FN |',
    '|---|---:|---:|---:|',
]
for split in ['train', 'val', 'test']:
    for threshold in comparison['thresholds']:
        cells = []
        for name in ['baseline', 'pilot']:
            m = comparison['models'][name][split][str(threshold)]
            assert m['tp'] + m['fn'] == {'train': 41, 'val': 16, 'test': 15}[split]
            cells.append(f"{m['tp']} / {m['fp']} / {m['fn']}")
        lines.append(f'| {split} | {threshold} | {cells[0]} | {cells[1]} |')
lines += ['', '## Andamento e limiti', '',
    f"Loss di classificazione train: {history[0]['train/cls_loss']:.3f} → {history[-1]['train/cls_loss']:.3f}.",
    f"Massimo mAP50-95 sulla validazione: {best['metrics/mAP50-95(B)']:.4f}, epoca {int(best['epoch'])}.",
    'La diminuzione della loss non certifica da sola convergenza o miglioramento fuori dal train.',
    '![Curve di apprendimento](learning-curves.png)', '',
    'Questo modello riceve solo etichette della palla: le altre 79 classi non sono state validate',
    'e le loro prestazioni possono degradare. Il checkpoint è un candidato per il solo detector palla.',
    'Nessuna modifica a worker, modello attivo, contratti o database.', '',
    '## Artefatti e riproduzione', '',
    '`comparison.json` contiene metriche, hash dei pesi e versioni; i file `*-predictions.json`',
    'contengono i box per immagine. `dataset-audit.json` collega immagini, annotazioni e split.',
    '`train/weights/best.pt` conserva il checkpoint selezionato e `train/results.csv` la cronologia.',
    'Eseguire `run_experiment.py` nell’immagine `basketvision-worker:latest` con rete disattivata,',
    'repository montato in sola lettura su `/repo` e una cartella nuova su `/output`.',
    'Montare lo script separatamente oppure copiarlo nella nuova cartella; il programma rifiuta',
    'un output con dataset o training preesistenti. Poi eseguire `summarize_experiment.py` dalla stessa cartella.', '']
if 'lastDevelopment' in comparison:
    lines += ['## Diagnostica dell’ultima epoca', '',
        'Controllo aggiuntivo su train e validazione, senza rivalutare il test né cambiare checkpoint.',
        'Confidenza 0.02, IoU 0.5; il checkpoint finale non è necessariamente quello selezionato.', '',
        '| Split | Ultima epoca TP / FP / FN |', '|---|---:|']
    for split in ['train', 'val']:
        m = comparison['lastDevelopment'][split]['0.02']
        lines.append(f"| {split} | {m['tp']} / {m['fp']} / {m['fn']} |")
    lines += ['', 'Riproduzione: eseguire anche `analyze_last.py` dopo il training e prima di generare questo report.', '']
    lines += ['L’ultima epoca riduce i falsi positivi sul train da 43 a 8, ma conserva 12 TP su 41.',
              'A soglia 0.02 la riduzione della loss non si traduce quindi nel recupero di nuove palle.',
              'Non è dimostrata una convergenza utile alla priorità CV-02. I prossimi esperimenti',
              'devono concentrarsi sui frame mancati, misurando separatamente assenza di candidati',
              'e localizzazione insufficiente, prima di investire in ulteriori epoche.', '']
(root / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
print('Report and learning curves saved.')
