"""Offline CV diagnostic: no database, jobs or production configuration changes.

Run in the worker image with /app/worker.py and a mounted video/output directory.
Timings describe this machine, exclude model loading and are not VM predictions.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, '/app')
import worker as w

parser = argparse.ArgumentParser()
parser.add_argument('video')
parser.add_argument('output')
parser.add_argument('--start', type=float, default=9)
parser.add_argument('--end', type=float, default=10.5)
parser.add_argument('--width', type=int, help='Single profile: resize width (omit to preserve source)')
parser.add_argument('--stride', type=int, help='Single profile: analyze every N source frames')
args = parser.parse_args()
if args.start < 0 or args.end <= args.start or (args.width is not None and args.width < 1) or (args.stride is not None and args.stride < 1):
    parser.error('Require 0 <= start < end, positive width and stride')
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)
ball = w.get_ball_model()
person = w.get_person_model()
# Warm up predictors; exclude model loading/first inference from timings.
ball.predict(np.zeros((544, 960, 3), dtype=np.uint8), imgsz=960, verbose=False)
person.track(np.zeros((384, 640, 3), dtype=np.uint8), persist=True,
             tracker=w.PERSON_TRACKER_CONFIG, classes=[0], verbose=False)
reports = []
profiles = [('custom', args.width, args.stride or 1)] if args.width or args.stride else [('original', None, 1), ('720p-15fps', 1280, 4)]
for name, width, stride in profiles:
    for person_tracker in getattr(person.predictor, 'trackers', []):
        person_tracker.reset()
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or fps <= 0:
        raise ValueError(f'Cannot open video or invalid FPS: {args.video}')
    metadata = dict(width=cap.get(cv2.CAP_PROP_FRAME_WIDTH), height=cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
                    fps=fps, frames=cap.get(cv2.CAP_PROP_FRAME_COUNT))
    first, last = round(args.start * fps), round(args.end * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    tracker = w.BallTracker()
    stages = dict(decode=0., resize=0., person=0., full=0., tiled=0., filtering=0.)
    rows = []
    started = time.perf_counter()
    for index in range(first, last):
        t = time.perf_counter()
        ok, frame = cap.read()
        stages['decode'] += time.perf_counter()-t
        if not ok:
            break
        if (index-first) % stride:
            continue
        t = time.perf_counter()
        if width:
            frame = cv2.resize(frame, (width, round(frame.shape[0]*width/frame.shape[1])), interpolation=cv2.INTER_AREA)
        stages['resize'] += time.perf_counter()-t
        timestamp = index/fps
        count = (index-first)//stride
        if count % 3 == 0:
            t = time.perf_counter()
            person.track(frame, persist=True, tracker=w.PERSON_TRACKER_CONFIG, classes=[0],
                         conf=w.PERSON_CONFIDENCE, imgsz=w.PERSON_IMGSZ, verbose=False)
            stages['person'] += time.perf_counter()-t
        t = time.perf_counter()
        full = w.detect_ball_full(ball, frame, timestamp)
        stages['full'] += time.perf_counter()-t
        tiles = []
        if (count+1) % w.BALL_TILE_STRIDE == 0:
            t = time.perf_counter()
            tiles = w.detect_ball_tiled(ball, frame, timestamp)
            stages['tiled'] += time.perf_counter()-t
        t = time.perf_counter()
        candidates = w.merge_ball_candidates(full+tiles)
        trackable = [c for c in candidates if c['qualityScore'] >= w.BALL_TRACK_UPDATE_MIN_SCORE]
        for c in candidates:
            c['accepted'] = False
            if c['qualityScore'] < w.BALL_TRACK_UPDATE_MIN_SCORE:
                c['rejectionReason'] = 'score_below_track_update_threshold'
        tracker.update(trackable, timestamp)
        stages['filtering'] += time.perf_counter()-t
        rows.append(dict(frame=index, timestamp=timestamp, width=frame.shape[1], height=frame.shape[0], candidates=candidates))
        if abs(timestamp-10.166667) < stride/fps/2:
            cv2.imwrite(str(out/f'{name}-10.17-raw.jpg'), frame)
            w._draw_ball_candidates(frame, [c for c in candidates if c['accepted']], (0,255,0), 'accepted', 2)
            w._draw_ball_candidates(frame, [c for c in candidates if not c['accepted']], (0,0,255), 'rejected', 2)
            cv2.imwrite(str(out/f'{name}-10.17-debug.jpg'), frame)
        if count % 30 == 0:
            print(name, round(timestamp,3), 'seconds processed', flush=True)
    elapsed = time.perf_counter()-started
    cap.release()
    result = dict(profile=name, source=metadata, start=args.start, end=args.end,
                  settings={k: v for k, v in vars(w).items() if k.startswith(('BALL_', 'PERSON_', 'YOLO_')) and isinstance(v, (str, int, float, bool))},
                  resizeWidth=width, stride=stride,
                  elapsedSeconds=elapsed, stagesSeconds=stages, processedBallFrames=len(rows),
                  accepted=sum(c['accepted'] for r in rows for c in r['candidates']), frames=rows)
    (out/f'{name}.json').write_text(json.dumps(result, indent=2))
    reports.append({k:v for k,v in result.items() if k!='frames'})
    print(json.dumps(reports[-1]), flush=True)
(out/'summary.json').write_text(json.dumps(reports, indent=2))
