"""Fixed additional first-minute frames; no model proposals or inference."""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np

BASE = Path(__file__).resolve().parent

if __name__ == '__main__':
    out = BASE/'balanced-verifier'
    out.mkdir(exist_ok=False)
    refs = out/'reference'
    refs.mkdir()
    video = Path('/video.mp4')
    expected = json.loads((BASE/'benchmark/raw.json').read_text())['sourceVideoSha256']
    assert hashlib.sha256(video.read_bytes()).hexdigest() == expected
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    rows, images = [], []
    try:
        for second in range(15,60,4):
            index = round(second*fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES,index)
            ok,image = cap.read()
            if not ok:
                raise ValueError(index)
            path = refs/f'frame-{index:06d}.png'
            assert cv2.imwrite(str(path),image)
            rows.append(dict(frame=index,requestedSeconds=second,file=path.name,
                             sha256=hashlib.sha256(path.read_bytes()).hexdigest(),width=image.shape[1],height=image.shape[0]))
            images.append(image)
    finally:
        cap.release()
    for start in range(0,len(images),2):
        board = np.zeros((1020,854,3),dtype=np.uint8)
        for i,image in enumerate(images[start:start+2]):
            board[i*510:i*510+480] = image
            cv2.putText(board,f'{rows[start+i]["requestedSeconds"]}s f{rows[start+i]["frame"]}',(8,i*510+502),0,.6,(255,255,255),1)
        assert cv2.imwrite(str(refs/f'board-{start//2:02d}.jpg'),board)
    (out/'frames.json').write_text(json.dumps(dict(fps=fps,sourceVideoSha256=expected,frames=rows),indent=2))
    print(f'{len(rows)} fixed frames extracted')
