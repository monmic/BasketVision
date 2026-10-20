"""Propose training-only hard-negative crops for visual review, not labels."""
import json
from pathlib import Path
import sys
import cv2
import numpy as np

sys.path.insert(0,'/repo/scripts')
from evaluate_ball_clip import iou

OUT=Path('/output')
PRIOR=Path('/repo/backend/artifacts/ball-crops-20261011')
rows=json.loads((PRIOR/'pilot-development-predictions.json').read_text())['train']
proposals=[]
for row in rows:
    image=cv2.imread(str(PRIOR/'dataset/images/train'/row['image']))
    h,w=image.shape[:2]
    options=[]
    for box,conf in zip(row['boxes'],row['confidence']):
        if any(iou(box,t)>0 for t in row['truth']):
            continue
        cx,cy=(box[0]+box[2])*w/2,(box[1]+box[3])*h/2
        x,y=max(0,min(w-128,round(cx-64))),max(0,min(h-128,round(cy-64)))
        window=[x,y,x+128,y+128]
        # Reject even near misses: a 16px margin around every annotated ball.
        if any(min(x+128,t[2]*w+16)>max(x,t[0]*w-16) and
               min(y+128,t[3]*h+16)>max(y,t[1]*h-16) for t in row['truth']):
            continue
        options.append((conf,box,window))
    if options:
        conf,box,window=max(options,key=lambda r:r[0])
        proposals.append(dict(image=row['image'],frame=int(Path(row['image']).stem.split('-')[-1]),
                              confidence=conf,box=box,window=window,review='pending'))
proposals=sorted(proposals,key=lambda r:r['confidence'],reverse=True)[:16]
for i,row in enumerate(proposals):
    row['id']=f'negative-{i+1:02d}'
(OUT/'proposals.json').write_text(json.dumps(proposals,indent=2))
sheet=np.full((((len(proposals)+3)//4)*288,4*256,3),245,dtype=np.uint8)
for i,row in enumerate(proposals):
    original=cv2.imread(str(PRIOR/'dataset/images/train'/row['image']))
    x,y,r,b=row['window']
    crop=cv2.resize(original[y:b,x:r],(256,256),interpolation=cv2.INTER_NEAREST)
    ox,oy=(i%4)*256,(i//4)*288
    sheet[oy+32:oy+288,ox:ox+256]=crop
    cv2.putText(sheet,f"{row['id']} f{row['frame']}",(ox+4,oy+21),
                cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,0),1)
cv2.imwrite(str(OUT/'proposals.jpg'),sheet)
for i,row in enumerate(proposals):
    x,y,r,b=row['window']
    original=cv2.imread(str(PRIOR/'dataset/images/train'/row['image']))
    h,w=original.shape[:2]
    box=row['box']
    ox,oy=(i%4)*256,(i//4)*288+32
    cv2.rectangle(sheet,(ox+round((box[0]*w-x)*2),oy+round((box[1]*h-y)*2)),
                  (ox+round((box[2]*w-x)*2),oy+round((box[3]*h-y)*2)),(0,140,255),2)
cv2.imwrite(str(OUT/'proposals-marked.jpg'),sheet)
print('Proposals requiring visual review:',len(proposals))
