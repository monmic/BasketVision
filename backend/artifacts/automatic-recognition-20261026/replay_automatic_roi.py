"""Six continuous episodes: baseline candidates plus specialist automatic ROI.

No database, manual ROI, event labels, tracker tuning or production changes.
"""
import argparse
import copy
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

sys.path[:0] = ['/app', '/scripts']
import worker as w
from replay_ball_tracker import replay
from screen_automatic_roi import roi_bounds

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('weights',type=Path)
p.add_argument('audit',type=Path)
p.add_argument('output',type=Path)
args=p.parse_args()
args.output.mkdir(exist_ok=False)
model=YOLO(str(args.weights))
if model.names!={0:'ball',1:'hoop'}:raise ValueError(model.names)
model.add_callback('on_predict_start',lambda predictor:torch.set_num_threads(2))
model.predict(np.zeros((480,854,3),dtype=np.uint8),classes=[1],imgsz=960,conf=.02,device='cpu',verbose=False)
model.predict(np.zeros((256,256,3),dtype=np.uint8),classes=[0],imgsz=640,conf=.02,device='cpu',verbose=False)
summary=[]
for eid in range(6):
    base=json.loads((args.audit/f'ball-gap-audit/tile-cadence/baseline-{eid:02d}.json').read_text())
    cap=cv2.VideoCapture('/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4')
    if not cap.isOpened() or cap.get(cv2.CAP_PROP_FPS)!=30:raise ValueError('Video/FPS mismatch')
    cap.set(cv2.CAP_PROP_POS_FRAMES,base['frames'][0]['frame'])
    rows=[];times=dict(decode=0.,hoop=0.,roi=0.,merge=0.);roi_frames=0
    started=time.perf_counter()
    for n,row in enumerate(base['frames']):
        if row['frame']!=base['frames'][0]['frame']+n:raise ValueError('Non-contiguous baseline')
        t=time.perf_counter();ok,frame=cap.read();times['decode']+=time.perf_counter()-t
        if not ok:raise ValueError(row['frame'])
        t=time.perf_counter()
        result=model.predict(frame,classes=[1],imgsz=960,conf=.02,device='cpu',verbose=False)[0]
        times['hoop']+=time.perf_counter()-t
        hoops=w._extract_boxes(result,1,'automatic-hoop',row['timestamp'])
        bounds=roi_bounds(hoops,frame.shape[1],frame.shape[0]);extra=[]
        if bounds:
            roi_frames+=1;left,top,right,bottom=bounds;t=time.perf_counter()
            result=model.predict(frame[top:bottom,left:right],classes=[0],imgsz=640,conf=.02,device='cpu',verbose=False)[0]
            times['roi']+=time.perf_counter()-t
            extra=w._extract_boxes(result,0,'automatic-hoop-roi',row['timestamp'],left,top)
        t=time.perf_counter()
        candidates=w.merge_ball_candidates(copy.deepcopy(row['candidates'])+extra)
        times['merge']+=time.perf_counter()-t
        rows.append(dict(row,candidates=candidates,automaticHoop=hoops,automaticRoi=bounds,width=854,height=480))
    cap.release()
    report=dict(base,frames=rows,sourceVideo='35b68704-541f-4c6d-b8ab-45228266102a.mp4',
                automaticRoiExperiment=dict(elapsedSeconds=time.perf_counter()-started,stagesSeconds=times,roiFrames=roi_frames,
                    notice='Incremental work using cached baseline candidates; not end-to-end runtime. No manual calibration.'))
    for name,data in [('raw',report),('replay',replay(report,worker=Path('/app/worker.py')))]:
        with (args.output/f'{name}-{eid:02d}.json').open('x') as stream:json.dump(data,stream,allow_nan=False)
    item=dict(episode=eid,frames=len(rows),roiFrames=roi_frames,incrementalSeconds=report['automaticRoiExperiment']['elapsedSeconds'],
              stagesSeconds=times,baselineAccepted=sum(c.get('accepted',False) for r in base['frames'] for c in r['candidates']),
              experimentAccepted=sum(c.get('accepted',False) for r in data['frames'] for c in r['candidates']))
    summary.append(item);print(json.dumps(item),flush=True)
with (args.output/'summary.json').open('x') as stream:json.dump(summary,stream,indent=2)
