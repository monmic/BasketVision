"""Independent arithmetic, split and provenance audit; no ML dependencies."""
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent


def counts(rows, predictions, field):
    result = Counter(dict(ballKept=0, ballRejected=0, falseKept=0, falseRejected=0))
    for row, prediction in zip(rows, predictions):
        assert row['index'] == prediction['index']
        label = row.get('label', row.get('visualObject'))
        if label == 'uncertain':
            continue
        assert label in ('ball', 'non_ball')
        result[('ball' if label == 'ball' else 'false') + ('Kept' if prediction[field] >= .5 else 'Rejected')] += 1
    return dict(result)


if __name__ == '__main__':
    read = lambda path: json.loads(path.read_text())
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    root = BASE / 'spatial-verifier'
    summary = read(root / 'summary.json')
    classifier = read(root / 'classifier.json')
    manifest = BASE / 'adapted-examples/manifest.json'
    assert sha(manifest) == classifier['trainingManifestSha256']
    assert sha(root / 'classifier.json') == summary['classifierSha256']
    assert len(classifier['weight']) == summary['features'] == 1024
    training = read(manifest)['examples']
    assert len(training) == summary['trainingExamples'] == 409
    source = 'ad0b3783-9ef0-49b9-8645-a8fac9540389-020ad1c9868d47e48fe7193d831fc33f.mp4'
    for r in training:
        assert sha(manifest.parent / r['file']) == r['sha256']
        if r['sourceVideo'] == source:
            assert r['timestamp'] < 60
    paths = dict(proposals=BASE / 'adapted-review.json', trackIdentities=BASE / 'continuous-review/review.json')
    audit = {}
    for name, path in paths.items():
        rows = read(path)['observations']
        data = summary['controls'][name]
        assert len(rows) == len(data['scores']) == len(data['nativeCropSizes'])
        assert min(r['frame'] for r in rows) >= 1798
        assert max(r['frame'] for r in rows) < 3596
        for field, target in [('score', 'spatial'), ('oldScore', 'original')]:
            assert counts(rows, data['scores'], field) == data[target]
        sizes = [min(shape) for row, shape in zip(rows, data['nativeCropSizes']) if row.get('label', row.get('visualObject')) == 'ball']
        audit[name] = dict(labelSha256=sha(path), nativeBallShortSideRange=[min(sizes), max(sizes)],
                           nativeBallShortSideMedian=statistics.median(sizes), nativeBallBelow16px=sum(s < 16 for s in sizes))
        if name == 'proposals':
            # Same decoder/crop/preprocessing/backbone as the historical control.
            max_error = max(abs(r['candidate']['semanticScore'] - p['oldScore']) for r,p in zip(rows, data['scores']))
            # CPU convolution batch shapes can change float32 rounding slightly.
            assert max_error < 1e-5, max_error
            assert all((p['oldScore'] >= .5) == r['candidate']['semanticKept'] for r,p in zip(rows, data['scores']))
            audit[name]['historicalScoreMaxError'] = max_error
    passed = all(d['spatial']['ballRejected'] == 0 and d['spatial']['falseRejected'] > 0 for d in summary['controls'].values())
    assert passed == summary['eligibleForContinuousReplay']
    assert summary['productionRelease'] is False
    result = dict(trainingManifestSha256=sha(manifest), classifierSha256=sha(root / 'classifier.json'), controls=audit,
                  eligibleForContinuousReplay=passed, auditPassed=True)
    with (root / 'audit.json').open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))
