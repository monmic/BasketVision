"""Reuse the existing offline annotation UI for failures shared by both detectors."""
import base64
import json
from pathlib import Path
import cv2

HERE=Path(__file__).resolve().parent
OUTPUT=HERE/'specialist-screening'
review=json.loads((OUTPUT/'visual-review.json').read_text())
samples=[]
cap=cv2.VideoCapture('/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4')
if not cap.isOpened() or cap.get(cv2.CAP_PROP_FPS)!=30:
    raise ValueError('Expected original 30 fps source')
try:
    for row in review['frames']:
        if row['status']!='both_miss':
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES,row['frame'])
        ok,frame=cap.read()
        if not ok:
            raise RuntimeError(row['frame'])
        ok,encoded=cv2.imencode('.png',frame)
        if not ok:
            raise RuntimeError('PNG encoding failed')
        samples.append(dict(frame=row['frame'],timestamp=row['frame']/30,
                            image='data:image/png;base64,'+base64.b64encode(encoded).decode()))
finally:
    cap.release()
data=dict(source='35b68704-541f-4c6d-b8ab-45228266102a.mp4',fps=30,
          exportName='home-vs-away-hard-near-rim.json',samples=samples)
template=Path('/scripts/ball_review.html').read_text(encoding='utf-8')
page=template.replace('/*REVIEW_DATA*/',json.dumps(data).replace('<','\\u003c'))
with (OUTPUT/'hard-cases-review.html').open('x',encoding='utf-8') as stream:
    stream.write(page)
plan=dict(source=data['source'],fps=30,frames=[dict(frame=s['frame'],timestamp=s['timestamp']) for s in samples],
          status='awaiting_explicit_all_visible_ball_annotations',
          notice='Known development failures, not an untouched test set. No boxes, negative labels, or train/val/test assignments inferred. Review all visible balls, omit uncertain frames.')
with (OUTPUT/'hard-cases-plan.json').open('x') as stream:
    json.dump(plan,stream,indent=2)
print(f'Prepared {len(samples)} original PNG frames in an existing offline annotation UI; no labels invented')
