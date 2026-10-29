"""Trace original lost identities and their causal neighbourhood, from cache."""
import json
from collections import Counter
from replay_motion_support import BASE, key


if __name__ == '__main__':
    root = BASE / 'detector-preserved'
    read = lambda path: json.loads(path.read_text())
    baseline = read(root / 'continuous/baseline.json')
    gated = read(root / 'continuous/gated.json')
    motion = read(root / 'motion-support/replay.json')
    losses = read(root / 'continuous/review-comparison.json')['knownBallObservationsLost']
    indexed = {name: {key(r['frame'], c): c for r in report['frames'] for c in r['candidates']}
               for name, report in [('baseline', baseline), ('gated', gated), ('motion', motion)]}
    details = []
    for loss in losses:
        identity = (loss['frame'], *loss['box'])
        original = indexed['baseline'][identity]
        trace = []
        for row in baseline['frames']:
            if abs(row['timestamp'] - loss['timestamp']) > .5:
                continue
            for c in row['candidates']:
                if c.get('trackId') != original['trackId']:
                    continue
                k = key(row['frame'], c)
                trace.append(dict(frame=row['frame'], semanticBall=c['semanticBall'],
                                  baselineAccepted=c['accepted'],
                                  gatedAccepted=indexed['gated'][k]['accepted'],
                                  gatedReason=indexed['gated'][k].get('rejectionReason'),
                                  motionAccepted=indexed['motion'][k]['accepted'],
                                  hits=c['trackHits'], speed=c['trackAverageSpeedPxPerSecond']))
        details.append(dict(**loss, neighbourhood=trace))
    reasons = Counter(indexed['gated'][(r['frame'], *r['box'])].get('rejectionReason') for r in losses)
    result = dict(lostObservations=len(losses), rejectionReasons=dict(reasons), details=details,
                  notice='Same baseline track in a +/-0.5s diagnostic window; future rows are diagnostic only and never used by replay.')
    with (root / 'motion-support/loss-diagnosis.json').open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(dict(lostObservations=len(losses), rejectionReasons=dict(reasons)), indent=2))
