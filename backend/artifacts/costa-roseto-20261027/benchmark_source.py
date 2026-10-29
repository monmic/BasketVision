"""Preselected new-source frames, frozen verifier, paired raw-candidate comparison.

No tiles, tracking, database or application events. Pristine references are
written separately so visual annotations need not follow model proposals.
"""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO
from semantic_verifier import Extractor,probabilities

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('video',type=Path);p.add_argument('weights',type=Path)
p.add_argument('classifier',type=Path);p.add_argument('output',type=Path)
p.add_argument('--start',type=int,default=0)
args=p.parse_args();args.output.mkdir(exist_ok=False)
if args.start<0:raise ValueError('Nonnegative sample start required')
refs=args.output/'reference';refs.mkdir()
model_data=json.loads(args.classifier.read_text())
extractor=Extractor(args.weights)
if extractor.weights_sha256!=model_data['backboneSha256']:raise ValueError('Backbone changed after freezing classifier')
model=YOLO(str(args.weights))
if model.names.get(32)!='sports ball':raise ValueError(model.names)
options=dict(classes=[32],imgsz=960,conf=.02,device='cpu',verbose=False)
model.predict(np.zeros((480,854,3),dtype=np.uint8),**options)
cap=cv2.VideoCapture(str(args.video));fps=cap.get(cv2.CAP_PROP_FPS)
if not cap.isOpened() or fps<=0 or cap.get(cv2.CAP_PROP_FRAME_COUNT)/fps<args.start+60:raise ValueError('Video must cover fixed sample window')
rows=[];detector_seconds=0.;verifier_seconds=0.;originals=[]
try:
    for ordinal,seconds in enumerate(range(args.start,args.start+60,2)):
        index=round(seconds*fps);cap.set(cv2.CAP_PROP_POS_FRAMES,index)
        ok,frame=cap.read()
        if not ok:raise ValueError(index)
        file=refs/f'frame-{index:06d}.png'
        if not cv2.imwrite(str(file),frame):raise ValueError('Reference write failed')
        originals.append((index,frame.copy()))
        started=time.perf_counter();result=model.predict(frame,**options)[0]
        detector_seconds+=time.perf_counter()-started
        candidates=[];crops=[]
        for box in result.boxes:
            x1,y1,x2,y2=box.xyxy[0].tolist()
            left,top=max(0,math.floor(x1)),max(0,math.floor(y1))
            right,bottom=min(frame.shape[1],math.ceil(x2)),min(frame.shape[0],math.ceil(y2))
            if left>=right or top>=bottom:raise ValueError('Invalid predicted crop')
            candidates.append(dict(x1=x1,y1=y1,x2=x2,y2=y2,centerX=(x1+x2)/2,centerY=(y1+y2)/2,
                width=x2-x1,height=y2-y1,confidence=float(box.conf.item()),accepted=False,cropBounds=[left,top,right,bottom]))
            crops.append(frame[top:bottom,left:right])
        started=time.perf_counter();scores=probabilities(extractor.features(crops),model_data)
        verifier_seconds+=time.perf_counter()-started
        for c,score in zip(candidates,scores):c.update(semanticScore=float(score),semanticKept=bool(score>=.5))
        rows.append(dict(frame=index,requestedSeconds=seconds,timestamp=index/fps,width=frame.shape[1],height=frame.shape[0],candidates=candidates,
                         referenceFile=file.name,referenceSha256=hashlib.sha256(file.read_bytes()).hexdigest()))
        print(f'{ordinal+1}/30 frame {index}: {len(candidates)} proposals, {sum(c["semanticKept"] for c in candidates)} kept',flush=True)
finally:cap.release()
report=dict(sourceVideo=args.video.name,source=dict(fps=fps),frames=rows,
    classifierSha256=hashlib.sha256(args.classifier.read_bytes()).hexdigest(),backboneSha256=extractor.weights_sha256,
    sourceVideoSha256=hashlib.sha256(args.video.read_bytes()).hexdigest(),
    inferenceSeconds=detector_seconds,verifierSeconds=verifier_seconds,
    settings=dict(classes=[32],imgsz=960,confidence=.02,device='cpu',threads=2,semanticThreshold=.5),
    window=[args.start,args.start+60],
    notice='Fixed 30 full-frame observations; no tracking/tile or whole-video recall. Model frozen before inference on this window. Source adaptation if this source is listed in model trainingSources.')
with (args.output/'raw.json').open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False)
for start in range(0,len(originals),6):
    sheet=np.zeros((3*510,2*854,3),dtype=np.uint8)
    for n,(index,frame) in enumerate(originals[start:start+6]):
        x,y=n%2*854,n//2*510;sheet[y:y+480,x:x+854]=frame
        cv2.putText(sheet,f'{start+n}: frame {index} t={index/fps:.3f}',(x+6,y+502),0,.65,(255,255,255),1)
    if not cv2.imwrite(str(refs/f'board-{start//6:02d}.jpg'),sheet):raise ValueError('Reference board write failed')
print(json.dumps(dict(detectorSeconds=detector_seconds,verifierSeconds=verifier_seconds,classifierSha256=report['classifierSha256'])),flush=True)
