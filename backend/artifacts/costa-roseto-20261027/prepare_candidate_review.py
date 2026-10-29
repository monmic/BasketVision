"""All preselected-frame proposals, native context, labels hidden during review."""
import json
import math
import argparse
from pathlib import Path
import cv2
import numpy as np

HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
group=p.add_mutually_exclusive_group();group.add_argument('--context',action='store_true');group.add_argument('--adapted',action='store_true')
args=p.parse_args()
base=HERE/('context' if args.context else 'adapted-benchmark' if args.adapted else 'benchmark');out=base/'candidate-review';out.mkdir(exist_ok=False)
report=json.loads((base/'raw.json').read_text());rows=[];tiles=[]
for frame in report['frames']:
    reference_dir=HERE/'benchmark/reference' if args.context else base/'reference'
    image=cv2.imread(str(reference_dir/frame['referenceFile']))
    if image is None:raise ValueError('Missing pristine reference')
    for candidate_index,c in enumerate(frame['candidates']):
        radius=max(24,math.ceil(max(c['width'],c['height'])*2))
        cx,cy=round(c['centerX']),round(c['centerY'])
        left,top=max(0,cx-radius),max(0,cy-radius)
        crop=image[top:min(image.shape[0],cy+radius),left:min(image.shape[1],cx+radius)].copy()
        cv2.rectangle(crop,(round(c['x1'])-left,round(c['y1'])-top),(round(c['x2'])-left,round(c['y2'])-top),(0,255,255),1)
        tiles.append(cv2.resize(crop,(200,150)))
        rows.append(dict(index=len(rows),frame=frame['frame'],candidateIndex=candidate_index,candidate=c))
for start in range(0,len(tiles),24):
    sheet=np.zeros((4*180,6*200,3),np.uint8)
    for n,tile in enumerate(tiles[start:start+24]):
        row=rows[start+n];x,y=n%6*200,n//6*180
        sheet[y:y+150,x:x+200]=tile
        cv2.putText(sheet,f'{row["index"]} f{row["frame"]}',(x+3,y+172),0,.45,(255,255,255),1)
    if not cv2.imwrite(str(out/f'board-{start//24:02d}.jpg'),sheet):raise ValueError('Write failed')
with (out/'manifest.json').open('x') as stream:json.dump(rows,stream,indent=2)
print(f'Prepared all {len(rows)} proposal contexts, without semantic score overlays')
