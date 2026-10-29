"""Offline, frozen-backbone proposal verifier. Does not create detections/events."""
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO


def crop_tensor(image):
    if image is None or image.ndim != 3 or min(image.shape[:2]) < 1:
        raise ValueError('Nonempty BGR crop required')
    height,width=image.shape[:2]
    scale=128/max(width,height)
    nw,nh=max(1,round(width*scale)),max(1,round(height*scale))
    resized=cv2.resize(image,(nw,nh))
    padded=np.full((128,128,3),114,dtype=np.uint8)
    x,y=(128-nw)//2,(128-nh)//2
    padded[y:y+nh,x:x+nw]=resized
    return torch.from_numpy(padded[:,:,::-1].copy()).permute(2,0,1).float()/255


class Extractor:
    def __init__(self,weights):
        torch.set_num_threads(2)
        blocks=list(YOLO(str(weights)).model.float().cpu().eval().model.children())[:11]
        if len(blocks)!=11 or any(b.f!=-1 for b in blocks):
            raise ValueError('Expected sequential YOLO26 backbone through C2PSA')
        self.backbone=torch.nn.Sequential(*blocks).eval().requires_grad_(False)
        self.weights_sha256=hashlib.sha256(Path(weights).read_bytes()).hexdigest()

    def features(self,images):
        if not images:return np.empty((0,256),dtype=np.float32)
        outputs=[]
        with torch.inference_mode():
            for start in range(0,len(images),32):
                batch=torch.stack([crop_tensor(im) for im in images[start:start+32]])
                outputs.append(self.backbone(batch).mean(dim=(2,3)).numpy())
        return np.concatenate(outputs)


def fit(features,labels):
    if len(features)!=len(labels) or len(features)==0 or len(set(labels.tolist()))!=2:
        raise ValueError('Both reviewed classes required')
    if not np.isfinite(features).all() or not set(labels.tolist())<={0,1}:
        raise ValueError('Finite features and binary reviewed labels required')
    mean=features.mean(axis=0);std=features.std(axis=0).clip(1e-6)
    x=torch.tensor((features-mean)/std,dtype=torch.float64)
    y=torch.tensor(labels,dtype=torch.float64)
    weight=torch.zeros(x.shape[1],dtype=torch.float64,requires_grad=True)
    bias=torch.zeros((),dtype=torch.float64,requires_grad=True)
    optimizer=torch.optim.LBFGS([weight,bias],max_iter=100,line_search_fn='strong_wolfe')
    def closure():
        optimizer.zero_grad()
        loss=torch.nn.functional.binary_cross_entropy_with_logits(x@weight+bias,y)+.005*weight.square().sum()
        loss.backward();return loss
    optimizer.step(closure)
    return dict(mean=mean.tolist(),std=std.tolist(),weight=weight.detach().tolist(),bias=bias.item())


def probabilities(features,model):
    standardized=(features-np.asarray(model['mean']))/np.asarray(model['std'])
    logits=standardized@np.asarray(model['weight'])+model['bias']
    return 1/(1+np.exp(-np.clip(logits,-700,700)))


def metrics(labels,scores):
    kept=scores>=.5
    return dict(ballKept=int(np.sum(kept&(labels==1))),ballRejected=int(np.sum(~kept&(labels==1))),
                falseKept=int(np.sum(kept&(labels==0))),falseRejected=int(np.sum(~kept&(labels==0))))


def train(weights,examples,output):
    import time
    output=Path(output);output.mkdir(exist_ok=False)
    source=Path(examples)/'manifest.json'
    manifest=json.loads(source.read_text())
    rows=manifest['examples'];images=[]
    for row in rows:
        path=Path(examples)/row['file']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Changed reviewed crop')
        images.append(cv2.imread(str(path)))
    extractor=Extractor(weights);started=time.perf_counter()
    features=extractor.features(images)
    labels=np.asarray([r['label']=='active_ball' for r in rows],dtype=np.int64)
    groups=np.asarray([r['episode'] for r in rows])
    folds=[]
    for group in sorted(set(groups)):
        validation=groups==group
        model=fit(features[~validation],labels[~validation])
        scores=probabilities(features[validation],model)
        item=dict(episode=group,examples=int(validation.sum()),metrics=metrics(labels[validation],scores))
        folds.append(item);print(json.dumps(item),flush=True)
    model=dict(fit(features,labels),schemaVersion=1,threshold=.5,backboneSha256=extractor.weights_sha256,
               trainingManifestSha256=hashlib.sha256(source.read_bytes()).hexdigest(),
               featureProtocol='yolo26n first 11 sequential blocks, letterbox 128 BGR->RGB /255, spatial mean',
               l2=.01,trainingSources=sorted({r['sourceVideo'] for r in rows}),
               notice='Experimental proposal score, not calibrated probability. Training sources are explicitly listed; freeze this model before evaluating unseen frames.')
    model_path=output/'classifier.json'
    with model_path.open('x') as stream:json.dump(model,stream,indent=2,allow_nan=False)
    report=dict(examples=len(rows),featureDimensions=features.shape[1],folds=folds,
                classifierSha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
                elapsedSeconds=time.perf_counter()-started,
                notice='Whole-episode cross-validation on known development sources, not an untouched independent test.')
    with (output/'report.json').open('x') as stream:json.dump(report,stream,indent=2)
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('weights',type=Path);p.add_argument('examples',type=Path);p.add_argument('output',type=Path)
    args=p.parse_args();train(args.weights,args.examples,args.output)
