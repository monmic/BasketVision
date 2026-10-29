"""Ablate distance ranking on frozen candidates, with reviewed regression cohorts."""
import argparse
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parents[2]/'scripts'),str(HERE.parent/'ball-tracking-audit-20261026')]
from replay_ball_tracker import replay,WORKER
from evaluate_cohort import evaluate

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--worker',type=Path,default=HERE/'worker-distance-prototype.py')
p.add_argument('--temporal',action='store_true',help='Compare existing temporal policy with unchanged original worker')
args=p.parse_args()
out=HERE/('temporal-replay' if args.temporal else 'distance-replay');out.mkdir(exist_ok=False)
worker=WORKER if args.temporal else args.worker
overrides={'BALL_TRACK_TEMPORAL_WINDOW':True} if args.temporal else None
read=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
reviewed=read(HERE/'visual-review.json')
labels={(r['episode'],r['frame'],*(round(r[k],1) for k in ('x1','y1','x2','y2'))):r['visualObject'] for r in reviewed['accepted']}
summary=[]
for eid in range(6):
    raw=read(HERE/f'continuous/raw-{eid:02d}.json')
    variant=replay(raw,worker=worker,overrides=overrides)
    labeled={};unreviewed=[]
    for row in variant['frames']:
        for c in row['candidates']:
            if not c['accepted']:continue
            key=(eid,row['frame'],*(round(c[k],1) for k in ('x1','y1','x2','y2')))
            label=labels.get(key)
            if label:labeled[label]=labeled.get(label,0)+1
            else:unreviewed.append(dict(frame=row['frame'],candidate=c))
    with (out/f'replay-{eid:02d}.json').open('x') as stream:json.dump(variant,stream)
    item=dict(episode=eid,reviewedAccepted=labeled,newUnreviewed=unreviewed)
    summary.append(item);print(json.dumps(dict(episode=eid,reviewedAccepted=labeled,newUnreviewed=len(unreviewed))),flush=True)
minute=HERE.parent/'ball-tracking-audit-20261026'
raw=read(minute/'raw.json');variant=replay(raw,worker=worker,overrides=overrides)
cohort=evaluate(variant,read(minute/'combined-reviewed.json'))
with (out/'minute-replay.json').open('x') as stream:json.dump(variant,stream)
with (out/'comparison.json').open('x') as stream:json.dump(dict(episodes=summary,minute=cohort),stream,indent=2)
print('minute',json.dumps(dict(reviewedCounts=cohort['reviewedCounts'],newUnreviewed=len(cohort['newlyAcceptedUnreviewed']))))
