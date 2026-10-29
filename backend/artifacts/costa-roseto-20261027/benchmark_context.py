"""Frozen ball/hoop ROI experiment on the exact same new-source sample frames."""
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

sys.path.insert(0,'/previous')
from screen_automatic_roi import roi_bounds

HERE=Path(__file__).resolve().parent
source=HERE/'benchmark';out=HERE/'context';out.mkdir(exist_ok=False)
read=lambda p:json.loads(p.read_text())
reference=read(source/'raw.json')
weights=Path('/specialist/attalla-ball-hoop.pt')
if hashlib.sha256(weights.read_bytes()).hexdigest()!='40f3e596652a427ba290b3f72384e49aed12caf1a8ae41beaef4a8fffcf09fa3':raise ValueError('Changed specialist checkpoint')
model=YOLO(str(weights))
if model.names!={0:'ball',1:'hoop'}:raise ValueError(model.names)
model.add_callback('on_predict_start',lambda predictor:torch.set_num_threads(2))
model.predict(np.zeros((480,854,3),np.uint8),classes=[1],imgsz=960,conf=.02,device='cpu',verbose=False)
model.predict(np.zeros((256,256,3),np.uint8),classes=[0],imgsz=640,conf=.02,device='cpu',verbose=False)
rows=[];hoop_seconds=0.;roi_seconds=0.
for row in reference['frames']:
    image=cv2.imread(str(source/'reference'/row['referenceFile']))
    if image is None or hashlib.sha256((source/'reference'/row['referenceFile']).read_bytes()).hexdigest()!=row['referenceSha256']:raise ValueError('Changed reference frame')
    started=time.perf_counter();result=model.predict(image,classes=[1],imgsz=960,conf=.02,device='cpu',verbose=False)[0]
    hoop_seconds+=time.perf_counter()-started
    hoops=[]
    for b in result.boxes:
        x1,y1,x2,y2=b.xyxy[0].tolist();hoops.append(dict(x1=x1,y1=y1,x2=x2,y2=y2,confidence=float(b.conf.item())))
    bounds=roi_bounds(hoops,row['width'],row['height']);candidates=[]
    if bounds:
        left,top,right,bottom=bounds;started=time.perf_counter()
        result=model.predict(image[top:bottom,left:right],classes=[0],imgsz=640,conf=.02,device='cpu',verbose=False)[0]
        roi_seconds+=time.perf_counter()-started
        for b in result.boxes:
            x1,y1,x2,y2=b.xyxy[0].tolist();x1+=left;x2+=left;y1+=top;y2+=top
            candidates.append(dict(x1=x1,y1=y1,x2=x2,y2=y2,centerX=(x1+x2)/2,centerY=(y1+y2)/2,
                                   width=x2-x1,height=y2-y1,confidence=float(b.conf.item()),accepted=False))
    rows.append(dict(row,candidates=candidates,hoopCandidates=hoops,automaticRoi=bounds))
report=dict(reference,frames=rows,settings=dict(classes=[0,1],hoopImgsz=960,roiImgsz=640,confidence=.02,hoopThreshold=.25,roiRadiusWidths=4),
            weightsSha256=hashlib.sha256(weights.read_bytes()).hexdigest(),inferenceSeconds=hoop_seconds+roi_seconds,
            stagesSeconds=dict(hoop=hoop_seconds,roi=roi_seconds),
            notice='Same preselected 30 frames. Frozen specialist and ROI geometry from previous source; no manual calibration. No event inference or tracking. Separate from baseline semantic-verifier experiment.')
for stale in ('classifierSha256','backboneSha256','verifierSeconds'):report.pop(stale,None)
with (out/'raw.json').open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False)
for start in range(0,len(rows),6):
    sheet=np.zeros((3*510,2*854,3),np.uint8)
    for n,row in enumerate(rows[start:start+6]):
        image=cv2.imread(str(source/'reference'/row['referenceFile']))
        if row['hoopCandidates']:
            top=max(row['hoopCandidates'],key=lambda c:c['confidence'])
            cv2.rectangle(image,(round(top['x1']),round(top['y1'])),(round(top['x2']),round(top['y2'])),(0,255,255),2)
        x,y=n%2*854,n//2*510;sheet[y:y+480,x:x+854]=image
        caption=f'f{row["frame"]} ROI={row["automaticRoi"] is not None}'
        if row['hoopCandidates']:caption+=f' top={top["confidence"]:.3f}'
        cv2.putText(sheet,caption,(x+6,y+502),0,.65,(255,255,255),1)
    if not cv2.imwrite(str(out/f'hoop-board-{start//6:02d}.jpg'),sheet):raise ValueError('Write failed')
print(json.dumps(dict(frames=len(rows),roiFrames=sum(r['automaticRoi'] is not None for r in rows),candidates=sum(len(r['candidates']) for r in rows),stagesSeconds=report['stagesSeconds'])))
