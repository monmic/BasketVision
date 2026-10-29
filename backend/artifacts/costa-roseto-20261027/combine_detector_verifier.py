"""Final fixed composition of trained detector and existing frozen verifier.

No training or threshold selection; all samples are now known controls.
"""
import copy
import hashlib
import json
import sys
import time
from pathlib import Path
import cv2
from semantic_verifier import Extractor,probabilities
from benchmark_detector_pilot import score,regressions

BASE=Path(__file__).resolve().parent
HERE=BASE/'detector-pilot'
out=HERE/'composition';out.mkdir(exist_ok=False)
classifier_path=BASE/'adapted-training-corrected/classifier.json'
classifier=json.loads(classifier_path.read_text())
extractor=Extractor('/model.pt')
assert extractor.weights_sha256==classifier['backboneSha256']
assert hashlib.sha256(classifier_path.read_bytes()).hexdigest()=='4c0fdcb8d8fbb7190942ef2b5d2e3cdaf83046b8d29e80ec75e97d57178364ff'
data=json.loads((HERE/'dataset/manifest.json').read_text())
cohorts={}
for role in ['train','val','test']:
    rows=[r for r in data['frames'] if r['split']==role]
    cohorts['costa-'+role]=(dict(frames=[dict(frame=r['frame'],boxes=r['boxes']) for r in rows]),
        {r['frame']:HERE/'dataset'/r['image'] for r in rows})
old=json.loads(Path('/old-dataset/manifest.json').read_text())
truth=json.loads(Path('/old-annotations.json').read_text())
rows=[r for r in old['frames'] if r['split']=='test'];wanted={r['frame'] for r in rows}
cohorts['home-away-control']=(dict(frames=[r for r in truth['frames'] if r['frame'] in wanted]),
    {r['frame']:Path('/old-dataset')/r['image'] for r in rows})
truth=json.loads(Path('/online-annotations.json').read_text())
cohorts['online-control']=(dict(frames=truth['frames']),
    {r['frame']:HERE/'evaluation-stable-warmup'/f'online-{r["frame"]:06d}.png' for r in truth['frames']})
summary={}
for name,(truth,images) in cohorts.items():
    folder=HERE/'evaluation-stable-warmup'
    baseline=json.loads((folder/f'{name}-baseline.json').read_text())
    report=json.loads((folder/f'{name}-pilot.json').read_text())
    elapsed=0.
    for row in report['frames']:
        image=cv2.imread(str(images[row['frame']]))
        crops=[]
        import math
        for c in row['candidates']:
            left,top=max(0,math.floor(c['x1'])),max(0,math.floor(c['y1']))
            right,bottom=min(image.shape[1],math.ceil(c['x2'])),min(image.shape[0],math.ceil(c['y2']))
            if left>=right or top>=bottom:raise ValueError('Invalid proposal')
            crops.append(image[top:bottom,left:right])
        started=time.perf_counter()
        scores=probabilities(extractor.features(crops),classifier)
        elapsed+=time.perf_counter()-started
        row['candidates']=[dict(c,semanticScore=float(s)) for c,s in zip(row['candidates'],scores) if s>=.5]
    summary[name]=dict(verifierSeconds=elapsed,thresholds={str(conf):dict(
        models={k:score(r,truth,conf) for k,r in [('baseline',baseline),('composed',report)]},
        baselineObjectsLost=regressions(dict(baseline=baseline,pilot=report),truth,conf)) for conf in [.02,.12]})
    (out/f'{name}.json').write_text(json.dumps(report,indent=2))
    print(name,{t:{k:[m['tp'],m['fp'],m['fn']] for k,m in r['models'].items()} for t,r in summary[name]['thresholds'].items()},flush=True)
(out/'summary.json').write_text(json.dumps(summary,indent=2))
