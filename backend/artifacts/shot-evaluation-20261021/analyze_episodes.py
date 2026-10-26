"""Isolated ball inference; no DB access and no fixed rim assumption."""
import json
import sys
from pathlib import Path
import cv2

sys.path.insert(0, '/app')
import worker as w

output = Path('/output')
episodes = json.loads((output/'episodes.json').read_text())
model = w.get_ball_model()
summary = []
for episode in episodes:
    path = output/f"episode-{episode['episode']:02d}-ball.json"
    if path.exists():
        raise RuntimeError(f'Output exists: {path}')
    cap = cv2.VideoCapture('/app/storage/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4')
    fps = cap.get(cv2.CAP_PROP_FPS)
    first = round(episode['startSeconds']*fps)
    last = round(episode['endSeconds']*fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    tracker = w.BallTracker()
    frames = []
    for frame_index in range(first, last):
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(f'Cannot decode {frame_index}')
        timestamp = frame_index/fps
        detections = w.detect_ball_full(model, frame, timestamp)
        if w.BALL_USE_TILES and (frame_index-first+1) % w.BALL_TILE_STRIDE == 0:
            detections += w.detect_ball_tiled(model, frame, timestamp)
        candidates = w.merge_ball_candidates(detections)
        for c in candidates:
            c['accepted'] = False
        tracker.update([c for c in candidates if c['qualityScore'] >= w.BALL_TRACK_UPDATE_MIN_SCORE], timestamp)
        frames.append({'frame': frame_index, 'timestamp': timestamp, 'candidates': candidates})
    cap.release()
    result = dict(episode, fps=fps, frames=frames, notice='Ball-only diagnostic, no shot classification: moving camera requires temporal rim calibration.',
                  settings={k:v for k,v in vars(w).items() if k.startswith('BALL_') and isinstance(v,(str,int,float,bool))})
    with path.open('x') as f:
        json.dump(result, f)
    counts = {'episode':episode['episode'], 'manualTimestamp':episode['manualTimestamp'],
              'frames':len(frames), 'raw':sum(len(r['candidates']) for r in frames),
              'accepted':sum(c['accepted'] for r in frames for c in r['candidates']),
              'confirmedTracks':tracker.confirmed_count()}
    summary.append(counts)
    print(json.dumps(counts), flush=True)
with (output/'episodes-ball-summary.json').open('x') as f:
    json.dump(summary,f,indent=2)
