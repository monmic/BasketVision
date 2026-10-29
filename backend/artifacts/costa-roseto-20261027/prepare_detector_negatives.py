"""Mine only training-source background contexts; human review is still required."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

BASE=Path(__file__).resolve().parent


def crop_bounds(candidate,width,height):
    radius=max(64,math.ceil(max(candidate[2]-candidate[0],candidate[3]-candidate[1])*2))
    cx,cy=(candidate[0]+candidate[2])/2,(candidate[1]+candidate[3])/2
    return [max(0,math.floor(cx-radius)),max(0,math.floor(cy-radius)),
            min(width,math.ceil(cx+radius)),min(height,math.ceil(cy+radius))]


def excludes_balls(crop,balls,width,height,padding=16):
    for x1,y1,x2,y2 in balls:
        ball=[max(0,x1*width-padding),max(0,y1*height-padding),
              min(width,x2*width+padding),min(height,y2*height+padding)]
        if max(crop[0],ball[0])<min(crop[2],ball[2]) and max(crop[1],ball[1])<min(crop[3],ball[3]):
            return False
    return True


if __name__=='__main__':
    import cv2
    import numpy as np
    import torch
    from ultralytics import YOLO
    out=BASE/'detector-expanded';out.mkdir(exist_ok=False)
    (out/'negative-review').mkdir()
    read=lambda path:json.loads(Path(path).read_text())
    source=BASE/'detector-pilot/training-stable-warmup/weights/best.pt'
    expected=read(BASE/'detector-pilot/training-stable-warmup/frozen.json')['selectedWeightsSha256']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
    torch.set_num_threads(2);model=YOLO(str(source))
    old=read('/old-dataset/manifest.json');annotations=read('/old-annotations.json')
    truth={r['frame']:r['boxes'] for r in annotations['frames']}
    pilot=read(BASE/'detector-pilot/dataset/manifest.json')
    cohorts={'costa':[(r['frame'],'first60',BASE/'detector-pilot/dataset'/r['image'],r['boxes']) for r in pilot['frames'] if r['split']=='train' and r['boxes']],
             'home-away':[(r['frame'],r['episode'],Path('/old-dataset')/r['image'],truth[r['frame']]) for r in old['frames'] if r['split']=='train']}
    selected=[]
    for name,rows in cohorts.items():
        options=[]
        for frame,episode,path,boxes in rows:
            image=cv2.imread(str(path));height,width=image.shape[:2]
            prediction=model.predict(image,classes=[0],imgsz=960,conf=.02,device='cpu',verbose=False)[0]
            for detection in prediction.boxes:
                box=detection.xyxy[0].tolist();bounds=crop_bounds(box,width,height)
                if not excludes_balls(bounds,boxes,width,height):continue
                options.append(dict(source=name,frame=frame,episode=episode,path=str(path),sourceSha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    cropBounds=bounds,ballBoxes=boxes,width=width,height=height,
                    confidence=float(detection.conf.item()),proposalBox=box))
        frame_counts=Counter();episode_counts=Counter();chosen=[]
        for item in sorted(options,key=lambda r:(-r['confidence'],r['frame'],r['cropBounds'])):
            if frame_counts[item['frame']]>=2 or (name=='home-away' and episode_counts[item['episode']]>=4):continue
            if any(item['frame']==r['frame'] and abs(item['cropBounds'][0]-r['cropBounds'][0])<64 and abs(item['cropBounds'][1]-r['cropBounds'][1])<64 for r in chosen):continue
            chosen.append(item);frame_counts[item['frame']]+=1;episode_counts[item['episode']]+=1
            if len(chosen)==12:break
        selected.extend(chosen)
    tiles=[]
    for index,row in enumerate(selected):
        image=cv2.imread(row['path']);left,top,right,bottom=row['cropBounds']
        crop=image[top:bottom,left:right];file=f'negative-review/crop-{index:02d}.png'
        if not cv2.imwrite(str(out/file),crop):raise OSError(file)
        row.update(index=index,file=file,sha256=hashlib.sha256((out/file).read_bytes()).hexdigest(),status='unreviewed')
        tile=np.zeros((280,256,3),np.uint8);tile[:256]=cv2.resize(crop,(256,256),interpolation=cv2.INTER_NEAREST)
        cv2.putText(tile,f'{index} {row["source"]} f{row["frame"]}',(4,274),0,.4,(255,255,255),1);tiles.append(tile)
    for start in range(0,len(tiles),12):
        sheet=np.zeros((4*280,3*256,3),np.uint8)
        for j,tile in enumerate(tiles[start:start+12]):sheet[j//3*280:(j//3+1)*280,j%3*256:(j%3+1)*256]=tile
        cv2.imwrite(str(out/f'negative-review/board-{start//12:02d}.png'),sheet)
    (out/'negative-review/manifest.json').write_text(json.dumps(dict(miningModelSha256=expected,crops=selected),indent=2))
    print(dict(Counter(r['source'] for r in selected)),flush=True)
