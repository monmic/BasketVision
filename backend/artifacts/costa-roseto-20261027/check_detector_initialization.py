"""Compare untrained single-class transfer with source ball predictions."""
import json
from pathlib import Path
import numpy as np
import torch
from ultralytics import YOLO
from ultralytics.nn.tasks import DetectionModel

HERE=Path(__file__).resolve().parent/'detector-pilot'
torch.set_num_threads(2)
source=YOLO('/model.pt')
single=DetectionModel(source.model.yaml,nc=1,verbose=False)
single.names={0:'sports ball'}
single.load(source.model,verbose=False)
adapted=YOLO('/model.pt');adapted.model=single
samples=[HERE/'frame-000779.png',HERE/'frame-002697.png',HERE/'evaluation/online-000045.png']
rows=[]
for path in samples:
    results={}
    for name,model,cls in [('baseline',source,32),('single-untrained',adapted,0)]:
        prediction=model.predict(str(path),classes=[cls],conf=.02,imgsz=960,device='cpu',verbose=False)[0]
        results[name]=[dict(box=b.xyxy[0].tolist(),confidence=float(b.conf.item())) for b in prediction.boxes]
    rows.append(dict(image=path.name,predictions=results))
report=dict(notice='No optimizer or fitting; detect transfer effects before attributing changes to training.',frames=rows)
(HERE/'initialization-check.json').write_text(json.dumps(report,indent=2))
print(json.dumps({r['image']:{k:len(v) for k,v in r['predictions'].items()} for r in rows}))
