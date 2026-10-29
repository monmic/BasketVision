"""All semantic accepted boxes plus paired baseline boxes on fixed reference frames."""
import json
import math
from pathlib import Path

import cv2
import numpy as np

HERE=Path(__file__).resolve().parent
read=lambda path:json.loads(path.read_text())
baseline=read(HERE/'continuous/baseline.json');semantic=read(HERE/'continuous/semantic.json')
selected={r['frame'] for r in read(HERE/'adapted-benchmark/raw.json')['frames']}
out=HERE/'continuous-review';out.mkdir(exist_ok=False)
def key(frame,c):return (frame,*(round(c[k],1) for k in ('x1','y1','x2','y2')))
accepted={}
for name,report in [('baseline',baseline),('semantic',semantic)]:
    for row in report['frames']:
        for c in row['candidates']:
            if not c.get('accepted'):continue
            identity=key(row['frame'],c)
            if name=='baseline' and row['frame'] not in selected:continue
            if identity not in accepted:accepted[identity]=dict(frame=row['frame'],timestamp=row['timestamp'],candidate=c,baseline=False,semantic=False)
            accepted[identity][name]=True
# Fill baseline acceptance for every semantic observation even outside sample.
base_keys={key(r['frame'],c) for r in baseline['frames'] for c in r['candidates'] if c.get('accepted')}
rows=sorted(accepted.values(),key=lambda r:(r['frame'],r['candidate']['centerX'],r['candidate']['centerY']))
for i,r in enumerate(rows):r.update(index=i,baseline=key(r['frame'],r['candidate']) in base_keys,selectedReference=r['frame'] in selected)
cap=cv2.VideoCapture('/video.mp4')
try:
    for start in range(0,len(rows),40):
        sheet=np.zeros((5*150,8*150,3),np.uint8)
        for n,r in enumerate(rows[start:start+40]):
            cap.set(cv2.CAP_PROP_POS_FRAMES,r['frame']);ok,frame=cap.read()
            if not ok:raise ValueError(r['frame'])
            c=r['candidate'];radius=max(24,math.ceil(max(c['width'],c['height'])*2))
            cx,cy=round(c['centerX']),round(c['centerY']);left,top=max(0,cx-radius),max(0,cy-radius)
            crop=frame[top:min(frame.shape[0],cy+radius),left:min(frame.shape[1],cx+radius)].copy()
            cv2.rectangle(crop,(round(c['x1'])-left,round(c['y1'])-top),(round(c['x2'])-left,round(c['y2'])-top),(0,255,255),1)
            x,y=n%8*150,n//8*150;sheet[y:y+120,x:x+150]=cv2.resize(crop,(150,120))
            cv2.putText(sheet,f'{r["index"]} f{r["frame"]}',(x+3,y+137),0,.35,(255,255,255),1)
        if not cv2.imwrite(str(out/f'board-{start//40:02d}.jpg'),sheet):raise ValueError('Write failed')
finally:cap.release()
with (out/'manifest.json').open('x') as stream:json.dump(rows,stream,indent=2)
print(json.dumps(dict(reviewBoxes=len(rows),semanticAccepted=sum(r['semantic'] for r in rows),pairedReferenceBoxes=sum(r['selectedReference'] for r in rows))))
