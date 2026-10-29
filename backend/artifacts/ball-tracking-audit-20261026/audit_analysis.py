"""Read-only audit and isolated raw reconstruction of the 500–560 s analysis."""
import argparse
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('mode',choices=['accepted','infer'])
parser.add_argument('--report',type=Path,default=Path('/report.json'))
parser.add_argument('--replay',type=Path,help='Render accepted observations from an offline replay')
parser.add_argument('--new-only',action='store_true',help='Render only replay acceptances absent from operational report')
args=parser.parse_args()
report=json.loads(args.report.read_text(encoding='utf-8-sig'))
VIDEO='/videos/'+Path(report['video']['path']).name


def write(path,data):
    with path.open('x',encoding='utf-8') as stream:
        json.dump(data,stream,indent=2,allow_nan=False)


def accepted():
    cap=cv2.VideoCapture(VIDEO)
    records=[]
    tiles=[]
    try:
        points=report['ballTrack']
        prefix='accepted'
        if args.replay:
            replay=json.loads(args.replay.read_text())
            points=[c for row in replay['frames'] for c in row['candidates'] if c['accepted']]
            prefix='replay-accepted'
            if args.new_only:
                identity=lambda c:(round(c['timestamp']*report['video']['fps']),)+tuple(c[k] for k in ('x1','y1','x2','y2'))
                old={identity(c) for c in report['ballTrack']}
                points=[c for c in points if identity(c) not in old]
                prefix='new-accepted'
        for index,c in enumerate(points):
            frame_index=round(c['timestamp']*report['video']['fps'])
            cap.set(cv2.CAP_PROP_POS_FRAMES,frame_index)
            ok,frame=cap.read()
            if not ok:
                raise RuntimeError(frame_index)
            left,top=max(0,round(c['centerX'])-80),max(0,round(c['centerY'])-80)
            crop=frame[top:min(top+160,frame.shape[0]),left:min(left+160,frame.shape[1])].copy()
            cv2.rectangle(crop,(round(c['x1'])-left,round(c['y1'])-top),
                          (round(c['x2'])-left,round(c['y2'])-top),(0,255,0),1)
            tile=np.zeros((270,240,3),dtype=np.uint8)
            height,width=crop.shape[:2]
            scale=min(240/width,240/height)
            resized=cv2.resize(crop,(round(width*scale),round(height*scale)))
            tile[:resized.shape[0],:resized.shape[1]]=resized
            cv2.putText(tile,f'{index} t{c["trackId"]} {c["timestamp"]:.3f}',(2,257),0,.45,(255,255,255),1)
            tiles.append(tile)
            records.append(dict(index=index,frame=frame_index,timestamp=c['timestamp'],candidate=c,review=None))
    finally:
        cap.release()
    for offset in range(0,len(tiles),30):
        chunk=tiles[offset:offset+30]
        sheet=np.zeros((math.ceil(len(chunk)/6)*270,1440,3),dtype=np.uint8)
        for n,tile in enumerate(chunk):
            sheet[n//6*270:(n//6+1)*270,n%6*240:(n%6+1)*240]=tile
        path=HERE/f'{prefix}-{offset//30+1:02d}.jpg'
        if path.exists() or not cv2.imwrite(str(path),sheet):
            raise RuntimeError(path)
    write(HERE/f'{prefix}.json',dict(analysisId=report['analysisId'],observations=records,
        notice='All accepted observations, not a sample. Green box means tracker accepted, not verified ball.'))
    print(f'Created {len(records)} accepted crops in {math.ceil(len(tiles)/30)} boards',flush=True)


def infer():
    if (HERE/'raw.json').exists():
        raise RuntimeError('Preserve existing reconstruction')
    sys.path.insert(0,'/app')
    import worker as w
    mapped={}
    for key,value in report['config'].items():
        if not key.startswith('ball'):
            continue
        name=re.sub(r'(?<!^)(?=[A-Z])','_',key).upper()
        if not hasattr(w,name):
            raise ValueError(f'Unknown recorded setting {name}')
        setattr(w,name,value)
        mapped[name]=value
    if w.BALL_FRAME_STRIDE!=1 or w.BALL_CAMERA_MOTION_FILTER:
        raise ValueError('This reconstruction requires the recorded stride-1/no-camera profile')
    model=w.get_ball_model()
    w.detect_ball_full(model,np.zeros((480,854,3),dtype=np.uint8),0)
    w.detect_ball_tiled(model,np.zeros((480,854,3),dtype=np.uint8),0)
    cap=cv2.VideoCapture(VIDEO)
    fps=cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or fps!=report['video']['fps']:
        raise ValueError('Source mismatch')
    first,last=[round(report['video'][key]*fps) for key in ('analysisStartSeconds','analysisEndSeconds')]
    tracker=w.BallTracker()
    rows=[]
    started=time.perf_counter()
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES,first)
        for count,index in enumerate(range(first,last),1):
            ok,frame=cap.read()
            if not ok:
                raise RuntimeError(index)
            timestamp=index/fps
            candidates=w.detect_ball_full(model,frame,timestamp)
            if w.BALL_USE_TILES and count%w.BALL_TILE_STRIDE==0:
                candidates+=w.detect_ball_tiled(model,frame,timestamp)
            candidates=w.merge_ball_candidates(candidates)
            for c in candidates:
                c['accepted']=False
                if c['qualityScore']<w.BALL_TRACK_UPDATE_MIN_SCORE:
                    c['rejectionReason']='score_below_track_update_threshold'
            tracker.update([c for c in candidates if c['qualityScore']>=w.BALL_TRACK_UPDATE_MIN_SCORE],timestamp)
            rows.append(dict(frame=index,timestamp=timestamp,width=frame.shape[1],height=frame.shape[0],candidates=candidates))
            if count%60==0:
                print(f'Raw reconstruction: {count}/{last-first}, t={timestamp:.3f}',flush=True)
    finally:
        cap.release()
    result=dict(analysisId=report['analysisId'],sourceVideo=Path(VIDEO).name,source=dict(fps=fps),
        start=first/fps,end=last/fps,frames=rows,cpuThreads=w.torch.get_num_threads(),
        settings={k:v for k,v in vars(w).items() if k.startswith('BALL_') and isinstance(v,(str,int,float,bool))},
        mappedRecordedSettings=mapped,elapsedSeconds=time.perf_counter()-started,
        workerSha256=hashlib.sha256(Path('/app/worker.py').read_bytes()).hexdigest(),
        modelSha256=hashlib.sha256(Path(w.BALL_MODEL).read_bytes()).hexdigest(),
        reportSha256=hashlib.sha256(args.report.read_bytes()).hexdigest(),
        notice='Ball-only raw reconstruction; validate against operational report before drawing tracker conclusions. No person inference or DB access. Time excludes model load/warm-up; local CPU.')
    write(HERE/'raw.json',result)
    print(f'Saved {len(rows)} reconstructed frames in {result["elapsedSeconds"]:.2f}s',flush=True)


{'accepted':accepted,'infer':infer}[args.mode]()
