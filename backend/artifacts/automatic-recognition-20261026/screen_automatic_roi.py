"""Ball-only ROI ablation seeded by a model proposal, never a manual rim label.

Uses the previous ROI experiment's radius of four widths and imgsz=640.
Cached hoop inference cost is reported separately, not hidden in ROI timings.
"""
import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path


def roi_bounds(candidates, width, height):
    valid = [c for c in candidates if all(math.isfinite(c[k]) for k in ('x1','y1','x2','y2','confidence'))
             and c['confidence'] >= .25 and 0 <= c['x1'] < c['x2'] <= width and 0 <= c['y1'] < c['y2'] <= height]
    if not valid: return None
    hoop = max(valid, key=lambda c:c['confidence'])
    x, y = (hoop['x1']+hoop['x2'])/2, (hoop['y1']+hoop['y2'])/2
    radius = 4*(hoop['x2']-hoop['x1'])
    return [max(0, math.floor(x-radius)), max(0, math.floor(y-radius)),
            min(width, math.ceil(x+radius)), min(height, math.ceil(y+radius))]


def main():
    import cv2
    import numpy as np
    import torch
    from ultralytics import YOLO
    sys.path.insert(0, '/scripts')
    from evaluate_ball_clip import evaluate
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('weights', type=Path)
    p.add_argument('reports', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    args.output.mkdir(exist_ok=False)
    model = YOLO(str(args.weights))
    if model.names.get(0) != 'ball': raise ValueError(model.names)
    model.add_callback('on_predict_start', lambda predictor:torch.set_num_threads(2))
    summary = []
    for name in ('near-rim', 'control'):
        base = json.loads((args.reports/f'attalla-{name}.json').read_text())
        cap = cv2.VideoCapture('/videos/'+base['sourceVideo'])
        if not cap.isOpened() or cap.get(cv2.CAP_PROP_FPS) != base['source']['fps']: raise ValueError('Video/FPS mismatch')
        rows, seconds = [], 0.
        options = dict(classes=[0], conf=.02, imgsz=640, device='cpu', verbose=False)
        model.predict(np.zeros((256,256,3), dtype=np.uint8), **options)
        for row in base['frames']:
            cap.set(cv2.CAP_PROP_POS_FRAMES, row['frame'])
            ok, frame = cap.read()
            if not ok: raise ValueError(row['frame'])
            bounds = roi_bounds(row['hoopCandidates'], row['width'], row['height'])
            candidates = []
            if bounds:
                left, top, right, bottom = bounds
                started = time.perf_counter()
                result = model.predict(frame[top:bottom,left:right], **options)[0]
                seconds += time.perf_counter()-started
                for box in result.boxes:
                    x1,y1,x2,y2 = box.xyxy[0].tolist()
                    candidates.append(dict(x1=x1+left, y1=y1+top, x2=x2+left, y2=y2+top,
                        centerX=(x1+x2)/2+left, centerY=(y1+y2)/2+top, confidence=float(box.conf.item()), accepted=False))
            rows.append(dict(row, candidates=candidates, roi=bounds))
        cap.release()
        report = dict(base, frames=rows, inferenceSeconds=seconds,
            settings=dict(base['settings'], inference='automatic-hoop ROI only', imgsz=640,
                          weightsSha256=hashlib.sha256(args.weights.read_bytes()).hexdigest()),
            cachedFullFrameInferenceSeconds=base['inferenceSeconds'])
        if name == 'control':
            annotations=json.loads(Path('/control-annotations.json').read_text())
            report['evaluation']=evaluate(report, annotations)['metrics']['raw']
        with (args.output/f'attalla-{name}.json').open('x') as stream: json.dump(report, stream, indent=2, allow_nan=False)
        item=dict(dataset=name, frames=len(rows), roiFrames=sum(r['roi'] is not None for r in rows),
                  inferenceSeconds=seconds, evaluation=report.get('evaluation'))
        summary.append(item)
        print(json.dumps(item), flush=True)
        if name == 'near-rim':
            context=json.loads(Path('/audit/ball-gap-audit/samples.json').read_text())
            origins={(e['episode'],r['frame']):r['cropOrigin'] for e in context for r in e['samples']}
            cap=cv2.VideoCapture('/videos/'+base['sourceVideo'])
            for eid in range(6):
                sheet=np.zeros((660,1200,3), dtype=np.uint8)
                for n,row in enumerate(r for r in rows if r['episode']==eid):
                    cap.set(cv2.CAP_PROP_POS_FRAMES,row['frame']);ok,frame=cap.read()
                    if not ok: raise ValueError(row['frame'])
                    left,top=origins[(eid,row['frame'])];crop=frame[top:top+200,left:left+200].copy()
                    for i,c in enumerate(row['candidates']):
                        if c['x2']<left or c['x1']>=left+200 or c['y2']<top or c['y1']>=top+200: continue
                        x1,y1,x2,y2=[round(c[k]) for k in ('x1','y1','x2','y2')]
                        cv2.rectangle(crop,(x1-left,y1-top),(x2-left,y2-top),(0,255,255),1)
                        cv2.putText(crop,str(i),(x1-left,max(10,y1-top-3)),0,.35,(0,255,255),1)
                    x,y=n%4*300,n//4*330;sheet[y:y+300,x:x+300]=cv2.resize(crop,(300,300))
                    cv2.putText(sheet,f'f{row["frame"]} ROI={row["roi"] is not None}',(x+2,y+320),0,.45,(255,255,255),1)
                if not cv2.imwrite(str(args.output/f'episode-{eid:02d}.jpg'),sheet): raise ValueError('Write failed')
            cap.release()
    with (args.output/'summary.json').open('x') as stream: json.dump(summary,stream,indent=2)


if __name__ == '__main__': main()
