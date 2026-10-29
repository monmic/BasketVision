"""Review saved raw candidates on exact dense source frames near the rim."""
import json
import math
import argparse
from pathlib import Path
import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / 'ball-gap-audit'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--profile', choices=['baseline','every-frame','rim-roi'])
args=parser.parse_args()
if args.profile:
    from review_ball_gaps import SELECTED
WINDOWS = {0:(435.1,435.9), 1:(593.2,594.8), 2:(1175.2,1176.4),
           3:(1190.9,1192.3), 4:(1198.5,1199.8), 5:(1207.,1208.3)}
summaries = []
for eid, (start, end) in WINDOWS.items():
    folder = HERE / ('original-temporal-review' if eid == 0 else 'temporal-review')
    manifest = next(e for e in json.loads((folder/'manifest.json').read_text()) if e['episode'] == eid)
    registration = next(e for e in json.loads((folder/'rim-review-v2/rim-proposals.json').read_text()) if e['episode'] == eid)
    rims = {r['frame']:r for r in registration['samples']}
    report = json.loads((OUTPUT/'original-raw.json' if eid == 0 else HERE/f'episode-{eid:02d}-ball.json').read_text())
    if args.profile:
        report_path=(HERE/f'rim-roi-trial/replayed-{eid:02d}.json' if args.profile=='rim-roi'
                     else OUTPUT/f'tile-cadence/{args.profile}-{eid:02d}.json')
        report=json.loads(report_path.read_text())
    rows = {r['frame']:r for r in report['frames']}
    selected = [r for r in manifest['frames'] if start-0.02 <= r['timestamp'] <= end+0.02 and r['frame'] in rows]
    if args.profile:
        selected=[r for r in selected if r['frame'] in SELECTED[eid]]
    sheet = np.zeros((math.ceil(len(selected)/4)*330,1200,3), dtype=np.uint8)
    samples = []
    for n, row in enumerate(selected):
        frame = cv2.imread(str(folder/row['file']))
        if frame is None:
            raise RuntimeError(row['file'])
        rim = rims[row['frame']]
        left, top = max(0,round(rim['x'])-100), max(0,round(rim['y'])-100)
        crop = frame[top:top+200,left:left+200].copy()
        candidates = rows[row['frame']]['candidates']
        for index, c in enumerate(candidates):
            x1,y1,x2,y2 = [round(c[k]) for k in ('x1','y1','x2','y2')]
            if x2 < left or x1 >= left+200 or y2 < top or y1 >= top+200:
                continue
            color = (0,255,0) if c.get('accepted') else (0,0,255)
            cv2.rectangle(crop,(x1-left,y1-top),(x2-left,y2-top),color,1)
            cv2.putText(crop,str(index),(x1-left,max(10,y1-top-3)),0,.35,color,1)
        x,y = n%4*300,n//4*330
        sheet[y:y+300,x:x+300] = cv2.resize(crop,(300,300))
        cv2.putText(sheet,f'{row["timestamp"]:.3f} f{row["frame"]}',(x+2,y+320),0,.45,(255,255,255),1)
        samples.append(dict(frame=row['frame'],timestamp=row['timestamp'],cropOrigin=[left,top],
                            candidates=candidates, review=None))
    path = OUTPUT/f'episode-{eid:02d}-audit{("-"+args.profile) if args.profile else ""}.jpg'
    if path.exists() or not cv2.imwrite(str(path),sheet):
        raise RuntimeError(f'Cannot create {path}')
    summaries.append(dict(episode=eid, window=[start,end], samples=samples))
with (OUTPUT/f'samples{("-"+args.profile) if args.profile else ""}.json').open('x') as stream:
    json.dump(summaries,stream,indent=2,allow_nan=False)
print(f'Created six audit boards, {sum(len(e["samples"]) for e in summaries)} sampled frames')
