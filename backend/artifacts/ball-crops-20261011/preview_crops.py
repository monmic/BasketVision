"""Contact sheet of original/crop triplets to review label geometry."""
import json
from pathlib import Path
import cv2
import numpy as np

root=Path('/output')
manifest=json.loads((root/'dataset-audit.json').read_text())
sources=[r for r in manifest['frames'] if r['split']=='train']
sheet=np.full((3*220,3*320,3),245,dtype=np.uint8)
for row,index in enumerate([0,20,40]):
    stem=Path(sources[index]['image']).stem
    for col,suffix in enumerate(['','-crop256','-crop512']):
        name=stem+suffix
        frame=cv2.imread(str(root/'dataset/images/train'/(name+'.png')))
        panel=cv2.resize(frame,(320,180))
        for line in (root/'dataset/labels/train'/(name+'.txt')).read_text().splitlines():
            _,x,y,w,h=map(float,line.split())
            cv2.rectangle(panel,(round((x-w/2)*320),round((y-h/2)*180)),
                          (round((x+w/2)*320),round((y+h/2)*180)),(0,255,0),1)
        y0,x0=row*220,col*320
        sheet[y0+40:y0+220,x0:x0+320]=panel
        label=f"Frame {sources[index]['frame']} / "+(suffix[1:] or 'original')
        cv2.putText(sheet,label,(x0+5,y0+24),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,0,0),1)
cv2.imwrite(str(root/'crop-preview.jpg'),sheet)
