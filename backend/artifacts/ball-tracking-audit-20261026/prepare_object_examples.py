"""Package reviewed candidate crops; never turn whole basketball frames into negatives."""
import hashlib
import json
import math
from pathlib import Path
import cv2

HERE=Path(__file__).resolve().parent
OUTPUT=HERE/'object-examples'
OUTPUT.mkdir(exist_ok=False)
review=json.loads((HERE/'combined-reviewed.json').read_text())
cap=cv2.VideoCapture('/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4')
if not cap.isOpened() or cap.get(cv2.CAP_PROP_FPS)!=30:
    raise ValueError('Expected original video at 30 fps')
records=[]
groups={}
try:
    for row in sorted(review['observations'],key=lambda r:(r['frame'],r['candidate']['trackId'])):
        if row['review']=='uncertain_tiny_candidate':
            continue
        candidate=row['candidate']
        cap.set(cv2.CAP_PROP_POS_FRAMES,row['frame'])
        ok,frame=cap.read()
        if not ok:
            raise RuntimeError(row['frame'])
        x1,y1=[max(0,math.floor(candidate[k])) for k in ('x1','y1')]
        x2,y2=min(frame.shape[1],math.ceil(candidate['x2'])),min(frame.shape[0],math.ceil(candidate['y2']))
        if not (x1<x2 and y1<y2):
            raise ValueError('Invalid reviewed candidate crop')
        group_key=(row['review'],candidate['trackId'])
        previous=groups.get(group_key)
        if previous is None or row['timestamp']-previous['last']>.25:
            group=dict(id=f'{row["review"]}-track{candidate["trackId"]}-frame{row["frame"]}',last=row['timestamp'])
            groups[group_key]=group
        else:
            group=previous
            group['last']=row['timestamp']
        name=f'{len(records):03d}-{row["review"]}-frame{row["frame"]}.png'
        path=OUTPUT/name
        if not cv2.imwrite(str(path),frame[y1:y2,x1:x2]):
            raise RuntimeError(path)
        records.append(dict(file=name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            sourceVideo='35b68704-541f-4c6d-b8ab-45228266102a.mp4',frame=row['frame'],timestamp=row['timestamp'],
            label=row['review'],candidateBox=[candidate[k] for k in ('x1','y1','x2','y2')],
            cropBounds=[x1,y1,x2,y2],trackId=candidate['trackId'],temporalGroup=group['id']))
finally:
    cap.release()
manifest=dict(examples=records,excludedUncertain=20,
    notice='Diagnostic candidate-classification examples from visually reviewed proposal boxes. Not exhaustive full-frame YOLO labels; source frames may contain real balls outside shoe crops. No train/val/test assignment or automatic training. Adjacent observations are correlated; track IDs can mix objects. Group by source and independent episodes before evaluating a future model.')
with (OUTPUT/'manifest.json').open('x') as stream:
    json.dump(manifest,stream,indent=2)
print(f'Packaged {len(records)} native candidate PNGs; 20 uncertain boxes excluded; no training performed')
