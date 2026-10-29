"""Paired continuous ball tracking: semantic evidence gates new/strong hits only.

Identical raw full/tiled proposals and existing weak-update constraints. Frozen
classifier from [0,60) development, compare [60,120). No database or events.
"""
import copy
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path[:0]=['/app','/scripts']
import worker as w
from replay_ball_tracker import load_tracker
from semantic_verifier import Extractor,probabilities

HERE=Path(__file__).resolve().parent
out=HERE/'continuous';out.mkdir(exist_ok=False)
classifier_path=HERE/'adapted-training-corrected/classifier.json'
classifier=json.loads(classifier_path.read_text())
extractor=Extractor('/model.pt')
if extractor.weights_sha256!=classifier['backboneSha256']:raise ValueError('Frozen backbone mismatch')
settings={k:v for k,v in vars(w).items() if k.startswith('BALL_') and isinstance(v,(str,int,float,bool))}
module=load_tracker(settings,worker=HERE/'worker-semantic-prototype.py')
trackers={'baseline':w.BallTracker(),'semantic':module['BallTracker']()}
model=w.get_ball_model()
w.detect_ball_full(model,np.zeros((480,854,3),np.uint8),0)
w.detect_ball_tiled(model,np.zeros((480,854,3),np.uint8),0)
cap=cv2.VideoCapture('/video.mp4');fps=cap.get(cv2.CAP_PROP_FPS)
if not cap.isOpened() or fps<=0:raise ValueError('Invalid video')
first,last=round(60*fps),round(120*fps);cap.set(cv2.CAP_PROP_POS_FRAMES,first)
rows={k:[] for k in trackers};times=dict(decode=0.,full=0.,tiled=0.,verifier=0.,tracking=0.)
started=time.perf_counter()
try:
    for count,index in enumerate(range(first,last),1):
        t=time.perf_counter();ok,frame=cap.read();times['decode']+=time.perf_counter()-t
        if not ok:raise ValueError(index)
        timestamp=index/fps
        t=time.perf_counter();candidates=w.detect_ball_full(model,frame,timestamp);times['full']+=time.perf_counter()-t
        if w.BALL_USE_TILES and count%w.BALL_TILE_STRIDE==0:
            t=time.perf_counter();candidates+=w.detect_ball_tiled(model,frame,timestamp);times['tiled']+=time.perf_counter()-t
        candidates=w.merge_ball_candidates(candidates)
        crops=[]
        for c in candidates:
            left,top=max(0,math.floor(c['x1'])),max(0,math.floor(c['y1']))
            right,bottom=min(frame.shape[1],math.ceil(c['x2'])),min(frame.shape[0],math.ceil(c['y2']))
            if left>=right or top>=bottom:raise ValueError('Invalid proposal crop')
            crops.append(frame[top:bottom,left:right])
        t=time.perf_counter();scores=probabilities(extractor.features(crops),classifier);times['verifier']+=time.perf_counter()-t
        for c,score in zip(candidates,scores):c.update(semanticScore=float(score),semanticBall=bool(score>=.5))
        t=time.perf_counter()
        for name,tracker in trackers.items():
            copied=copy.deepcopy(candidates)
            for c in copied:
                c['accepted']=False
                if c['qualityScore']<w.BALL_TRACK_UPDATE_MIN_SCORE:c['rejectionReason']='score_below_track_update_threshold'
            tracker.update([c for c in copied if c['qualityScore']>=w.BALL_TRACK_UPDATE_MIN_SCORE],timestamp)
            rows[name].append(dict(frame=index,timestamp=timestamp,width=frame.shape[1],height=frame.shape[0],candidates=copied))
        times['tracking']+=time.perf_counter()-t
        if count%150==0:print(f'{count}/{last-first} frames, accepted '+str({k:sum(c.get('accepted',False) for r in v for c in r['candidates']) for k,v in rows.items()}),flush=True)
finally:cap.release()
elapsed=time.perf_counter()-started
summary={}
for name,frames in rows.items():
    report=dict(sourceVideo='ad0b3783-9ef0-49b9-8645-a8fac9540389-020ad1c9868d47e48fe7193d831fc33f.mp4',
        source=dict(fps=fps),start=first/fps,end=last/fps,frames=frames,settings=settings,
        classifierSha256=hashlib.sha256(classifier_path.read_bytes()).hexdigest(),
        workerSha256=hashlib.sha256(Path('/app/worker.py').read_bytes()).hexdigest(),
        notice='Paired continuous diagnostic; semantic model only changes new-track/strong-hit eligibility. No manual ROI, events or database writes.')
    with (out/f'{name}.json').open('x') as stream:json.dump(report,stream,allow_nan=False)
    summary[name]=dict(accepted=sum(c['accepted'] for r in frames for c in r['candidates']),frames=len(frames))
summary.update(stagesSeconds=times,elapsedSeconds=elapsed,classifierSha256=report['classifierSha256'],
    notice='One shared detector pass, two trackers and one verifier. Stage times isolate incremental verifier cost; total is paired diagnostic, not either full application job.')
with (out/'summary.json').open('x') as stream:json.dump(summary,stream,indent=2)
print(json.dumps(summary),flush=True)
