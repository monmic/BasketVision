"""Read-only comparison of a saved worker report and reviewed DB snapshot."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'vision'))
from shot_detector import Rim, detect_shot_candidates
ANALYSIS_ID = 'ce355034-9329-4fff-bfd4-9b9a2c96a033'


def evaluate():
    source = ROOT / 'storage' / 'analysis' / f'{ANALYSIS_ID}.json'
    report = json.loads(source.read_text(encoding='utf-8-sig'))
    events = json.loads((HERE / 'reviewed-shots.json').read_text(encoding='utf-8-sig'))
    video = report['video']
    start = video['analysisStartSeconds']
    end = video.get('analysisEndSeconds') or video['durationSeconds']
    calibration = report.get('shotCandidateCalibration')
    candidates = report.get('shotCandidates', [])
    tolerance = 1.0
    rows = []
    used = set()
    for event in sorted(events, key=lambda e: e['VideoTimestamp']):
        if event['AnalysisJobId'] != ANALYSIS_ID or event['Status'] not in (1, 2) or event['Type'] not in (0, 1):
            continue
        timestamp = event['VideoTimestamp']
        status = 'outside_analysis'
        match = None
        if start <= timestamp < end:
            if calibration and calibration['startSeconds'] <= timestamp <= calibration['endSeconds']:
                eligible = [(abs(c['timestamp']-timestamp), i) for i, c in enumerate(candidates)
                            if i not in used and abs(c['timestamp']-timestamp) <= tolerance]
                if eligible:
                    _, match = min(eligible)
                    used.add(match)
                status = 'matched' if match is not None else 'missed'
            else:
                status = 'outside_calibration'
        rows.append({'timestamp': timestamp, 'status': status, 'candidateIndex': match})
    replay = []
    if calibration:
        c = calibration
        replay = detect_shot_candidates(report['ballTrack'],
            Rim(c['x'], c['y'], c['width'], c['startSeconds'], c['endSeconds']),
            video['width'], video['height'])
    eligible_rows = [r for r in rows if not r['status'].startswith('outside_')]
    replay_used = set()
    replay_matches = []
    for row in eligible_rows:
        eligible = [(abs(c['timestamp']-row['timestamp']), i) for i, c in enumerate(replay)
                    if i not in replay_used and abs(c['timestamp']-row['timestamp']) <= tolerance]
        if eligible:
            delta, index = min(eligible)
            replay_used.add(index)
            replay_matches.append({'manualTimestamp': row['timestamp'], 'candidateTimestamp': replay[index]['timestamp'],
                                   'absoluteDeltaSeconds': round(delta, 3)})
    return {'analysisId': ANALYSIS_ID, 'toleranceSeconds': tolerance,
            'analysisInterval': [start, end], 'calibration': calibration,
            'manualShots': rows, 'storedCandidates': len(candidates),
            'matched': sum(r['status']=='matched' for r in rows),
            'missed': sum(r['status']=='missed' for r in rows),
            'excluded': sum(r['status'].startswith('outside_') for r in rows),
            'unmatchedCandidates': len(candidates)-len(used),
            'currentDetectorReplay': {'candidates': replay, 'matches': replay_matches,
                                      'missed': len(eligible_rows)-len(replay_matches),
                                      'unmatchedCandidates': len(replay)-len(replay_used)},
            'notice': 'Exploratory reviewed sample, not exhaustive ground truth. Unmatched candidates are not certified false positives. No production data modified.'}


if __name__ == '__main__':
    print(json.dumps(evaluate(), indent=2))
