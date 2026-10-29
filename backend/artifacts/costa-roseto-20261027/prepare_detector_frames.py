"""Extract the frozen detector pilot sample without running inference."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPLITS = dict(train=[0,6,10,14,18,22,26,30,34,38,42,46,50,54,58],
              val=[60,70,80,90,100,110], test=[120,130,140,150,160,170])

if __name__ == '__main__':
    import argparse
    import cv2
    import numpy as np
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fresh-expanded',action='store_true')
    args=parser.parse_args()
    splits=dict(test=[180,190,200,210,220,230]) if args.fresh_expanded else SPLITS
    out = HERE / ('detector-expanded/fresh' if args.fresh_expanded else 'detector-pilot')
    out.mkdir(exist_ok=False)
    expected=json.loads((HERE/'benchmark/raw.json').read_text())['sourceVideoSha256']
    if hashlib.sha256(Path('/video.mp4').read_bytes()).hexdigest()!=expected:
        raise ValueError('Source video hash differs')
    cap = cv2.VideoCapture('/video.mp4')
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or fps <= 0:
        raise ValueError('Invalid video')
    rows, images = [], []
    try:
        for role, times in splits.items():
            for second in times:
                index = round(second*fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES,index)
                ok, frame = cap.read()
                if not ok: raise ValueError(index)
                file = f'frame-{index:06d}.png'
                if not cv2.imwrite(str(out/file), frame): raise OSError(file)
                rows.append(dict(frame=index,requestedSeconds=second,split=role,
                    file=file,sha256=hashlib.sha256((out/file).read_bytes()).hexdigest(),
                    width=frame.shape[1],height=frame.shape[0]))
                images.append(frame)
    finally:
        cap.release()
    for start in range(0,len(images),2):
        sheet = np.zeros((2*510,854,3),dtype=np.uint8)
        for offset, frame in enumerate(images[start:start+2]):
            sheet[offset*510:offset*510+480] = frame
            row=rows[start+offset]
            cv2.putText(sheet,f'{start+offset}: {row["split"]} {row["requestedSeconds"]}s f{row["frame"]}',
                (8,offset*510+502),0,.6,(255,255,255),1)
        cv2.imwrite(str(out/f'board-{start//2:02d}.jpg'),sheet)
    (out/'frames.json').write_text(json.dumps(dict(fps=fps,frames=rows),indent=2))
    print(f'{len(rows)} pristine frames extracted, no inference')
