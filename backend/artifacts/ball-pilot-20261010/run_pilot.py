"""Small offline experiment; does not change the deployed model."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

import torch
from ultralytics import YOLO

sys.path.insert(0, '/repo/scripts')
from evaluate_ball_clip import matches

out = Path('/output')
source = Path('/repo/storage/diagnostics/home-vs-away-dataset-v1')
dataset = out / 'dataset'
shutil.copytree(source, dataset)
(dataset / 'data.yaml').write_text(
    'path: /output/dataset\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: ball\n'
)
torch.set_num_threads(2)
weights = Path('/repo/storage/diagnostics/models/yolo26n.pt')
model = YOLO(str(weights))
model.train(data=str(dataset / 'data.yaml'), epochs=5, imgsz=960,
            batch=4, device='cpu', workers=0, seed=42, deterministic=True,
            project=str(out), name='train', exist_ok=False, pretrained=True,
            freeze=10, optimizer='AdamW', lr0=0.001, amp=False,
            mosaic=0.0, mixup=0.0, plots=False, save=True)

summary = {
    'notice': 'Exploratory only: 41 training frames, 16 validation frames, 15 test frames from the same previously inspected game; no verified negatives. Test is not independent.',
    'baselineSha256': hashlib.sha256(weights.read_bytes()).hexdigest(),
    'iou': 0.5, 'imgsz': 960, 'models': {}
}
for name, path, cls in [('baseline', weights, 32), ('pilot', out / 'train/weights/best.pt', 0)]:
    detector = YOLO(str(path))
    summary['models'][name] = {}
    for split in ['val', 'test']:
        totals = {str(c): dict(tp=0, fp=0, fn=0) for c in [0.02, 0.1, 0.25, 0.5]}
        for image in sorted((dataset / 'images' / split).glob('*.png')):
            targets = []
            for line in (dataset / 'labels' / split / (image.stem + '.txt')).read_text().splitlines():
                _, x, y, w, h = map(float, line.split())
                targets.append([x-w/2, y-h/2, x+w/2, y+h/2])
            result = detector.predict(str(image), imgsz=960, conf=0.02,
                                      classes=[cls], device='cpu', verbose=False)[0]
            boxes = result.boxes.xyxyn.tolist()
            scores = result.boxes.conf.tolist()
            for threshold, counts in totals.items():
                predictions = [b for b, c in zip(boxes, scores) if c >= float(threshold)]
                tp = matches(predictions, targets, 0.5)
                counts['tp'] += tp
                counts['fp'] += len(predictions)-tp
                counts['fn'] += len(targets)-tp
        summary['models'][name][split] = totals
        print(name, split, totals, flush=True)
(out / 'comparison.json').write_text(json.dumps(summary, indent=2))
