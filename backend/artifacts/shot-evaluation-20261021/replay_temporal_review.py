"""Exploratory rim-relative replay of saved ball observations; no new inference."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'vision'))
from shot_detector import Rim, detect_shot_candidates


def evaluate():
    registrations = json.loads((HERE / 'temporal-review/rim-review-v2/rim-proposals.json').read_text())
    registrations += json.loads((HERE / 'original-temporal-review/rim-review-v2/rim-proposals.json').read_text())
    results = []
    for registration in registrations:
        eid = registration['episode']
        if eid == 0:
            original = json.loads((HERE.parents[2] / 'storage/analysis/ce355034-9329-4fff-bfd4-9b9a2c96a033.json').read_text(encoding='utf-8-sig'))
            report = dict(startSeconds=433, endSeconds=436, manualTimestamp=434.68,
                          frames=[dict(frame=round(p['timestamp']*30), candidates=[p]) for p in original['ballTrack']])
        else:
            report = json.loads((HERE / f'episode-{eid:02d}-ball.json').read_text())
        samples = {r['frame']: r for r in registration['samples']}
        observations = [(row, p) for row in report['frames'] for p in row['candidates'] if p.get('accepted')]
        # Exact registration at each accepted frame: no interpolation across gaps.
        if any(row['frame'] not in samples for row, _ in observations):
            raise ValueError('Missing registration at an accepted observation')
        variants = []
        for dx in (-4, 0, 4):
            for dy in (-4, 0, 4):
                for width_factor in (.8, 1., 1.2):
                    points = []
                    for row, point in observations:
                        rim = samples[row['frame']]
                        scale = 24 / (rim['width'] * width_factor)
                        normalized = dict(point)
                        normalized.update(centerX=427+(point['centerX']-rim['x']-dx)*scale,
                                          centerY=240+(point['centerY']-rim['y']-dy)*scale)
                        if not (0 <= normalized['centerX'] < 854 and 0 <= normalized['centerY'] < 480):
                            raise ValueError('Virtual frame clips an observation')
                        points.append(normalized)
                    candidates = detect_shot_candidates(points, Rim(427, 240, 24,
                        report['startSeconds'], report['endSeconds']), 854, 480)
                    variants.append(dict(offsetX=dx, offsetY=dy, widthFactor=width_factor,
                                         candidates=candidates))
        nominal = next(v for v in variants if (v['offsetX'], v['offsetY'], v['widthFactor']) == (0, 0, 1))
        by_track = {}
        for _, point in observations:
            by_track.setdefault(point['trackId'], []).append(point['timestamp'])
        longest = 0
        for times in by_track.values():
            run = 0
            previous = None
            for timestamp in sorted(set(times)):
                run = run+1 if previous is not None and timestamp-previous <= .25 else 1
                longest = max(longest, run)
                previous = timestamp
        results.append(dict(episode=eid, manualTimestamp=report['manualTimestamp'],
            accepted=len(observations), longestContinuousAcceptedRun=longest,
            nominalCandidates=nominal['candidates'], sensitivityCandidateCounts=[len(v['candidates']) for v in variants],
            sensitivityVariants=variants,
            diagnosis='no_accepted_ball_evidence' if not observations else
                      'fewer_than_three_continuous_observations' if longest < 3 else
                      'available_motion_does_not_pass_existing_rules',
            rimXRange=[min(r['x'] for r in samples.values()), max(r['x'] for r in samples.values())],
            rimYRange=[min(r['y'] for r in samples.values()), max(r['y'] for r in samples.values())]))
    return dict(method='Exploratory rim-relative normalization before unchanged fixed-rim detector; not production temporal-rim support.',
        evidenceCoordinates='Virtual 854x480 frame, rim=(427,240), width=24; not original video pixels.',
        review='265 registration overlays visually inspected across six episodes; episode 4 seed corrected in v2. Approximate geometry, not certified pixel annotations.',
        sensitivity='27 variants per episode: offsets +/-4 original pixels per axis, width factors 0.8/1/1.2. A robustness check, not calibration accuracy.',
        episodes=results,
        notice='No database/report changes. These new offline windows are separate from the original analysis. No general precision/recall claim; no made/missed inference.')


if __name__ == '__main__':
    result = evaluate()
    with (HERE / 'temporal-review/replay-six-episodes.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    for row in result['episodes']:
        print(f'E{row["episode"]}: accepted={row["accepted"]}, continuous={row["longestContinuousAcceptedRun"]}, '
              f'candidates={len(row["nominalCandidates"])}, sensitivity={sorted(set(row["sensitivityCandidateCounts"]))}')
