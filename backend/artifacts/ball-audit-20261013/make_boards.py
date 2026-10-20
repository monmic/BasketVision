"""Full-frame review boards without model overlays or preselected detections."""
import json
from pathlib import Path
import cv2
import numpy as np

out=Path('/output')
source=Path('/repo/backend/artifacts/ball-crops-20261011')
rows=json.loads((source/'dataset-audit.json').read_text())['frames']
rows=sorted(rows,key=lambda r:r['frame'])
index=[]
for start in range(0,len(rows),6):
    chunk=rows[start:start+6]
    sheet=np.full((3*510,2*854,3),245,dtype=np.uint8)
    for i,row in enumerate(chunk):
        frame=cv2.imread(str(source/'dataset'/row['image']))
        assert frame.shape[:2]==(480,854)
        x,y=(i%2)*854,(i//2)*510
        sheet[y+30:y+510,x:x+854]=frame
        cv2.putText(sheet,f"{row['frame']} {row['episode']} {row['split']}",(x+8,y+22),
                    cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,0),1)
    name=f'board-{start//6+1:02d}.jpg'
    cv2.imwrite(str(out/name),sheet,[cv2.IMWRITE_JPEG_QUALITY,95])
    index.append(dict(board=name,frames=[r['frame'] for r in chunk]))
(out/'boards.json').write_text(json.dumps(index,indent=2))
print('Created',len(index),'boards for',len(rows),'frames')
