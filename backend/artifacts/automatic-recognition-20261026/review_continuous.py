"""Prepare exhaustive accepted-box review and compare unchanged shot rules.

Reviewed rim geometry is used ONLY to evaluate ball trajectories, not to seed
the automatic detector. This is not an end-to-end automatic shot benchmark.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path[:0]=['/app','/scripts']
from diagnose_reviewed_shots import diagnose

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('audit',type=Path)
p.add_argument('experiment',type=Path)
p.add_argument('output',type=Path)
args=p.parse_args();args.output.mkdir(exist_ok=False)
read=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
calibration=read(args.audit/'rim-roi-trial/calibration.json')
episodes=[];accepted=[]
for eid in range(6):
    baseline=read(args.audit/f'ball-gap-audit/tile-cadence/baseline-{eid:02d}.json')
    variant=read(args.experiment/f'replay-{eid:02d}.json')
    keys=next(e['keyframes'] for e in calibration['episodes'] if e['id']==eid)
    item=dict(episode=eid,manualTimestamp=baseline.get('manualTimestamp'),profiles={})
    for name,report in [('baseline',baseline),('automaticRoi',variant)]:
        points=[c for row in report['frames'] for c in row['candidates'] if c.get('accepted')]
        longest=0
        for tid in {c['trackId'] for c in points}:
            previous=-math.inf;run=0
            for t in sorted({c['timestamp'] for c in points if c['trackId']==tid}):
                run=run+1 if t-previous<=.250001 else 1
                longest=max(longest,run);previous=t
        item['profiles'][name]=dict(accepted=len(points),longestContinuousRun=longest,
                                   shotCandidates=diagnose(points,keys,854,480))
    episodes.append(item)
    for row in variant['frames']:
        for c in row['candidates']:
            if c.get('accepted'):accepted.append(dict(index=len(accepted),episode=eid,frame=row['frame'],**c))
    print(json.dumps(item),flush=True)
with (args.output/'comparison.json').open('x') as stream:json.dump(episodes,stream,indent=2)
with (args.output/'accepted-manifest.json').open('x') as stream:json.dump(accepted,stream,indent=2)
cap=cv2.VideoCapture('/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4')
try:
    for start in range(0,len(accepted),40):
        sheet=np.zeros((5*150,8*150,3),dtype=np.uint8)
        for n,c in enumerate(accepted[start:start+40]):
            cap.set(cv2.CAP_PROP_POS_FRAMES,c['frame']);ok,frame=cap.read()
            if not ok:raise ValueError(c['frame'])
            radius=max(24,math.ceil(max(c['width'],c['height'])*2))
            cx,cy=round(c['centerX']),round(c['centerY'])
            left,top=max(0,cx-radius),max(0,cy-radius)
            crop=frame[top:min(frame.shape[0],cy+radius),left:min(frame.shape[1],cx+radius)].copy()
            cv2.rectangle(crop,(round(c['x1'])-left,round(c['y1'])-top),(round(c['x2'])-left,round(c['y2'])-top),(0,255,255),1)
            x,y=n%8*150,n//8*150;sheet[y:y+120,x:x+150]=cv2.resize(crop,(150,120))
            cv2.putText(sheet,f'{c["index"]} E{c["episode"]} t{c["trackId"]}',(x+2,y+132),0,.35,(255,255,255),1)
            cv2.putText(sheet,f'{c["timestamp"]:.3f}s',(x+2,y+146),0,.35,(255,255,255),1)
        if not cv2.imwrite(str(args.output/f'accepted-{start//40:02d}.jpg'),sheet):raise ValueError('Image write failed')
finally:cap.release()
