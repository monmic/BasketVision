"""Extract review frames before assigning a fixed-camera rim calibration."""
import cv2
import json
from pathlib import Path

OUTPUT = Path('/output')
VIDEO = '/app/storage/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4'
TIMES = [592.85, 1175.91, 1191.56, 1199.54, 1207.89]
cap = cv2.VideoCapture(VIDEO)
plan = []
for index, timestamp in enumerate(TIMES, 1):
    start, end = max(0, timestamp-2), timestamp+2
    frames = []
    for sample, t in enumerate([start, timestamp, end]):
        cap.set(cv2.CAP_PROP_POS_MSEC, t*1000)
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(f'Cannot decode {t}')
        name = f'episode-{index:02d}-{sample}.jpg'
        if not cv2.imwrite(str(OUTPUT/name), frame):
            raise RuntimeError(name)
        frames.append({'timestamp': t, 'file': name})
    plan.append({'episode': index, 'manualTimestamp': timestamp, 'startSeconds': start,
                 'endSeconds': end, 'reviewFrames': frames, 'calibration': None,
                 'status': 'awaiting_camera_review'})
cap.release()
with (OUTPUT/'episodes.json').open('x', encoding='utf-8') as out:
    json.dump(plan, out, indent=2)
