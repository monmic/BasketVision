"""Offline ball fine-tuning retaining the pretrained 80-class head.

Mount repository read-only at /repo and a new writable directory at /output.
Run with the existing basketvision-worker image, without network access.
"""
import copy
import hashlib
import json
import logging
from pathlib import Path
import shutil
import sys
import time

import torch
import ultralytics
from ultralytics import YOLO
from ultralytics.models.yolo.detect.train import DetectionTrainer
from ultralytics.nn.tasks import DetectionModel
from ultralytics.utils import LOGGER

sys.path.insert(0, '/repo/scripts')
from evaluate_ball_clip import matches

OUT = Path('/output')
SOURCE = Path('/repo/storage/diagnostics/home-vs-away-dataset-v1')
WEIGHTS = Path('/repo/storage/diagnostics/models/yolo26n.pt')
THRESHOLDS = [0.02, 0.1, 0.25, 0.5]


def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, allow_nan=False))


class VerifiedTrainer(DetectionTrainer):
    def get_model(self, cfg=None, weights=None, verbose=True):
        model = super().get_model(cfg, weights, verbose)
        if weights is None:
            raise ValueError('Pretrained weights are required')
        expected = weights.float().state_dict()
        actual = model.state_dict()
        mismatch = [k for k in expected if k not in actual or
                    not torch.equal(expected[k].cpu(), actual[k].cpu())]
        extra = sorted(set(actual) - set(expected))
        save('actual-transfer.json', dict(tensors=len(expected),
                                         mismatches=mismatch, extra=extra))
        if mismatch or extra:
            raise ValueError('Training initialization differs from pretrained weights')
        return model


def audit_transfer():
    source = YOLO(str(WEIGHTS)).model.float()
    # Reproduce the first pilot's initialization using the installed implementation.
    one = DetectionModel(copy.deepcopy(source.yaml), nc=1, verbose=False)
    one.names = {0: 'ball'}
    one.load(copy.deepcopy(source), verbose=False)
    a, b = source.state_dict(), one.state_dict()
    incompatible = {k: {'source': list(a[k].shape), 'target': list(b[k].shape)}
                    for k in a.keys() & b.keys() if a[k].shape != b[k].shape}
    audit = dict(sourceClass=source.names[32], previousTargetClass=one.names[0],
                 incompatibleShapes=incompatible,
                 exactSharedTensors=sum(torch.equal(a[k], b[k])
                     for k in a.keys() & b.keys() if a[k].shape == b[k].shape))
    save('previous-transfer-audit.json', audit)
    del one
    return source.names


def prepare(names):
    annotations_path = Path('/repo/vision/fixtures/home-vs-away-ball-annotations-revised-v1.json')
    annotations = json.loads(annotations_path.read_text(encoding='utf-8-sig'))
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    assert manifest['annotationsSha256'] == hashlib.sha256(annotations_path.read_bytes()).hexdigest()
    truth = {r['frame']: r['boxes'] for r in annotations['frames']}
    seen, counts = set(), {}
    for row in manifest['frames']:
        assert row['frame'] not in seen
        seen.add(row['frame'])
        assert row['episode'] in manifest['split']['splits'][row['split']]
        labels = (SOURCE / row['label']).read_text().splitlines()
        assert len(labels) == len(truth[row['frame']]) == row['boxes']
        for line, box in zip(labels, truth[row['frame']]):
            cls, x, y, w, h = map(float, line.split())
            x1, y1, x2, y2 = box
            assert cls == 0
            assert max(abs(u-v) for u, v in zip([x,y,w,h],
                       [(x1+x2)/2,(y1+y2)/2,x2-x1,y2-y1])) < 1e-7
        counts[row['split']] = counts.get(row['split'], 0) + 1
    assert seen == set(truth)
    dataset = OUT / 'dataset'
    shutil.copytree(SOURCE, dataset)
    for label in (dataset / 'labels').rglob('*.txt'):
        lines = label.read_text().splitlines()
        label.write_text(''.join('32 ' + line.split(' ', 1)[1] + '\n' for line in lines))
    # JSON is valid YAML and avoids ambiguous quoting of class names.
    (dataset / 'data.yaml').write_text(json.dumps(dict(
        path=str(dataset), train='images/train', val='images/val', test='images/test',
        names=names)))
    save('dataset-audit.json', dict(counts=counts, annotationSha256=manifest['annotationsSha256'],
                                  frames=manifest['frames'], labelMapping={'0': 32}))
    return dataset


def score(weights, dataset, splits, name):
    detector = YOLO(str(weights))
    assert detector.names[32] == 'sports ball'
    output, predictions_dump = {}, {}
    for split in splits:
        totals = {str(c): dict(tp=0, fp=0, fn=0) for c in THRESHOLDS}
        predictions_dump[split] = []
        for image in sorted((dataset / 'images' / split).glob('*.png')):
            targets = []
            for line in (dataset / 'labels' / split / (image.stem + '.txt')).read_text().splitlines():
                cls, x, y, w, h = map(float, line.split())
                assert cls == 32
                targets.append([x-w/2, y-h/2, x+w/2, y+h/2])
            result = detector.predict(str(image), imgsz=960, conf=0.02,
                                      classes=[32], device='cpu', verbose=False)[0]
            boxes, scores = result.boxes.xyxyn.tolist(), result.boxes.conf.tolist()
            predictions_dump[split].append(dict(image=image.name, truth=targets,
                                                 boxes=boxes, confidence=scores))
            for threshold, counts in totals.items():
                predictions = [b for b, c in zip(boxes, scores) if c >= float(threshold)]
                tp = matches(predictions, targets, 0.5)
                counts['tp'] += tp
                counts['fp'] += len(predictions)-tp
                counts['fn'] += len(targets)-tp
        output[split] = totals
        print(name, split, totals, flush=True)
    save(name + '-predictions.json', predictions_dump)
    save(name + '-metrics.json', output)
    return output


def main():
    if (OUT / 'dataset').exists() or (OUT / 'train').exists():
        raise ValueError('Use a new output directory')
    LOGGER.addHandler(logging.FileHandler(OUT / 'training.log'))
    torch.set_num_threads(2)
    start = time.monotonic()
    names = audit_transfer()
    assert names[32] == 'sports ball' and len(names) == 80
    dataset = prepare(names)
    baseline = score(WEIGHTS, dataset, ['train', 'val'], 'baseline-development')
    model = YOLO(str(WEIGHTS))
    model.train(trainer=VerifiedTrainer, data=str(dataset / 'data.yaml'),
                epochs=20, patience=20, imgsz=960, batch=4, device='cpu', workers=0,
                seed=42, deterministic=True, project=str(OUT), name='train',
                exist_ok=False, pretrained=True, freeze=10, optimizer='AdamW',
                lr0=0.0001, warmup_bias_lr=0.0, amp=False,
                mosaic=0.0, close_mosaic=0, mixup=0.0, scale=0.2, translate=0.05,
                plots=False, save=True, classes=[32])
    best = OUT / 'train/weights/best.pt'
    pilot = score(best, dataset, ['train', 'val'], 'pilot-development')
    # No training decisions are based on the test split.
    baseline.update(score(WEIGHTS, dataset, ['test'], 'baseline-test'))
    pilot.update(score(best, dataset, ['test'], 'pilot-test'))
    save('comparison.json', dict(
        notice='Exploratory same-game sample, previously inspected. No verified negatives. Test not independent.',
        selection='Best checkpoint selected by trainer using validation mAP50-95; fixed 20-epoch budget.',
        versions=dict(ultralytics=ultralytics.__version__, torch=torch.__version__),
        baselineSha256=hashlib.sha256(WEIGHTS.read_bytes()).hexdigest(),
        pilotSha256=hashlib.sha256(best.read_bytes()).hexdigest(),
        thresholds=THRESHOLDS, imgsz=960, iou=0.5,
        elapsedSeconds=time.monotonic()-start, models=dict(baseline=baseline, pilot=pilot)))


if __name__ == '__main__':
    main()
