"""Sequence holdout, repetition reduction and source/class-balanced fit."""
import json
import math
import time
from collections import Counter
from pathlib import Path
import cv2
import numpy as np
import torch
from semantic_verifier import Extractor, fit, probabilities, metrics
from spatial_verifier import features, control_crops
from context_verifier import BASE, VIDEOS, read, sha


def partition(row):
    t = row['timestamp']
    if row['sourceVideo'] == VIDEOS['costa']:
        if not 0 <= t < 60:
            raise ValueError('Costa training pool outside first minute')
        return 'validation' if t >= 44 else ('guard' if t >= 42 else 'train')
    return 'validation' if 500 <= t < 560 else 'train'


def repetition_key(row):
    a,b,c,d = row['bounds']
    return (row['sourceVideo'],row['label'],math.floor(row['timestamp']),math.floor((a+c)/128),math.floor((b+d)/128))


def reduce_rows(rows):
    priorities = {'new-ground-truth':0,'train-ground-truth':1,'verified-proposal':2}
    selected, seen = [], set()
    for row in sorted(rows,key=lambda r:(priorities[r['provenance']],r['index'])):
        key = repetition_key(row)
        if key not in seen:
            selected.append(row)
            seen.add(key)
    return sorted(selected,key=lambda r:r['index'])


def balanced_weights(rows):
    groups = Counter((r['sourceVideo'],r['label']) for r in rows)
    if len(groups) != 4:
        raise ValueError('Both reviewed classes from both sources required')
    return np.asarray([1/(4*groups[(r['sourceVideo'],r['label'])]) for r in rows])


def fit_weighted(x, y, weights):
    # Same logistic fit/L2 as semantic_verifier.fit, changing only BCE weights.
    if len(x) != len(y) or len(y) != len(weights) or set(y.tolist()) != {0,1}:
        raise ValueError('Aligned binary labels and weights required')
    if not np.isfinite(weights).all() or np.any(weights <= 0):
        raise ValueError('Positive finite weights required')
    mean,std = x.mean(axis=0),x.std(axis=0).clip(1e-6)
    values = torch.tensor((x-mean)/std,dtype=torch.float64)
    labels = torch.tensor(y,dtype=torch.float64)
    sample = torch.tensor(weights/weights.sum(),dtype=torch.float64)
    w = torch.zeros(x.shape[1],dtype=torch.float64,requires_grad=True)
    b = torch.zeros((),dtype=torch.float64,requires_grad=True)
    optimizer = torch.optim.LBFGS([w,b],max_iter=100,line_search_fn='strong_wolfe')
    def closure():
        optimizer.zero_grad()
        loss = (torch.nn.functional.binary_cross_entropy_with_logits(values@w+b,labels,reduction='none')*sample).sum()+.005*w.square().sum()
        loss.backward()
        return loss
    optimizer.step(closure)
    return dict(mean=mean.tolist(),std=std.tolist(),weight=w.detach().tolist(),bias=b.item())


def gate(pairs):
    return bool(pairs) and all((p.get('kind') == 'validation' or
                               (p['balanced']['ballRejected'] == 0 and p['balanced']['falseRejected'] > 0))
                              and p['balanced']['ballRejected'] <= p['reference']['ballRejected']
                              and p['balanced']['falseKept'] <= p['reference']['falseKept'] for p in pairs)


def main():
    root = BASE/'balanced-verifier'
    previous = BASE/'context-verifier'
    prior = read(previous/'manifest.json')
    reviewed = read(root/'reviewed.json')
    rows, images = [], []
    for r in prior['examples']:
        path = previous/r['detailFile']
        assert sha(path) == r['detailSha256']
        fps = reviewed['fps'] if r['sourceVideo'] == VIDEOS['costa'] else 30
        rows.append(dict(r,index=len(rows),timestamp=r['frame']/fps,pixelSha256=sha(path)))
        images.append(cv2.imread(str(path)))
    for r in reviewed['frames']:
        path = root/'reference'/r['file']
        assert sha(path) == r['sha256']
        if r['status'] != 'visible':
            continue
        image = cv2.imread(str(path))
        for bounds in r['pixelBoxes']:
            a,b,c,d = bounds
            crop = image[b:d,a:c]
            file = root/f'new-{r["frame"]}.png'
            assert cv2.imwrite(str(file),crop)
            rows.append(dict(index=len(rows),sourceVideo=VIDEOS['costa'],frame=r['frame'],timestamp=r['frame']/reviewed['fps'],
                             bounds=bounds,label=1,provenance='new-ground-truth',pixelSha256=sha(file),newFile=file.name))
            images.append(crop)
    selected = reduce_rows(rows)
    for row in rows:
        row['partition'] = partition(row)
        row['retained'] = row['index'] in {r['index'] for r in selected}
    manifest = dict(examples=rows,previousManifestSha256=sha(previous/'manifest.json'),annotationSha256=sha(root/'reviewed.json'))
    (root/'dataset.json').write_text(json.dumps(manifest,indent=2))
    train = [r for r in selected if r['partition'] == 'train']
    validation = [r for r in selected if r['partition'] == 'validation']
    weights = balanced_weights(train)
    extractor = Extractor('/model.pt')
    assert extractor.weights_sha256 == read(BASE/'adapted-training-corrected/classifier.json')['backboneSha256']
    started = time.perf_counter()
    x = features(extractor,[images[r['index']] for r in train])[0]
    y = np.asarray([r['label'] for r in train],dtype=np.int64)
    models = dict(reference=fit(x,y),balanced=fit_weighted(x,y,weights))
    hashes = {}
    for name,model in models.items():
        model.update(threshold=.5,l2=.01,manifestSha256=sha(root/'dataset.json'),backboneSha256=extractor.weights_sha256,
                     trainingIndices=[r['index'] for r in train],weights=weights.tolist() if name == 'balanced' else None)
        path = root/(name+'-classifier.json')
        with path.open('x') as stream:
            json.dump(model,stream,allow_nan=False)
        hashes[name] = sha(path)
    training_seconds = time.perf_counter()-started
    pairs = {}
    for source in sorted({r['sourceVideo'] for r in validation}):
        subset = [r for r in validation if r['sourceVideo'] == source]
        z = features(extractor,[images[r['index']] for r in subset])[0]
        truth = np.asarray([r['label'] for r in subset],dtype=np.int64)
        pair = dict(kind='validation',predictions={})
        for name,model in models.items():
            scores = probabilities(z,model)
            pair[name] = metrics(truth,scores)
            pair['predictions'][name] = [dict(index=r['index'],score=float(s)) for r,s in zip(subset,scores)]
        pairs['validation-'+source] = pair
        print(json.dumps(dict(source=source,reference=pair['reference'],balanced=pair['balanced'])),flush=True)
    capture = cv2.VideoCapture('/video.mp4')
    try:
        for name,path in [('proposals',BASE/'adapted-review.json'),('trackIdentities',BASE/'continuous-review/review.json')]:
            observed = read(path)['observations']
            z = features(extractor,control_crops(observed,capture))[0]
            valid = np.asarray([r.get('label',r.get('visualObject')) in ('ball','non_ball') for r in observed])
            truth = np.asarray([r.get('label',r.get('visualObject')) == 'ball' for r in observed],dtype=np.int64)
            pair = dict(labelSha256=sha(path),predictions={})
            for mode,model in models.items():
                scores = probabilities(z,model)
                pair[mode] = metrics(truth[valid],scores[valid])
                pair['predictions'][mode] = [dict(index=r['index'],score=float(s)) for r,s in zip(observed,scores)]
            pairs[name] = pair
            print(json.dumps(dict(control=name,reference=pair['reference'],balanced=pair['balanced'])),flush=True)
    finally:
        capture.release()
    assert all(sha(root/(name+'-classifier.json')) == hashes[name] for name in models)
    summary = dict(poolExamples=len(rows),retained=len(selected),train=len(train),validation=len(validation),
                   groupCounts={f'{s}:{label}':n for (s,label),n in Counter((r['sourceVideo'],r['label']) for r in train).items()},
                   classifierSha256=hashes,trainingSeconds=training_seconds,pairs=pairs,
                   eligibleForContinuousReplay=gate(list(pairs.values())),productionRelease=False)
    (root/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k != 'pairs'}),flush=True)


if __name__ == '__main__':
    main()
