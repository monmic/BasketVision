"""Review changed full-frame detections using annotation-centered display crops only."""
import json
from pathlib import Path
import sys
import cv2
import numpy as np

sys.path.insert(0,'/repo/scripts')
from evaluate_ball_clip import iou

root=Path('/output')
prior=Path('/repo/backend/artifacts/ball-pilot-20261011')
changed=[]
counts={}
for split in ['val','test']:
    suffix='development' if split=='val' else 'test'
    baseline=json.loads((prior/f'baseline-{suffix}-predictions.json').read_text())[split]
    pilot=json.loads((root/f'pilot-{suffix}-predictions.json').read_text())[split]
    by_name={r['image']:r for r in pilot}
    counts[split]={'gained':[],'lost':[],'retained':[],'stillMissed':[]}
    for a in baseline:
        b=by_name[a['image']]
        assert a['truth']==b['truth'] and len(a['truth'])==1
        truth=a['truth'][0]
        ai=max([iou(truth,x) for x in a['boxes']],default=0)
        bi=max([iou(truth,x) for x in b['boxes']],default=0)
        kind='retained' if ai>=.5 and bi>=.5 else 'gained' if bi>=.5 else 'lost' if ai>=.5 else 'stillMissed'
        counts[split][kind].append(a['image'])
        changed.append(dict(split=split,image=a['image'],baseline=a,pilot=b,
                            baselineIoU=ai,pilotIoU=bi,kind=kind))
(root/'changed-frames.json').write_text(json.dumps(counts,indent=2))
selected=sorted(changed,key=lambda r:(r['kind'] in ['gained','lost'],
                                      abs(r['pilotIoU']-r['baselineIoU'])),reverse=True)[:6]
sheet=np.full((len(selected)*290,2*256,3),245,dtype=np.uint8)
for row,item in enumerate(selected):
    original=cv2.imread(str(prior/'dataset/images'/item['split']/item['image']))
    h,w=original.shape[:2]
    gt=item['baseline']['truth'][0]
    cx,cy=round((gt[0]+gt[2])*w/2),round((gt[1]+gt[3])*h/2)
    left,top=max(0,min(w-128,cx-64)),max(0,min(h-128,cy-64))
    for col,name in enumerate(['baseline','pilot']):
        crop=original[top:top+128,left:left+128].copy()
        for box in item[name]['boxes']:
            cv2.rectangle(crop,(round(box[0]*w)-left,round(box[1]*h)-top),
                          (round(box[2]*w)-left,round(box[3]*h)-top),(0,140,255),1)
        cv2.rectangle(crop,(round(gt[0]*w)-left,round(gt[1]*h)-top),
                      (round(gt[2]*w)-left,round(gt[3]*h)-top),(0,255,0),1)
        panel=cv2.resize(crop,(256,256),interpolation=cv2.INTER_NEAREST)
        y,x=row*290,col*256
        sheet[y+34:y+290,x:x+256]=panel
        frame=item['image'].split('-')[-1][:-4]
        text=f"{item['split']} {frame} {name} IoU {item[name+'IoU']:.2f}"
        cv2.putText(sheet,text,(x+3,y+14),cv2.FONT_HERSHEY_SIMPLEX,.36,(0,0,0),1)
        cv2.putText(sheet,item['kind']+' / truth green, pred orange',(x+3,y+29),
                    cv2.FONT_HERSHEY_SIMPLEX,.32,(0,0,0),1)
cv2.imwrite(str(root/'changed-frames.jpg'),sheet)
print({s:{k:len(v) for k,v in counts[s].items()} for s in counts})
