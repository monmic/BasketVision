"""Recover missing raw evidence for the original episode, without DB access."""
import json
import sys
import time
from pathlib import Path
import cv2

sys.path.insert(0, '/app')
import worker as w

HERE = Path(__file__).resolve().parent
output = HERE / 'ball-gap-audit'
output.mkdir(exist_ok=True)
path = output / 'original-raw.json'
if path.exists():
    raise RuntimeError('Preserve existing raw evidence')
settings = json.loads((HERE / 'episode-01-ball.json').read_text())['settings']
for name, value in settings.items():
    if name != 'BALL_MODEL':
        setattr(w, name, value)
model = w.get_ball_model()
cap = cv2.VideoCapture('/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4')
fps = cap.get(cv2.CAP_PROP_FPS)
if not cap.isOpened() or fps != 30:
    raise ValueError('Expected original 30 fps video')
tracker = w.BallTracker()
frames = []
started = time.perf_counter()
try:
    cap.set(cv2.CAP_PROP_POS_FRAMES, 433*30)
    for count, index in enumerate(range(433*30, 436*30), 1):
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(index)
        timestamp = index/fps
        candidates = w.detect_ball_full(model, frame, timestamp)
        if w.BALL_USE_TILES and count % w.BALL_TILE_STRIDE == 0:
            candidates += w.detect_ball_tiled(model, frame, timestamp)
        candidates = w.merge_ball_candidates(candidates)
        for candidate in candidates:
            candidate['accepted'] = False
            if candidate['qualityScore'] < w.BALL_TRACK_UPDATE_MIN_SCORE:
                candidate['rejectionReason'] = 'score_below_track_update_threshold'
        tracker.update([c for c in candidates if c['qualityScore'] >= w.BALL_TRACK_UPDATE_MIN_SCORE], timestamp)
        frames.append(dict(frame=index, timestamp=timestamp, candidates=candidates))
        if count % 30 == 0:
            print(f'Original raw audit: {count}/90 frames', flush=True)
finally:
    cap.release()
result = dict(episode=0, manualTimestamp=434.68, startSeconds=433, endSeconds=436,
              fps=fps, frames=frames, elapsedSeconds=time.perf_counter()-started,
              settings={k:v for k,v in vars(w).items() if k.startswith('BALL_') and isinstance(v,(str,int,float,bool))},
              cpuThreads=w.torch.get_num_threads(), notice='Fresh ball-only inference; compare accepted points before treating as reproduction. Time includes decode/inference/tracking, excludes model loading; local CPU, not production benchmark.')
with path.open('x') as stream:
    json.dump(result, stream, indent=2, allow_nan=False)
print(f'Saved {path}', flush=True)
