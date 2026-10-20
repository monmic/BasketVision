"""Diagnostic contact sheet: annotation-centered crops, never used for inference."""
import json
from pathlib import Path
import cv2
import numpy as np

out = Path('/output')
prior = Path('/repo/backend/artifacts/ball-pilot-20261011')
rows = json.loads((prior/'baseline-development-predictions.json').read_text())['val']
sheet = np.full((4*286,4*256,3),245,dtype=np.uint8)
for idx,row in enumerate(rows):
    image = cv2.imread(str(prior/'dataset/images/val'/row['image']))
    h,w = image.shape[:2]
    b = row['truth'][0]
    cx,cy=round((b[0]+b[2])*w/2),round((b[1]+b[3])*h/2)
    x0,y0=max(0,min(w-128,cx-64)),max(0,min(h-128,cy-64))
    crop=image[y0:y0+128,x0:x0+128].copy()
    cv2.rectangle(crop,(round(b[0]*w)-x0,round(b[1]*h)-y0),
                  (round(b[2]*w)-x0,round(b[3]*h)-y0),(0,255,0),1)
    panel=cv2.resize(crop,(256,256),interpolation=cv2.INTER_NEAREST)
    y,x=idx//4*286,idx%4*256
    sheet[y+30:y+286,x:x+256]=panel
    cv2.putText(sheet,str(idx+1)+' frame '+row['image'].split('-')[-1][:-4],
                (x+5,y+20),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,0),1)
cv2.imwrite(str(out/'validation-crops.jpg'),sheet)
