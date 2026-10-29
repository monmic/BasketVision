"""Same raw baseline stream, auxiliary strong-hit eligibility, isolated trackers."""
import copy
import hashlib
import json
import sys
import time
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO

sys.path[:0]=['/app','/scripts']
import worker as w
from replay_ball_tracker import load_tracker
from evaluate_ball_clip import iou
from preserved_score_hook import PreservedScoreHook

BASE=Path(__file__).resolve().parent;root=BASE/'detector-preserved'
read=lambda path:json.loads(Path(path).read_text())
if not read(root/'strong-gate/decision.json')['eligibleForContinuousReplay']:raise ValueError('Strong sample gate failed')
out=root/'continuous';out.mkdir(exist_ok=False)
frozen=read(root/'training/frozen.json');best=root/'training/weights/best.pt'
assert hashlib.sha256(best.read_bytes()).hexdigest()==frozen['selectedWeightsSha256']
threshold=read(root/'operating-points/selection.json')['selected']['strong']
settings={k:v for k,v in vars(w).items() if k.startswith('BALL_') and isinstance(v,(str,int,float,bool))}
prototype=load_tracker(settings,worker=BASE/'worker-semantic-prototype.py')
trackers=dict(baseline=w.BallTracker(),gated=prototype['BallTracker']())
model=w.get_ball_model();blank=np.zeros((480,854,3),np.uint8)
w.detect_ball_full(model,blank,0);w.detect_ball_tiled(model,blank,0)
hook=PreservedScoreHook(model,YOLO(str(best)),threshold)
cap=cv2.VideoCapture('/video.mp4');fps=cap.get(cv2.CAP_PROP_FPS)
if not cap.isOpened() or fps<=0:raise ValueError('Invalid source')
first,last=round(60*fps),round(120*fps);cap.set(cv2.CAP_PROP_POS_FRAMES,first)
rows={name:[] for name in trackers};times=dict(decode=0.,full=0.,tiled=0.,association=0.,tracking=0.)
started=time.perf_counter()
xyxy=lambda c:[c[k] for k in ['x1','y1','x2','y2']]
try:
    for count,index in enumerate(range(first,last),1):
        t=time.perf_counter();ok,frame=cap.read();times['decode']+=time.perf_counter()-t
        if not ok:raise ValueError(index)
        timestamp=index/fps
        t=time.perf_counter()
        result=model.predict(frame,classes=[32],conf=w.BALL_CONFIDENCE,imgsz=w.BALL_IMGSZ,verbose=False)[0]
        candidates=w._extract_boxes(result,32,'full',timestamp);support=hook.native_boxes(result)
        times['full']+=time.perf_counter()-t
        if w.BALL_USE_TILES and count%w.BALL_TILE_STRIDE==0:
            t=time.perf_counter();height,width=frame.shape[:2]
            ox,oy=int(width*w.BALL_TILE_OVERLAP/2),int(height*w.BALL_TILE_OVERLAP/2);mx,my=width//2,height//2
            tiles=[(0,0,min(width,mx+ox),min(height,my+oy)),(max(0,mx-ox),0,width,min(height,my+oy)),
                   (0,max(0,my-oy),min(width,mx+ox),height),(max(0,mx-ox),max(0,my-oy),width,height)]
            tiled=[]
            for number,(left,top,right,bottom) in enumerate(tiles,1):
                crop=frame[top:bottom,left:right]
                result=model.predict(crop,classes=[32],conf=w.BALL_CONFIDENCE,imgsz=w.BALL_TILE_IMGSZ,verbose=False)[0]
                tiled+=w._extract_boxes(result,32,f'tile{number}',timestamp,left,top)
                support+=hook.native_boxes(result,(left,top))
            candidates+=w._nms_ball_candidates(tiled,w.BALL_CONFIDENCE)
            times['tiled']+=time.perf_counter()-t
        candidates=w.merge_ball_candidates(candidates)
        t=time.perf_counter()
        for c in candidates:c['semanticBall']=any(iou(xyxy(c),xyxy(s))>=.5 for s in support)
        times['association']+=time.perf_counter()-t
        t=time.perf_counter()
        for name,tracker in trackers.items():
            copied=copy.deepcopy(candidates)
            for c in copied:
                c['accepted']=False
                if c['qualityScore']<w.BALL_TRACK_UPDATE_MIN_SCORE:c['rejectionReason']='score_below_track_update_threshold'
            tracker.update([c for c in copied if c['qualityScore']>=w.BALL_TRACK_UPDATE_MIN_SCORE],timestamp)
            rows[name].append(dict(frame=index,timestamp=timestamp,width=frame.shape[1],height=frame.shape[0],candidates=copied))
        times['tracking']+=time.perf_counter()-t
        if count%150==0:print(f'{count}/{last-first} '+str({k:sum(c.get('accepted',False) for r in v for c in r['candidates']) for k,v in rows.items()}),flush=True)
finally:cap.release();hook.close()
elapsed=time.perf_counter()-started
for name,frames in rows.items():
    report=dict(sourceVideo='ad0b3783-9ef0-49b9-8645-a8fac9540389-020ad1c9868d47e48fe7193d831fc33f.mp4',
        source=dict(fps=fps),frames=frames,settings=settings,start=first/fps,end=last/fps,
        classifierWeightsSha256=frozen['selectedWeightsSha256'],strongRawThreshold=threshold,
        workerSha256=hashlib.sha256(Path('/app/worker.py').read_bytes()).hexdigest(),
        notice='Same raw baseline proposals; auxiliary classifier evidence only changes strong-hit eligibility. No database/events or runtime worker edits.')
    (out/f'{name}.json').write_text(json.dumps(report,allow_nan=False))
summary=dict(frames=last-first,accepted={name:sum(c.get('accepted',False) for r in frames for c in r['candidates']) for name,frames in rows.items()},
    stagesSeconds=times,auxiliarySecondsIncludedInDetectorStages=hook.seconds,elapsedSeconds=elapsed,
    notice='One shared CNN inference pass, auxiliary final convolutions/decoding and two trackers. Counts are not accuracy; paired elapsed is not either full application job runtime.')
(out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
