"""Show every newly accepted observation, including possible background objects."""
import json
import math
import argparse
from pathlib import Path
import cv2
import numpy as np

HERE=Path(__file__).resolve().parent
OUTPUT=HERE/'ball-gap-audit/tile-cadence'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--roi',action='store_true',help='Review rim ROI trial instead of tile cadence')
parser.add_argument('--raw-roi',action='store_true',help='Show all raw ROI proposals, including rejected/background candidates')
args=parser.parse_args()
if args.roi or args.raw_roi:
    OUTPUT=HERE/'rim-roi-trial'
    args.roi=True
prefix='roi-candidates' if args.raw_roi else 'new-accepted'
cap=cv2.VideoCapture('/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4')
records=[]
tiles=[]
try:
    for eid in range(6):
        base=json.loads((OUTPUT/(f'input-{eid:02d}.json' if args.roi else f'baseline-{eid:02d}.json')).read_text())
        variant=json.loads((OUTPUT/(f'raw-{eid:02d}.json' if args.raw_roi else f'replayed-{eid:02d}.json' if args.roi else f'every-frame-{eid:02d}.json')).read_text())
        old={r['frame']:r for r in base['frames']}
        for row in variant['frames']:
            newly=[c for c in row['candidates'] if c.get('accepted') and not any(
                b['accepted'] and abs(b['centerX']-c['centerX'])<2 and abs(b['centerY']-c['centerY'])<2
                for b in old[row['frame']]['candidates'])]
            if args.raw_roi:
                newly=row.get('rimRoi',{}).get('candidates',[])
            if not newly:
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES,row['frame'])
            ok,frame=cap.read()
            if not ok:
                raise RuntimeError(row['frame'])
            for c in newly:
                left,top=max(0,round(c['centerX'])-50),max(0,round(c['centerY'])-50)
                crop=frame[top:top+100,left:left+100].copy()
                cv2.rectangle(crop,(round(c['x1'])-left,round(c['y1'])-top),
                              (round(c['x2'])-left,round(c['y2'])-top),(0,255,0),1)
                tile=np.zeros((240,240,3),dtype=np.uint8)
                tile[:200,:200]=cv2.resize(crop,(200,200))
                index=len(records)
                cv2.putText(tile,f'{index} E{eid} {row["timestamp"]:.3f}',(2,225),0,.45,(255,255,255),1)
                tiles.append(tile)
                records.append(dict(index=index,episode=eid,frame=row['frame'],timestamp=row['timestamp'],candidate=c,review=None))
    for offset in range(0,len(tiles),30):
        chunk=tiles[offset:offset+30]
        sheet=np.zeros((math.ceil(len(chunk)/6)*240,1440,3),dtype=np.uint8)
        for n,tile in enumerate(chunk):
            sheet[n//6*240:(n//6+1)*240,n%6*240:(n%6+1)*240]=tile
        path=OUTPUT/f'{prefix}-{offset//30+1:02d}.jpg'
        if path.exists() or not cv2.imwrite(str(path),sheet):
            raise RuntimeError(path)
    with (OUTPUT/f'{prefix}.json').open('x') as stream:
        json.dump(records,stream,indent=2)
    print(f'{len(records)} {prefix} observations, {math.ceil(len(tiles)/30)} boards')
finally:
    cap.release()
