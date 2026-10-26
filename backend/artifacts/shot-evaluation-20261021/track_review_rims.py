"""Offline template registration proposals; never changes worker calibration."""
import json
import math
import argparse
from pathlib import Path
import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / 'temporal-review'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--original-report', type=Path)
args = parser.parse_args()
if args.original_report:
    OUTPUT = HERE / 'original-temporal-review'
REVIEW = OUTPUT / 'rim-review-v2'
# Original 854x480 pixels, visually selected from the central reference images.
# (rim x, rim y, rim width, backboard template x1, y1, x2, y2)
SEEDS = {0: (256, 173, 26, 210, 125, 273, 184),
         1: (306, 178, 22, 260, 130, 319, 185),
         2: (240, 161, 24, 186, 107, 254, 174),
         3: (391, 165, 25, 378, 111, 442, 175),
         4: (504, 157, 30, 457, 107, 525, 172),
         5: (380, 168, 24, 361, 117, 425, 177)}
manifest = json.loads((OUTPUT / 'manifest.json').read_text())
video = cv2.VideoCapture('/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4')
results = []
try:
    REVIEW.mkdir(exist_ok=False)
    for episode in manifest:
        eid = episode['episode']
        rx, ry, rw, x1, y1, x2, y2 = SEEDS[eid]
        reference_path = (OUTPUT / 'episode-00-frame-013040.jpg' if eid == 0
                          else HERE / f'episode-{eid:02d}-1.jpg')
        reference = cv2.imread(str(reference_path))
        if reference.shape[:2] != (480, 854):
            raise ValueError('Seed coordinates require 854x480 source')
        template = cv2.cvtColor(reference[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        if eid == 0:
            original = json.loads(args.original_report.read_text(encoding='utf-8-sig'))
            saved = {'frames': [dict(frame=round(p['timestamp']*episode['fps']), candidates=[p])
                                for p in original['ballTrack']]}
        else:
            saved = json.loads((HERE / f'episode-{eid:02d}-ball.json').read_text())
        indices = sorted({r['frame'] for r in episode['frames']} |
                         {r['frame'] for r in saved['frames'] if any(c.get('accepted') for c in r['candidates'])})
        rows = []
        sheet = np.zeros((math.ceil(len(indices)/6)*150, 6*200, 3), dtype=np.uint8)
        for n, index in enumerate(indices):
            video.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = video.read()
            if not ok:
                raise RuntimeError(index)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            best = None
            for scale in [.90, .95, 1., 1.05, 1.10]:
                scaled = cv2.resize(template, None, fx=scale, fy=scale)
                response = cv2.matchTemplate(gray[:240], scaled, cv2.TM_CCOEFF_NORMED)
                _, score, _, location = cv2.minMaxLoc(response)
                if best is None or score > best[0]:
                    best = score, location, scale
            score, (tx, ty), scale = best
            cx, cy, width = tx+(rx-x1)*scale, ty+(ry-y1)*scale, rw*scale
            rows.append(dict(frame=index, timestamp=index/episode['fps'], x=cx, y=cy,
                             width=width, templateScore=score, scale=scale))
            left, top = max(0, round(cx)-50), max(0, round(cy)-55)
            crop = frame[top:top+100, left:left+100].copy()
            cv2.line(crop, (round(cx-width/2)-left, round(cy)-top),
                     (round(cx+width/2)-left, round(cy)-top), (0,255,0), 1)
            tile = cv2.resize(crop, (200,120))
            sx, sy = n%6*200, n//6*150
            sheet[sy:sy+120, sx:sx+200] = tile
            cv2.putText(sheet, f'{index/episode["fps"]:.3f} q{score:.2f}', (sx+2,sy+140), 0, .42, (255,255,255), 1)
        path = REVIEW / f'episode-{eid:02d}-rim-proposals.jpg'
        if path.exists() or not cv2.imwrite(str(path), sheet):
            raise RuntimeError(f'Cannot create: {path}')
        results.append(dict(episode=eid, seed=SEEDS[eid], samples=rows,
                            status='proposal_requires_visual_review'))
    with (REVIEW / 'rim-proposals.json').open('x', encoding='utf-8') as stream:
        json.dump(results, stream, indent=2, allow_nan=False)
    print(f'Registered {sum(len(r["samples"]) for r in results)} review/accepted frames')
finally:
    video.release()
