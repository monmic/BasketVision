"""Restore selected weights and independently verify preservation and controls."""
import json
import cv2
import numpy as np
import torch
from adapter_verifier import AdapterVerifier, prefix_features, score, weighted_bce
from semantic_verifier import Extractor
from balanced_verifier import balanced_weights
from context_verifier import BASE, read, sha
from spatial_verifier import control_crops
from audit_spatial_verifier import counts


if __name__ == '__main__':
    root = BASE/'adapter-verifier'
    old = BASE/'balanced-verifier'
    summary = read(root/'summary.json')
    proof = read(root/'preservation.json')
    checkpoint = torch.load(root/'selected.pth',map_location='cpu',weights_only=True)
    assert sha(root/'selected.pth') == summary['checkpointSha256']
    assert checkpoint['datasetSha256'] == summary['datasetSha256'] == sha(old/'dataset.json')
    assert checkpoint['classifierSha256'] == summary['classifierSha256'] == sha(old/'balanced-classifier.json')
    dataset = read(old/'dataset.json')
    assert read(old/'audit.json')['datasetSha256'] == sha(old/'dataset.json')
    classifier = read(old/'balanced-classifier.json')
    train = [r for r in dataset['examples'] if r['retained'] and r['partition'] == 'train']
    validation = [r for r in dataset['examples'] if r['retained'] and r['partition'] == 'validation']
    assert classifier['trainingIndices'] == [r['index'] for r in train]
    assert not set(classifier['trainingIndices']) & {r['index'] for r in validation}
    extractor = Extractor('/model.pt')
    assert extractor.weights_sha256 == checkpoint['backboneSha256']
    model = AdapterVerifier(extractor,classifier)
    initial = model.state_dict()
    selected = checkpoint['state']
    buffers = set(dict(model.named_buffers()))
    assert set(initial) == set(selected)
    changed = [name for name in initial if not torch.equal(initial[name],selected[name])]
    assert changed == proof['changedTensors']
    assert not any(name.startswith('prefix.') or name in buffers for name in changed)
    assert all(name.startswith(('adapter.','head.')) for name in changed)
    assert len(buffers) == proof['unchangedBuffers']
    assert sum(p.numel() for p in model.parameters() if p.requires_grad) == proof['trainableParameters']
    history = summary['history']
    assert [r['epoch'] for r in history] == list(range(11))
    best = min(history,key=lambda r:r['validationBce'])
    assert best['epoch'] == checkpoint['selectedEpoch'] == summary['selectedEpoch']
    model.load_state_dict(selected)
    crops = []
    for row in validation:
        path = old/row['newFile'] if 'newFile' in row else BASE/'context-verifier'/row['detailFile']
        assert sha(path) == row['pixelSha256']
        crops.append(cv2.imread(str(path)))
    actual,logits = score(model,prefix_features(model,crops))
    labels = torch.tensor([r['label'] for r in validation],dtype=torch.float32)
    weights = torch.tensor(balanced_weights(validation),dtype=torch.float32)
    assert abs(weighted_bce(logits,labels,weights)-best['validationBce']) < 1e-5
    actual_by_index = {r['index']:float(s) for r,s in zip(validation,actual)}
    capture = cv2.VideoCapture('/video.mp4')
    try:
        for key,pair in summary['pairs'].items():
            if pair.get('kind') == 'validation':
                source = key[len('validation-'):]
                reviewed = [dict(index=r['index'],label='ball' if r['label'] else 'non_ball') for r in validation if r['sourceVideo'] == source]
                scored = actual_by_index
            else:
                path = BASE/('adapted-review.json' if key == 'proposals' else 'continuous-review/review.json')
                assert sha(path) == pair['labelSha256']
                reviewed = read(path)['observations']
                scores,_ = score(model,prefix_features(model,control_crops(reviewed,capture)))
                scored = {r['index']:float(s) for r,s in zip(reviewed,scores)}
            for mode in ['reference','adapted']:
                assert counts(reviewed,pair['predictions'],mode) == pair[mode]
            assert len(reviewed) == len(pair['predictions'])
            for prediction in pair['predictions']:
                assert abs(scored[prediction['index']]-prediction['adapted']) < 1e-5
    finally:
        capture.release()
    passed = all((p.get('kind') == 'validation' or (p['adapted']['ballRejected'] == 0 and p['adapted']['falseRejected'] > 0))
                 and p['adapted']['ballRejected'] <= p['reference']['ballRejected']
                 and p['adapted']['falseKept'] <= p['reference']['falseKept'] for p in summary['pairs'].values())
    assert summary['eligibleForContinuousReplay'] == passed
    assert summary['productionRelease'] is False
    result = dict(auditPassed=True,selectedEpoch=best['epoch'],stateTensorsChecked=len(initial),changedTensors=len(changed),
                  unchangedBuffers=len(buffers),checkpointSha256=sha(root/'selected.pth'),
                  restoredControlAndValidationScores=True,eligibleForContinuousReplay=passed)
    with (root/'audit.json').open('x') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))
