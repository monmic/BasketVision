"""Visual proposal identities on the preselected, previously unseen second minute."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
path=HERE/'adapted-benchmark/candidate-review/manifest.json'
rows=json.loads(path.read_text())
assert len(rows)==97 and [r['index'] for r in rows]==list(range(97))
balls={14,19,20,32,46,62,69,83,93}
metrics=dict(ballKept=0,ballRejected=0,falseKept=0,falseRejected=0)
for row in rows:
    row['visualObject']='ball' if row['index'] in balls else 'non_ball'
    kept=row['candidate']['semanticKept']
    metrics[('ball' if row['index'] in balls else 'false')+('Kept' if kept else 'Rejected')]+=1
result=dict(manifestSha256=hashlib.sha256(path.read_bytes()).hexdigest(),metrics=metrics,observations=rows,
            uniqueBallFrames=len({r['frame'] for r in rows if r['index'] in balls}),
            policy='All 97 proposals inspected on native-context sheets; ambiguous hand/ball cases checked against pristine full frames. Two proposals at frame 2338 contain the same motion-blurred ball. No exhaustive all-visible-ball annotations, no IoU certification, no global recall.',
            decision='Adapted verifier not promoted: excessive loss of real-ball evidence, despite reducing background and shoe proposals. Text overlay letters also produce false candidates. No threshold changes after observing this block.')
with (HERE/'adapted-review.json').open('x') as stream:json.dump(result,stream,indent=2)
print(json.dumps(metrics))
