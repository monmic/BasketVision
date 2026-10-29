"""Explicit reviewed identities; not exhaustive frame labels or an event benchmark."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def review(folder,ball_indices,expected):
    path=HERE/folder/'candidate-review/manifest.json'
    rows=json.loads(path.read_text())
    assert len(rows)==expected and [r['index'] for r in rows]==list(range(expected))
    metrics=dict(ballKept=0,ballRejected=0,falseKept=0,falseRejected=0)
    for r in rows:
        r['visualObject']='ball' if r['index'] in ball_indices else 'non_ball'
        kept=r['candidate'].get('semanticKept',True)
        metrics[('ball' if r['index'] in ball_indices else 'false')+('Kept' if kept else 'Rejected')]+=1
    return dict(manifestSha256=hashlib.sha256(path.read_bytes()).hexdigest(),metrics=metrics,observations=rows)


if __name__=='__main__':
    result=dict(baseline=review('benchmark',{21,34,50},64),context=review('context',{2,9},16),
        hoopReview=dict(gameFrames=23,correctTopHoopAboveThreshold=23,introFrames=7,
            falseTopHoopAboveThresholdInIntro=0,
            notice='Reviewed all 30 full-frame overlays. Two low-score studio proposals are below 0.25 and produce no ROI. Boxes locate hoop/net objects, not exact rim lines.'),
        policy='All raw proposals reviewed against pristine references and native-context sheets. Ball means visible ball in the box, not certified box IoU. No full-frame all-visible-ball ground truth; no detector recall or whole-video precision inferred.',
        decision='Do not promote semantic filter: one of three real-ball proposals is removed. Automatic ROI finds the hoop but adds no ball frame beyond baseline and misses its third ball proposal. No dense tracker/event trial justified by these gates.')
    with (HERE/'review.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({k:result[k]['metrics'] for k in ('baseline','context')}))
