"""Visual check of highest-confidence hoop proposals, without manual ROI at inference.

Boxes describe the model's hoop/net object, not an annotated physical rim line.
"""
import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('report', type=Path)
parser.add_argument('video', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
report = json.loads(args.report.read_text())
args.output.mkdir(exist_ok=False)
cap = cv2.VideoCapture(str(args.video))
if not cap.isOpened() or not math.isclose(cap.get(cv2.CAP_PROP_FPS), report['source']['fps']):
    raise ValueError('Video/FPS mismatch')
try:
    for episode in sorted({r.get('episode', 0) for r in report['frames']}):
        rows = [r for r in report['frames'] if r.get('episode', 0) == episode]
        sheet = np.zeros((math.ceil(len(rows)/2)*265, 854, 3), dtype=np.uint8)
        for n, row in enumerate(rows):
            cap.set(cv2.CAP_PROP_POS_FRAMES, row['frame'])
            ok, frame = cap.read()
            if not ok: raise ValueError(row['frame'])
            candidates = row['hoopCandidates']
            index = max(range(len(candidates)), key=lambda i:candidates[i]['confidence']) if candidates else None
            if index is not None:
                c = candidates[index]
                cv2.rectangle(frame, (round(c['x1']), round(c['y1'])), (round(c['x2']), round(c['y2'])), (0,255,255), 2)
                caption = f'f{row["frame"]} top={index} conf={c["confidence"]:.3f} proposals={len(candidates)}'
            else: caption = f'f{row["frame"]} NO HOOP'
            x,y=n%2*427,n//2*265
            sheet[y:y+240,x:x+427]=cv2.resize(frame,(427,240))
            cv2.putText(sheet,caption,(x+3,y+257),0,.4,(255,255,255),1)
        if not cv2.imwrite(str(args.output/f'episode-{episode:02d}.jpg'),sheet): raise RuntimeError('Image write failed')
finally:
    cap.release()
