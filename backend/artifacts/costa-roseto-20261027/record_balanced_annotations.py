"""Native visual boxes selected without model predictions; frozen before fit."""
import hashlib
import json
from pathlib import Path

BOXES = {15:[665,177,679,192],19:[309,88,322,101],23:[339,329,357,346],
         27:[578,218,593,233],31:[482,99,495,112],35:[379,119,392,132],
         51:[448,47,462,61],55:[171,257,189,275]}
BASE = Path(__file__).resolve().parent

if __name__ == '__main__':
    import argparse
    import cv2
    import numpy as np
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    args = parser.parse_args()
    root = BASE/'balanced-verifier'
    data = json.loads((root/'frames.json').read_text())
    patches = []
    for row in data['frames']:
        path = root/'reference'/row['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
        second = row['requestedSeconds']
        box = BOXES.get(second)
        row.update(pixelBoxes=[box] if box else [], status='visible' if box else ('absent' if second == 39 else 'uncertain'))
        if box:
            x1,y1,x2,y2 = box
            assert 0 <= x1 < x2 <= row['width'] and 0 <= y1 < y2 <= row['height']
            image = cv2.imread(str(path))
            cx,cy = (x1+x2)//2,(y1+y2)//2
            left,top = max(0,cx-40),max(0,cy-40)
            crop = image[top:top+80,left:left+80].copy()
            cv2.rectangle(crop,(x1-left,y1-top),(x2-left,y2-top),(0,255,0),1)
            patch = cv2.resize(crop,(240,240),interpolation=cv2.INTER_NEAREST)
            cv2.putText(patch,f'{second}s',(5,20),0,.6,(255,255,255),1)
            patches.append(patch)
    board = np.zeros((4*240,3*240,3),dtype=np.uint8)
    for i,patch in enumerate(patches):
        board[(i//3)*240:(i//3+1)*240,(i%3)*240:(i%3+1)*240] = patch
    assert cv2.imwrite(str(root/'annotation-review.png'),board)
    if args.freeze:
        data['notice'] = 'Pristine full frame and enlarged native context inspected. 43/47/59s uncertain (hand/occlusion ambiguity), 39s title card. No model inference; labels apply to active ball only.'
        with (root/'reviewed.json').open('x') as stream:
            json.dump(data,stream,indent=2)
    print(f'{len(patches)} proposed visible ball boxes; freeze only after context review')
