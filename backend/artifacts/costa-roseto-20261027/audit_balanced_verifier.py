"""Independent audit of selection, holdouts, weight mass and recorded decisions."""
import json
import math
from collections import Counter
from pathlib import Path
from audit_spatial_verifier import counts
from audit_context_verifier import sha, read

BASE = Path(__file__).resolve().parent


def role(row):
    if row['sourceVideo'].startswith('ad0b3783'):
        assert 0 <= row['timestamp'] < 60
        return 'validation' if row['timestamp'] >= 44 else ('guard' if row['timestamp'] >= 42 else 'train')
    return 'validation' if 500 <= row['timestamp'] < 560 else 'train'


if __name__ == '__main__':
    root = BASE/'balanced-verifier'
    dataset = read(root/'dataset.json')
    summary = read(root/'summary.json')
    old = BASE/'context-verifier'
    assert dataset['previousManifestSha256'] == sha(old/'manifest.json')
    assert dataset['annotationSha256'] == sha(root/'reviewed.json')
    annotations = read(root/'reviewed.json')
    assert len(annotations['frames']) == 12
    assert Counter(r['status'] for r in annotations['frames']) == dict(visible=8,uncertain=3,absent=1)
    rows = dataset['examples']
    assert len(rows) == summary['poolExamples'] == 465
    prior = read(old/'manifest.json')['examples']
    for i,row in enumerate(rows):
        assert row['index'] == i
        assert row['partition'] == role(row)
        if i < len(prior):
            previous = prior[i]
            assert all(row[k] == previous[k] for k in ['sourceVideo','frame','bounds','label','provenance'])
            path = old/row['detailFile']
            assert sha(path) == previous['detailSha256'] == row['pixelSha256']
        else:
            source = next(r for r in annotations['frames'] if r['frame'] == row['frame'])
            assert source['status'] == 'visible' and row['bounds'] in source['pixelBoxes']
            assert row['label'] == 1
            assert sha(root/row['newFile']) == row['pixelSha256']
    priority = {'new-ground-truth':0,'train-ground-truth':1,'verified-proposal':2}
    chosen = {}
    for row in sorted(rows,key=lambda r:(priority[r['provenance']],r['index'])):
        a,b,c,d = row['bounds']
        identity = (row['sourceVideo'],row['label'],math.floor(row['timestamp']),math.floor((a+c)/128),math.floor((b+d)/128))
        chosen.setdefault(identity,row['index'])
    selected = set(chosen.values())
    assert selected == {r['index'] for r in rows if r['retained']}
    train = [r for r in rows if r['retained'] and role(r) == 'train']
    validation = [r for r in rows if r['retained'] and role(r) == 'validation']
    assert len(train) == summary['train'] == 104
    assert len(validation) == summary['validation'] == 72
    assert len(selected) == summary['retained'] == 180
    mass = Counter()
    for name in ['reference','balanced']:
        path = root/(name+'-classifier.json')
        model = read(path)
        assert sha(path) == summary['classifierSha256'][name]
        assert model['manifestSha256'] == sha(root/'dataset.json')
        assert model['trainingIndices'] == [r['index'] for r in train]
        assert not set(model['trainingIndices']) & {r['index'] for r in validation}
        assert model['threshold'] == .5 and model['l2'] == .01
        if name == 'balanced':
            assert len(model['weights']) == len(train)
            for row,weight in zip(train,model['weights']):
                assert math.isfinite(weight) and weight > 0
                mass[(row['sourceVideo'],row['label'])] += weight
    assert len(mass) == 4 and all(abs(total-.25) < 1e-12 for total in mass.values())
    for key,pair in summary['pairs'].items():
        if key.startswith('validation-'):
            source = key[len('validation-'):]
            observed = [dict(index=r['index'],label='ball' if r['label'] else 'non_ball') for r in validation if r['sourceVideo'] == source]
        else:
            path = BASE/('adapted-review.json' if key == 'proposals' else 'continuous-review/review.json')
            assert sha(path) == pair['labelSha256']
            observed = read(path)['observations']
        for name in ['reference','balanced']:
            assert len(observed) == len(pair['predictions'][name])
            assert counts(observed,pair['predictions'][name],'score') == pair[name]
    passed = all((p.get('kind') == 'validation' or (p['balanced']['ballRejected'] == 0 and p['balanced']['falseRejected'] > 0))
                 and p['balanced']['ballRejected'] <= p['reference']['ballRejected']
                 and p['balanced']['falseKept'] <= p['reference']['falseKept'] for p in summary['pairs'].values())
    assert passed == summary['eligibleForContinuousReplay']
    assert summary['productionRelease'] is False
    result = dict(auditPassed=True,pool=len(rows),repetitionsRemoved=len(rows)-len(selected),train=len(train),validation=len(validation),
                  retainedGuard=len(selected)-len(train)-len(validation),newVisibleBoxes=8,eligibleForContinuousReplay=passed,
                  annotationSha256=sha(root/'reviewed.json'),datasetSha256=sha(root/'dataset.json'))
    with (root/'audit.json').open('x') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))
