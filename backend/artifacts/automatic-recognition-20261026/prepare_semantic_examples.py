"""Native proposal crops for future semantic discrimination, with episode provenance.

This does not produce full-frame detection labels, split data, or train a model.
"""
import hashlib
import json
import math
from pathlib import Path

import cv2

HERE=Path(__file__).resolve().parent
old=HERE.parent/'ball-tracking-audit-20261026'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
rows=[]
for r in read(old/'combined-reviewed.json')['observations']:
    if r['review']=='uncertain_tiny_candidate':continue
    rows.append(dict(frame=r['frame'],timestamp=r['timestamp'],episode='minute-500-560',
                     label='active_ball' if r['review']=='visible_active_ball' else 'shoe',candidate=r['candidate']))
for r in read(HERE/'visual-review.json')['accepted']:
    rows.append(dict(frame=r['frame'],timestamp=r['timestamp'],episode=f'episode-{r["episode"]}',label=r['visualObject'],candidate=r))
for i,r in enumerate(read(HERE/'distance-review-input.json')):
    rows.append(dict(frame=r['frame'],timestamp=r['candidate']['timestamp'],episode='minute-500-560' if r['episode']=='minute' else f'episode-{r["episode"]}',
                     label='player_head' if i==0 else 'shoe',candidate=r['candidate']))
out=HERE/'semantic-examples';out.mkdir(exist_ok=False)
cap=cv2.VideoCapture('/videos/35b68704-541f-4c6d-b8ab-45228266102a.mp4')
if not cap.isOpened() or cap.get(cv2.CAP_PROP_FPS)!=30:raise ValueError('Video/FPS mismatch')
examples=[];identities=set()
try:
    for r in rows:
        c=r['candidate'];identity=(r['frame'],*(round(c[k],1) for k in ('x1','y1','x2','y2')))
        if identity in identities:raise ValueError('Duplicate proposal crop')
        identities.add(identity)
        cap.set(cv2.CAP_PROP_POS_FRAMES,r['frame']);ok,frame=cap.read()
        if not ok:raise ValueError(r['frame'])
        left,top=max(0,math.floor(c['x1'])),max(0,math.floor(c['y1']))
        right,bottom=min(frame.shape[1],math.ceil(c['x2'])),min(frame.shape[0],math.ceil(c['y2']))
        if left>=right or top>=bottom:raise ValueError('Empty box')
        file=f'{len(examples):03d}-{r["label"]}.png';path=out/file
        if not cv2.imwrite(str(path),frame[top:bottom,left:right]):raise ValueError('Write failed')
        examples.append(dict(file=file,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),label=r['label'],
            sourceVideo='35b68704-541f-4c6d-b8ab-45228266102a.mp4',episode=r['episode'],frame=r['frame'],timestamp=r['timestamp'],
            candidateBox=list(identity[1:]),cropBounds=[left,top,right,bottom],trackId=c.get('trackId')))
finally:cap.release()
counts={label:sum(r['label']==label for r in examples) for label in sorted({r['label'] for r in examples})}
manifest=dict(examples=examples,counts=counts,excludedUncertain=20,
    notice=__doc__+' All examples are previously inspected development data from one source. Adjacent observations and track IDs are not independent. Keep sources/episodes together in any future evaluation; no untouched test source exists here. Negative labels apply only to these proposal boxes, never entire basketball frames.')
with (out/'manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2)
print(json.dumps(counts))
