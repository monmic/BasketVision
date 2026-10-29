"""Offline last-block adaptation; production worker/model remain untouched."""
import copy
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from semantic_verifier import Extractor, crop_tensor, metrics
from spatial_verifier import spatial_pool, control_crops
from balanced_verifier import balanced_weights
from context_verifier import BASE, read, sha


class AdapterVerifier(torch.nn.Module):
    def __init__(self, extractor, classifier):
        super().__init__()
        self.prefix = torch.nn.Sequential(*list(extractor.backbone.children())[:10]).eval().requires_grad_(False)
        self.adapter = copy.deepcopy(extractor.backbone[10]).eval().requires_grad_(True)
        self.register_buffer('mean',torch.tensor(classifier['mean'],dtype=torch.float32))
        self.register_buffer('std',torch.tensor(classifier['std'],dtype=torch.float32))
        self.head = torch.nn.Linear(1024,1)
        with torch.no_grad():
            self.head.weight.copy_(torch.tensor(classifier['weight'],dtype=torch.float32).reshape(1,-1))
            self.head.bias.fill_(classifier['bias'])
        self.eval()

    def from_prefix(self, values):
        z = spatial_pool(self.adapter(values))
        return self.head((z-self.mean)/self.std).flatten()

    def forward(self, images):
        with torch.no_grad():
            values = self.prefix(images)
        return self.from_prefix(values)


def prefix_features(model, crops):
    results = []
    with torch.no_grad():
        for start in range(0,len(crops),32):
            batch = torch.stack([crop_tensor(c) for c in crops[start:start+32]])
            results.append(model.prefix(batch))
    return torch.cat(results)


def score(model, prefix):
    with torch.no_grad():
        logits = torch.cat([model.from_prefix(prefix[start:start+32]) for start in range(0,len(prefix),32)])
    return logits.sigmoid().numpy(),logits


def weighted_bce(logits, labels, weights):
    return float((torch.nn.functional.binary_cross_entropy_with_logits(logits,labels,reduction='none')*weights).sum()/weights.sum())


def main():
    torch.manual_seed(20261029)
    root = BASE/'adapter-verifier'
    root.mkdir(exist_ok=False)
    data_root = BASE/'balanced-verifier'
    data_path = data_root/'dataset.json'
    dataset = read(data_path)
    classifier_path = data_root/'balanced-classifier.json'
    classifier = read(classifier_path)
    assert classifier['manifestSha256'] == sha(data_path)
    rows = dataset['examples']
    train = [r for r in rows if r['retained'] and r['partition'] == 'train']
    validation = [r for r in rows if r['retained'] and r['partition'] == 'validation']
    assert [r['index'] for r in train] == classifier['trainingIndices']
    assert len(train) == 104 and len(validation) == 72
    def crops(subset):
        result = []
        for row in subset:
            path = data_root/row['newFile'] if 'newFile' in row else BASE/'context-verifier'/row['detailFile']
            assert sha(path) == row['pixelSha256']
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError(path)
            result.append(image)
        return result
    extractor = Extractor('/model.pt')
    assert extractor.weights_sha256 == classifier['backboneSha256']
    model = AdapterVerifier(extractor,classifier)
    original = copy.deepcopy(model.state_dict())
    started = time.perf_counter()
    train_prefix = prefix_features(model,crops(train))
    val_prefix = prefix_features(model,crops(validation))
    y = torch.tensor([r['label'] for r in train],dtype=torch.float32)
    vy = torch.tensor([r['label'] for r in validation],dtype=torch.float32)
    weights = torch.tensor(balanced_weights(train),dtype=torch.float32)
    vw = torch.tensor(balanced_weights(validation),dtype=torch.float32)
    baseline_scores,logits = score(model,val_prefix)
    baseline_loss = weighted_bce(logits,vy,vw)
    best_loss,best_epoch,best_state = baseline_loss,0,copy.deepcopy(original)
    history = [dict(epoch=0,validationBce=baseline_loss)]
    optimizer = torch.optim.AdamW([dict(params=model.adapter.parameters(),lr=1e-5),
                                  dict(params=model.head.parameters(),lr=1e-4)],weight_decay=0)
    generator = torch.Generator().manual_seed(20261029)
    for epoch in range(1,11):
        order = torch.randperm(len(train),generator=generator)
        for start in range(0,len(train),16):
            indices = order[start:start+16]
            optimizer.zero_grad()
            logits = model.from_prefix(train_prefix[indices])
            loss = (torch.nn.functional.binary_cross_entropy_with_logits(logits,y[indices],reduction='none')*weights[indices]*len(train)).mean()+.005*model.head.weight.square().sum()
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1)
            optimizer.step()
        _,logits = score(model,val_prefix)
        value = weighted_bce(logits,vy,vw)
        history.append(dict(epoch=epoch,validationBce=value))
        if value < best_loss:
            best_loss,best_epoch,best_state = value,epoch,copy.deepcopy(model.state_dict())
        print(json.dumps(history[-1]),flush=True)
    model.load_state_dict(best_state)
    training_seconds = time.perf_counter()-started
    buffers = set(dict(model.named_buffers()))
    changed = [name for name,value in best_state.items() if not torch.equal(original[name],value)]
    assert not any(name.startswith('prefix.') or name in buffers for name in changed)
    assert all(name.startswith(('adapter.','head.')) for name in changed)
    path = root/'selected.pth'
    torch.save(dict(state=best_state,selectedEpoch=best_epoch,datasetSha256=sha(data_path),
                    classifierSha256=sha(classifier_path),backboneSha256=extractor.weights_sha256),path)
    frozen_hash = sha(path)
    proof = dict(changedTensors=changed,totalStateTensors=len(best_state),unchangedBuffers=len(buffers),
                 trainableParameters=sum(p.numel() for p in model.parameters() if p.requires_grad),
                 frozenPrefix=True,selectedEpoch=best_epoch)
    (root/'preservation.json').write_text(json.dumps(proof,indent=2))
    adapted_scores,_ = score(model,val_prefix)
    pairs = {}
    for source in sorted({r['sourceVideo'] for r in validation}):
        selected = np.asarray([r['sourceVideo'] == source for r in validation])
        truth = vy.numpy().astype(np.int64)[selected]
        pair = dict(kind='validation',reference=metrics(truth,baseline_scores[selected]),adapted=metrics(truth,adapted_scores[selected]))
        pair['predictions'] = [dict(index=r['index'],reference=float(a),adapted=float(b)) for r,a,b in zip(validation,baseline_scores,adapted_scores) if r['sourceVideo'] == source]
        pairs['validation-'+source] = pair
    baseline_model = AdapterVerifier(extractor,classifier)
    capture = cv2.VideoCapture('/video.mp4')
    try:
        for name,label_path in [('proposals',BASE/'adapted-review.json'),('trackIdentities',BASE/'continuous-review/review.json')]:
            observations = read(label_path)['observations']
            started = time.perf_counter()
            prefix = prefix_features(model,control_crops(observations,capture))
            a,_ = score(baseline_model,prefix)
            b,_ = score(model,prefix)
            valid = np.asarray([r.get('label',r.get('visualObject')) in ('ball','non_ball') for r in observations])
            truth = np.asarray([r.get('label',r.get('visualObject')) == 'ball' for r in observations],dtype=np.int64)
            pair = dict(reference=metrics(truth[valid],a[valid]),adapted=metrics(truth[valid],b[valid]),
                        labelSha256=sha(label_path),pairedScoreSeconds=time.perf_counter()-started,
                        predictions=[dict(index=r['index'],reference=float(x),adapted=float(y)) for r,x,y in zip(observations,a,b)])
            # Initialisation must reproduce the previous classifier's decisions.
            old = read(data_root/'summary.json')['pairs'][name]['balanced']
            assert pair['reference'] == old
            pairs[name] = pair
            print(json.dumps(dict(control=name,reference=pair['reference'],adapted=pair['adapted'])),flush=True)
    finally:
        capture.release()
    assert sha(path) == frozen_hash
    passed = all((p.get('kind') == 'validation' or (p['adapted']['ballRejected'] == 0 and p['adapted']['falseRejected'] > 0))
                 and p['adapted']['ballRejected'] <= p['reference']['ballRejected']
                 and p['adapted']['falseKept'] <= p['reference']['falseKept'] for p in pairs.values())
    summary = dict(selectedEpoch=best_epoch,history=history,trainingSeconds=training_seconds,checkpointSha256=frozen_hash,
                   datasetSha256=sha(data_path),classifierSha256=sha(classifier_path),pairs=pairs,
                   eligibleForContinuousReplay=passed,productionRelease=False)
    (root/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(dict(selectedEpoch=best_epoch,trainingSeconds=training_seconds,eligibleForContinuousReplay=passed)),flush=True)


if __name__ == '__main__':
    main()
