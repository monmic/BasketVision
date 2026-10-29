"""Generate enlarged annotation context and full-frame overlays for review."""
import json
from pathlib import Path
import cv2
import numpy as np

import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--fresh-expanded',action='store_true')
args=parser.parse_args()
HERE=Path(__file__).resolve().parent/('detector-expanded/fresh' if args.fresh_expanded else 'detector-pilot')
data=json.loads((HERE/'annotations-draft.json').read_text())
tiles=[]
for i,row in enumerate(data['frames']):
    frame=cv2.imread(str(HERE/row['file']))
    for box in row['pixelBoxes']:
        x1,y1,x2,y2=box;cx,cy=(x1+x2)//2,(y1+y2)//2
        left,top=max(0,cx-50),max(0,cy-50)
        crop=frame[top:top+100,left:left+100].copy()
        cv2.rectangle(crop,(x1-left,y1-top),(x2-left,y2-top),(0,255,255),1)
        tile=np.zeros((330,300,3),np.uint8)
        tile[:300]=cv2.resize(crop,(300,300),interpolation=cv2.INTER_NEAREST)
        cv2.putText(tile,f'{i} {box}',(5,320),0,.4,(255,255,255),1)
        tiles.append(tile)
        cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,255),1)
    cv2.imwrite(str(HERE/f'overlay-{i:02d}.png'),frame)
for start in range(0,len(tiles),6):
    sheet=np.zeros((660,900,3),np.uint8)
    for j,tile in enumerate(tiles[start:start+6]):
        sheet[j//3*330:(j//3+1)*330,j%3*300:(j%3+1)*300]=tile
    cv2.imwrite(str(HERE/f'annotation-review-{start//6:02d}.png'),sheet)
