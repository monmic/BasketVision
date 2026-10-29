"""Native-frame context for an explicit list of proposals awaiting visual review."""
import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('manifest',type=Path)
p.add_argument('video',type=Path)
p.add_argument('output',type=Path)
args=p.parse_args()
if args.output.exists():raise ValueError('Preserve previous output')
rows=json.loads(args.manifest.read_text())
cap=cv2.VideoCapture(str(args.video))
sheet=np.zeros((math.ceil(len(rows)/4)*180,800,3),np.uint8)
try:
    for i,r in enumerate(rows):
        cap.set(cv2.CAP_PROP_POS_FRAMES,r['frame']);ok,frame=cap.read()
        if not ok:raise ValueError(r['frame'])
        c=r['candidate'];x,y=round(c['centerX']),round(c['centerY'])
        radius=max(35,math.ceil(max(c['width'],c['height'])*2))
        left,top=max(0,x-radius),max(0,y-radius)
        crop=frame[top:min(frame.shape[0],y+radius),left:min(frame.shape[1],x+radius)].copy()
        cv2.rectangle(crop,(round(c['x1'])-left,round(c['y1'])-top),(round(c['x2'])-left,round(c['y2'])-top),(0,255,255),1)
        a,b=i%4*200,i//4*180
        sheet[b:b+150,a:a+200]=cv2.resize(crop,(200,150))
        cv2.putText(sheet,f'{i} f{r["frame"]}',(a+2,b+170),0,.45,(255,255,255),1)
    if not cv2.imwrite(str(args.output),sheet):raise ValueError('Write failed')
finally:cap.release()
