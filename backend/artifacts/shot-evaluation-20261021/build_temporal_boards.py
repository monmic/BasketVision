"""Build diagnostic review sheets from extracted frames and saved accepted boxes."""
import json
import math
from pathlib import Path
import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / 'temporal-review'
manifest = json.loads((OUTPUT / 'manifest.json').read_text())
video = cv2.VideoCapture('/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4')
try:
    boxes = []
    for episode in manifest:
        sheet = np.zeros((math.ceil(len(episode['frames']) / 4) * 150, 427 * 4, 3), dtype=np.uint8)
        for n, row in enumerate(episode['frames']):
            frame = cv2.imread(str(OUTPUT / row['file']))
            if frame is None:
                raise RuntimeError(row['file'])
            tile = cv2.resize(frame[:240], (427, 120))
            x, y = n % 4 * 427, n // 4 * 150
            sheet[y:y+120, x:x+427] = tile
            cv2.putText(sheet, f'{row["timestamp"]:.3f}s f{row["frame"]}', (x+5, y+140), 0, .55, (255,255,255), 1)
        path = OUTPUT / f'episode-{episode["episode"]:02d}-board.jpg'
        if path.exists() or not cv2.imwrite(str(path), sheet):
            raise RuntimeError(f'Cannot create new output: {path}')
        saved = json.loads((HERE / f'episode-{episode["episode"]:02d}-ball.json').read_text())
        for row in saved['frames']:
            accepted = [c for c in row['candidates'] if c.get('accepted')]
            if not accepted:
                continue
            video.set(cv2.CAP_PROP_POS_FRAMES, row['frame'])
            ok, frame = video.read()
            if not ok:
                raise RuntimeError(row['frame'])
            for c in accepted:
                cx, cy = round(c['centerX']), round(c['centerY'])
                x, y = max(0, cx-50), max(0, cy-50)
                crop = frame[y:y+100, x:x+100].copy()
                cv2.rectangle(crop, (round(c['x1'])-x, round(c['y1'])-y),
                              (round(c['x2'])-x, round(c['y2'])-y), (0,255,0), 1)
                tile = np.zeros((240, 240, 3), dtype=np.uint8)
                tile[:200, :200] = cv2.resize(crop, (200,200))
                cv2.putText(tile, f'E{episode["episode"]} {row["timestamp"]:.3f}', (2,225), 0, .5, (255,255,255), 1)
                boxes.append(tile)
    sheet = np.zeros((math.ceil(len(boxes)/6)*240, 6*240, 3), dtype=np.uint8)
    for n, tile in enumerate(boxes):
        sheet[n//6*240:(n//6+1)*240,n%6*240:(n%6+1)*240] = tile
    path = OUTPUT / 'accepted-boxes.jpg'
    if path.exists() or not cv2.imwrite(str(path), sheet):
        raise RuntimeError(f'Cannot create new output: {path}')
    print(f'Created five temporal boards and {len(boxes)} accepted-box crops')
finally:
    video.release()
