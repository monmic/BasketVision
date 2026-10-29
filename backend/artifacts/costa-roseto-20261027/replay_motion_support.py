"""Causal cached replay: baseline continuity as optional semantic support."""
import copy
import json
import sys
import time
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parents[2] / 'scripts'))
from replay_ball_tracker import load_tracker
from evaluate_preserved_tracking import key

EVIDENCE = set('timestamp confidence source x1 y1 x2 y2 centerX centerY width height aspectRatio softAspectPenalty softSizePenalty qualityScore semanticBall'.split())


def motion_support(candidate, track, settings):
    return (candidate.get('accepted', False)
            and track is not None
            and track['hits'] >= settings['BALL_STATIC_MIN_HITS']
            and track['consecutiveHits'] >= settings['BALL_STATIC_MIN_HITS']
            and candidate['trackAverageSpeedPxPerSecond'] > settings['BALL_STATIC_MAX_SPEED_PX_PER_SECOND'])


def replay(report):
    settings = report['settings']
    baseline_module = load_tracker(settings)
    gated_module = load_tracker(settings, worker=BASE / 'worker-semantic-prototype.py')
    shadow = baseline_module['BallTracker']()
    gated = gated_module['BallTracker']()
    rows = []
    supported = 0
    started = time.perf_counter()
    for row in report['frames']:
        candidates = [{k: v for k, v in c.items() if k in EVIDENCE} for c in row['candidates']]
        original = copy.deepcopy(candidates)
        for values in (original, candidates):
            for c in values:
                c['accepted'] = False
                if c['qualityScore'] < settings['BALL_TRACK_UPDATE_MIN_SCORE']:
                    c['rejectionReason'] = 'score_below_track_update_threshold'
        shadow.update([c for c in original if c['qualityScore'] >= settings['BALL_TRACK_UPDATE_MIN_SCORE']], row['timestamp'])
        for cached, source, target in zip(row['candidates'], original, candidates):
            assert source['accepted'] == cached['accepted']
            if target.get('semanticBall') is False and motion_support(source, shadow.tracks.get(source.get('trackId')), settings):
                target['semanticBall'] = True
                target['motionSupported'] = True
                supported += 1
        gated.update([c for c in candidates if c['qualityScore'] >= settings['BALL_TRACK_UPDATE_MIN_SCORE']], row['timestamp'])
        rows.append(dict(frame=row['frame'], timestamp=row['timestamp'], candidates=candidates))
    return dict(frames=rows, supported=supported, elapsedSeconds=time.perf_counter()-started)


def compare(result, reviewed):
    accepted = {key(r['frame'], c) for r in result['frames'] for c in r['candidates'] if c['accepted']}
    kept = Counter()
    lost = []
    known = {key(r['frame'], r['candidate']) for r in reviewed}
    selected = {r['frame'] for r in reviewed if r['selectedReference']}
    for r in reviewed:
        identity = key(r['frame'], r['candidate'])
        if r['baseline'] and identity in accepted:
            kept[r['label']] += 1
        elif r['baseline'] and r['label'] == 'ball':
            lost.append(r['index'])
    unknown = sorted(k for k in accepted if k[0] in selected and k not in known)
    passed = not lost and kept['non_ball'] <= 8 and not unknown
    return dict(accepted=len(accepted), knownKept=dict(kept), lostBallIndices=lost,
                unreviewedFixed=unknown, eligibleForFurtherReview=passed, productionRelease=False)


if __name__ == '__main__':
    root = BASE / 'detector-preserved/motion-support'
    root.mkdir(exist_ok=False)
    report = json.loads((BASE / 'detector-preserved/continuous/baseline.json').read_text())
    result = replay(report)
    reviewed = json.loads((BASE / 'continuous-review/review.json').read_text())['observations']
    summary = compare(result, reviewed)
    summary.update(supported=result['supported'], elapsedReplaySeconds=result['elapsedSeconds'],
                   notice='Known development identities; not exhaustive recall. Cached replay excludes CNN/decode cost.')
    (root / 'replay.json').write_text(json.dumps(result))
    (root / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
