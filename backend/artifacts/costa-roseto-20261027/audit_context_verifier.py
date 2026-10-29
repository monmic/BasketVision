"""Independent dataset/decision audit with only the Python standard library."""
import hashlib
import json
import math
import struct
from collections import Counter
from pathlib import Path
from audit_spatial_verifier import counts

BASE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def no_regression(pair):
    return (pair['context']['ballRejected'] <= pair['detail']['ballRejected']
            and pair['context']['falseKept'] <= pair['detail']['falseKept'])


if __name__ == '__main__':
    root = BASE/'context-verifier'
    dataset = read(root/'manifest.json')
    summary = read(root/'summary.json')
    original_path = BASE/'adapted-examples/manifest.json'
    expanded_path = BASE/'detector-expanded/dataset/manifest.json'
    assert sha(original_path) == dataset['originalManifestSha256']
    assert sha(expanded_path) == dataset['expandedManifestSha256']
    rows = dataset['examples']
    assert len(rows) == summary['trainingExamples']
    identities = set()
    proposal_count = gt_count = 0
    for row in rows:
        identity = (row['sourceVideo'], row['frame'], *row['bounds'])
        assert identity not in identities
        identities.add(identity)
        assert row['label'] in (0, 1)
        a,b,c,d = row['bounds']
        x,y,z,w = row['contextBounds']
        assert x <= a < c <= z and y <= b < d <= w
        for mode in ('detail', 'context'):
            assert sha(root/row[mode+'File']) == row[mode+'Sha256']
        if row['sourceVideo'].startswith('ad0b3783'):
            assert row['frame'] < 1798
        if row['provenance'] == 'verified-proposal':
            proposal_count += 1
        elif row['provenance'] == 'train-ground-truth':
            assert row['label'] == 1
            gt_count += 1
        else:
            raise AssertionError('Unknown training provenance')
    assert proposal_count == 409
    original = read(original_path)['examples']
    by_identity = {(r['sourceVideo'], r['frame'], *r['bounds']): r for r in rows}
    for row in original:
        found = by_identity[(row['sourceVideo'], row['frame'], *row['cropBounds'])]
        assert found['label'] == int(row['label'] == 'active_ball')
        assert found['detailSha256'] == row['sha256']
    gt_identities = set()
    reviewed_boxes = 0
    for row in read(expanded_path)['frames']:
        if row['kind'] != 'full-frame' or row['split'] != 'train':
            continue
        image = expanded_path.parent/row['image']
        assert sha(image) == row['sha256']
        # PNG IHDR gives native dimensions without an image/ML dependency.
        header = image.read_bytes()[:24]
        assert header[:8] == b'\x89PNG\r\n\x1a\n'
        width,height = struct.unpack('>II', header[16:24])
        source = next(s for s in {r['sourceVideo'] for r in rows}
                      if s.startswith('ad0b3783') == (row['source'] == 'costa'))
        for a,b,c,d in row['boxes']:
            bounds = (max(0, math.floor(a*width)), max(0, math.floor(b*height)),
                      min(width, math.ceil(c*width)), min(height, math.ceil(d*height)))
            identity = (source, row['frame'], *bounds)
            gt_identities.add(identity)
            assert by_identity[identity]['label'] == 1
            reviewed_boxes += 1
    original_identities = {(r['sourceVideo'],r['frame'],*r['cropBounds']) for r in original}
    assert identities == original_identities | gt_identities
    assert gt_count == len(gt_identities-original_identities)
    assert reviewed_boxes == dataset['extraPositiveBoxes'] == 49
    for mode, dimensions in [('detail', 1024), ('context', 2048)]:
        path = root/(mode+'-classifier.json')
        model = read(path)
        assert sha(path) == summary['classifierSha256'][mode]
        assert model['manifestSha256'] == sha(root/'manifest.json')
        assert len(model['weight']) == model['featureDimensions'] == dimensions
        assert model['threshold'] == .5 and model['l2'] == .01
    sources = Counter(r['sourceVideo'] for r in rows)
    assert {f['heldOutVideo'] for f in summary['folds']} == set(sources)
    for fold in summary['folds']:
        assert fold['testExamples'] == sources[fold['heldOutVideo']]
        assert fold['trainExamples'] == len(rows)-fold['testExamples']
        labels = Counter(r['label'] for r in rows if r['sourceVideo'] == fold['heldOutVideo'])
        for mode in ('detail', 'context'):
            m = fold[mode]
            assert m['ballKept']+m['ballRejected'] == labels[1]
            assert m['falseKept']+m['falseRejected'] == labels[0]
    for name,path in [('proposals', BASE/'adapted-review.json'), ('trackIdentities', BASE/'continuous-review/review.json')]:
        control = summary['controls'][name]
        assert sha(path) == control['labelSha256']
        reviewed = read(path)['observations']
        assert len(reviewed) == control['observations']
        for mode in ('detail', 'context'):
            assert counts(reviewed, control['predictions'][mode], 'score') == control[mode]
    passed = (all(c['context']['ballRejected'] == 0 and c['context']['falseRejected'] > 0 and no_regression(c)
                  for c in summary['controls'].values()) and all(no_regression(f) for f in summary['folds']))
    assert summary['eligibleForContinuousReplay'] == passed
    assert summary['productionRelease'] is False
    result = dict(auditPassed=True, examples=len(rows), proposalCrops=proposal_count, addedGroundTruth=gt_count,
                  reviewedGroundTruthBoxes=reviewed_boxes, deduplicatedGroundTruth=reviewed_boxes-gt_count,
                  verifiedCropFiles=2*len(rows), bySource=dict(sources), manifestSha256=sha(root/'manifest.json'),
                  eligibleForContinuousReplay=passed)
    with (root/'audit.json').open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))
