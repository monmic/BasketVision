"""Unmarked original-pixel enlargements for reviewing missing ball annotations."""
from pathlib import Path
import json
import cv2
import numpy as np

root=Path('/output')
source=Path('/repo/backend/artifacts/ball-crops-20261011/dataset/images/train')
sheet=np.full((2*400,384,3),245,dtype=np.uint8)
for i,frame in enumerate([13008,13014]):
    image=cv2.imread(str(source/f'35b68704-541f-4c6d-b8ab-45228266102a-{frame:06d}.png'))
    crop=image[236:284,140:188]
    sheet[i*400+16:i*400+400]=cv2.resize(crop,(384,384),interpolation=cv2.INTER_NEAREST)
    cv2.putText(sheet,f'Frame {frame}; x140..188 y236..284',(3,i*400+12),
                cv2.FONT_HERSHEY_SIMPLEX,.35,(0,0,0),1)
cv2.imwrite(str(root/'missing-ball-unmarked.png'),sheet)
revision=json.loads((root/'missing-ball-review.json').read_text())
for i,row in enumerate(revision['additions']):
    for x1,y1,x2,y2 in row['boxesPixels']:
        cv2.rectangle(sheet,(round((x1-140)*8),i*400+16+round((y1-236)*8)),
                      (round((x2-140)*8),i*400+16+round((y2-236)*8)),(0,255,0),2)
cv2.imwrite(str(root/'missing-ball-reviewed.png'),sheet)
