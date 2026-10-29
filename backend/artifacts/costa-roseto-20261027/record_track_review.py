"""Persist visual review of all accepted semantic observations and fixed controls.

Labels concern proposal identity, not exhaustive ball ground truth or shot events.
Boards are produced by review_track_gate.py; uncertainty remains explicit.
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = json.loads((HERE / 'continuous-review/manifest.json').read_text())
assert len(rows) == 133 and [r['index'] for r in rows] == list(range(133))
balls = set(range(18)) | set(range(19, 35)) | {43, 71, 74}
balls |= set(range(79, 86)) | set(range(104, 116)) | set(range(121, 133))
uncertain = {86}
for row in rows:
    row['label'] = ('ball' if row['index'] in balls else
                    'uncertain' if row['index'] in uncertain else 'non_ball')

def counts(policy, selected=False):
    return dict(Counter(r['label'] for r in rows
                        if r[policy] and (not selected or r['selectedReference'])))

report = dict(
    method='Visual identity review of context crops; frame 2338 motion blur '
           'also checked in the full-frame adapted detector review.',
    limitations=['No exhaustive ball annotations; no recall or IoU accuracy.',
                 'Baseline outside the 30 fixed reference frames is not fully reviewed.',
                 'Same-source holdout; edited montage may repeat actions.'],
    semanticAll=counts('semantic'),
    fixedReferenceBaseline=counts('baseline', True),
    fixedReferenceSemantic=counts('semantic', True),
    fixedReferenceLost=dict(Counter(r['label'] for r in rows
        if r['selectedReference'] and r['baseline'] and not r['semantic'])),
    observations=rows,
    decision='Rejected: text false positives and lost ball observations; offline only.')
(HERE / 'continuous-review/review.json').write_text(json.dumps(report, indent=2))
print(json.dumps({k:v for k,v in report.items() if k != 'observations'}, indent=2))
