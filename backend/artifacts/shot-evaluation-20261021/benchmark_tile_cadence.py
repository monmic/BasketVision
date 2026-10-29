"""Paired local CPU benchmark: only tiled inference cadence changes."""
import json
import sys
import time
from pathlib import Path
import cv2
import numpy as np

sys.path.insert(0, '/app')
import worker as w

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / 'ball-gap-audit/tile-cadence'
OUTPUT.mkdir(exist_ok=False)
episodes = [dict(episode=0,startSeconds=433,endSeconds=436,manualTimestamp=434.68)] + json.loads((HERE/'episodes.json').read_text())
settings = json.loads((HERE/'episode-01-ball.json').read_text())['settings']
for name,value in settings.items():
    if name != 'BALL_MODEL':
        setattr(w,name,value)
model = w.get_ball_model()
# Initialize backend and thread limits before timing either profile.
w.detect_ball_full(model,np.zeros((480,854,3),dtype=np.uint8),0)
summary = []
for profile,stride in [('baseline',3),('every-frame',1)]:
    w.BALL_TILE_STRIDE = stride
    for episode in episodes:
        tracker = w.BallTracker()
        cap = cv2.VideoCapture('/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4')
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not cap.isOpened() or fps != 30:
            raise ValueError('Expected 30 fps source')
        first,last = [round(episode[k]*fps) for k in ('startSeconds','endSeconds')]
        frames=[]
        stages=dict(decode=0.,full=0.,tiled=0.,tracking=0.)
        started=time.perf_counter()
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES,first)
            for count,index in enumerate(range(first,last),1):
                t=time.perf_counter()
                ok,frame=cap.read()
                stages['decode']+=time.perf_counter()-t
                if not ok:
                    raise RuntimeError(index)
                timestamp=index/fps
                t=time.perf_counter()
                full=w.detect_ball_full(model,frame,timestamp)
                stages['full']+=time.perf_counter()-t
                tiled=[]
                if count % stride == 0:
                    t=time.perf_counter()
                    tiled=w.detect_ball_tiled(model,frame,timestamp)
                    stages['tiled']+=time.perf_counter()-t
                t=time.perf_counter()
                candidates=w.merge_ball_candidates(full+tiled)
                for c in candidates:
                    c['accepted']=False
                    if c['qualityScore'] < w.BALL_TRACK_UPDATE_MIN_SCORE:
                        c['rejectionReason']='score_below_track_update_threshold'
                tracker.update([c for c in candidates if c['qualityScore'] >= w.BALL_TRACK_UPDATE_MIN_SCORE],timestamp)
                stages['tracking']+=time.perf_counter()-t
                frames.append(dict(frame=index,timestamp=timestamp,candidates=candidates))
                if count%30==0:
                    print(f'{profile} E{episode["episode"]}: {count}/{last-first}',flush=True)
        finally:
            cap.release()
        result=dict(episode=episode['episode'],profile=profile,fps=fps,
                    startSeconds=episode['startSeconds'],endSeconds=episode['endSeconds'],
                    manualTimestamp=episode['manualTimestamp'],frames=frames,
                    elapsedSeconds=time.perf_counter()-started,stagesSeconds=stages,
                    cpuThreads=w.torch.get_num_threads(),
                    settings={k:v for k,v in vars(w).items() if k.startswith('BALL_') and isinstance(v,(str,int,float,bool))})
        with (OUTPUT/f'{profile}-{episode["episode"]:02d}.json').open('x') as stream:
            json.dump(result,stream,allow_nan=False)
        summary.append({k:v for k,v in result.items() if k not in ('frames','settings')})
        print(f'{profile} E{episode["episode"]}: {result["elapsedSeconds"]:.2f}s',flush=True)
with (OUTPUT/'summary.json').open('x') as stream:
    json.dump(summary,stream,indent=2)
