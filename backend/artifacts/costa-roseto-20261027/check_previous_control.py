"""Evaluate frozen verifiers on the existing separately annotated 720p control."""
import copy
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import cv2

from semantic_verifier import Extractor,probabilities
sys.path.insert(0,'/scripts')
from evaluate_ball_clip import evaluate

HERE=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
base=read('/previous/baseline-control.json');annotations=read('/annotations.json')
extractor=Extractor('/model.pt');cap=cv2.VideoCapture('/video.mp4')
if not cap.isOpened() or not math.isclose(cap.get(cv2.CAP_PROP_FPS),base['source']['fps']):raise ValueError('Wrong control video')
rows=copy.deepcopy(base['frames']);features=[]
try:
    for row in rows:
        cap.set(cv2.CAP_PROP_POS_FRAMES,row['frame']);ok,frame=cap.read()
        if not ok:raise ValueError(row['frame'])
        crops=[]
        for c in row['candidates']:
            left,top=max(0,math.floor(c['x1'])),max(0,math.floor(c['y1']))
            right,bottom=min(frame.shape[1],math.ceil(c['x2'])),min(frame.shape[0],math.ceil(c['y2']))
            if left>=right or top>=bottom:raise ValueError('Empty control crop')
            crops.append(frame[top:bottom,left:right])
        features.append(extractor.features(crops))
finally:cap.release()
results={'baseline':evaluate(base,annotations)['metrics']['raw']}
for name,folder in [('original','training'),('adapted','adapted-training-corrected')]:
    path=HERE/folder/'classifier.json';model=read(path)
    if model['backboneSha256']!=extractor.weights_sha256:raise ValueError('Backbone differs')
    report=copy.deepcopy(base)
    for row,x in zip(report['frames'],features):
        scores=probabilities(x,model)
        row['candidates']=[dict(c,semanticScore=float(score)) for c,score in zip(row['candidates'],scores) if score>=.5]
    results[name]=dict(metrics=evaluate(report,annotations)['metrics']['raw'],classifierSha256=hashlib.sha256(path.read_bytes()).hexdigest())
with (HERE/'previous-control.json').open('x') as stream:json.dump(results,stream,indent=2)
print(json.dumps(results,indent=2))
