"""Fixed-scale ablation on validation; evaluate one selected profile on test."""
import json
from pathlib import Path
import sys
import time
import cv2
import torch
from ultralytics import YOLO

sys.path.insert(0, '/repo/scripts')
from evaluate_ball_clip import iou, matches

OUT = Path('/output')
PRIOR = Path('/repo/backend/artifacts/ball-pilot-20261011')
DATA = PRIOR / 'dataset'
torch.set_num_threads(2)
model = YOLO('/repo/storage/diagnostics/models/yolo26n.pt')
assert model.names[32] == 'sports ball'


def predict(image, size):
    result = model.predict(image, imgsz=size, conf=0.02, classes=[32], device='cpu', verbose=False)[0]
    return list(zip(result.boxes.xyxyn.tolist(), result.boxes.conf.tolist()))


def suppress(candidates):
    kept = []
    for box, confidence in sorted(candidates, key=lambda v: v[1], reverse=True):
        if not any(iou(box, existing) > 0.5 for existing, _ in kept):
            kept.append((box, confidence))
    return kept


def measure(profile, split):
    rows = []
    start = time.monotonic()
    for path in sorted((DATA / 'images' / split).glob('*.png')):
        image = cv2.imread(str(path))
        h, w = image.shape[:2]
        targets = []
        for line in (DATA / 'labels' / split / (path.stem+'.txt')).read_text().splitlines():
            cls, x, y, bw, bh = map(float, line.split())
            assert cls == 32
            targets.append([x-bw/2, y-bh/2, x+bw/2, y+bh/2])
        if profile == 'full1600':
            candidates = predict(image, 1600)
        else:
            candidates = predict(image, 960)
            # Four fixed 60%-width/height tiles. No annotation-dependent crops.
            tw, th = round(w*0.6), round(h*0.6)
            for y0 in [0, h-th]:
                for x0 in [0, w-tw]:
                    for b, conf in predict(image[y0:y0+th, x0:x0+tw], 960):
                        candidates.append(([(x0+b[0]*tw)/w,(y0+b[1]*th)/h,
                                            (x0+b[2]*tw)/w,(y0+b[3]*th)/h],conf))
            candidates = suppress(candidates)
        boxes = [b for b, _ in candidates]
        tp = matches(boxes, targets, 0.5)
        rows.append(dict(image=path.name, truth=targets, candidates=candidates,
                         tp=tp, fp=len(boxes)-tp, fn=len(targets)-tp))
    metrics = {key: sum(r[key] for r in rows) for key in ['tp','fp','fn']}
    metrics['seconds'] = time.monotonic()-start
    (OUT / f'{profile}-{split}.json').write_text(json.dumps(dict(metrics=metrics,frames=rows),indent=2))
    print(profile,split,metrics,flush=True)
    return metrics


def f1(m):
    return 2*m['tp']/(2*m['tp']+m['fp']+m['fn']) if m['tp'] else 0


if __name__ == '__main__':
    if (OUT / 'comparison.json').exists():
        raise ValueError('Output already exists')
    previous = json.loads((PRIOR/'comparison.json').read_text())['models']['baseline']
    val = {'baseline960':previous['val']['0.02']}
    for profile in ['full1600','full960_plus_tiles960']:
        val[profile] = measure(profile,'val')
    # Fixed selection: highest validation F1 at conf=.02, tie prefers baseline.
    selected = max(val, key=lambda p: f1(val[p]))
    test = {'baseline960':previous['test']['0.02']}
    if selected != 'baseline960':
        test[selected] = measure(selected,'test')
    summary = dict(confidence=0.02, iou=0.5, selected=selected,
                   selection='Highest validation F1, fixed threshold, ties prefer baseline',
                   val=val,test=test,
                   notice='Exploratory previously inspected same-game sample. No verified negatives. Full-frame and fixed tiles, no tracker. Timing includes decode, preprocessing and initial warmup; not a controlled speed benchmark.')
    (OUT/'comparison.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)
