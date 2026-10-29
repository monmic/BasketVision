"""Compare paired trackers against previously reviewed observation identities."""
import json
from collections import Counter
from pathlib import Path

BASE=Path(__file__).resolve().parent


def key(frame,c):return (frame,*(round(c[k],1) for k in ['x1','y1','x2','y2']))


if __name__=='__main__':
    root=BASE/'detector-preserved/continuous'
    read=lambda path:json.loads(Path(path).read_text())
    baseline=read(root/'baseline.json');gated=read(root/'gated.json')
    previous=read(BASE/'continuous/baseline.json')
    reviewed=read(BASE/'continuous-review/review.json')['observations']
    signature=lambda r:sorted((*(round(c[k],4) for k in ['x1','y1','x2','y2','confidence','qualityScore']),c['source']) for c in r['candidates'])
    assert len(baseline['frames'])==len(gated['frames'])==len(previous['frames'])==1798
    for a,b,old in zip(baseline['frames'],gated['frames'],previous['frames']):
        assert a['frame']==b['frame']==old['frame']
        assert signature(a)==signature(b)==signature(old)
    accepted={name:{key(r['frame'],c) for r in report['frames'] for c in r['candidates'] if c.get('accepted')}
              for name,report in [('baseline',baseline),('gated',gated)]}
    lost=[];known=Counter();kept=Counter();fixed_before=Counter();fixed_after=Counter()
    for row in reviewed:
        identity=key(row['frame'],row['candidate'])
        assert (identity in accepted['baseline'])==row['baseline']
        if row['baseline']:
            known[row['label']]+=1
            if identity in accepted['gated']:kept[row['label']]+=1
            elif row['label']=='ball':lost.append(dict(index=row['index'],frame=row['frame'],timestamp=row['timestamp'],box=identity[1:]))
        if row['selectedReference']:
            if identity in accepted['baseline']:fixed_before[row['label']]+=1
            if identity in accepted['gated']:fixed_after[row['label']]+=1
    selected={r['frame'] for r in reviewed if r['selectedReference']}
    known_keys={key(r['frame'],r['candidate']) for r in reviewed}
    unknown_fixed=sorted(k for k in accepted['gated'] if k[0] in selected and k not in known_keys)
    new_only=sorted(accepted['gated']-accepted['baseline'])
    result=dict(unchangedRawFrames=1798,baselineAccepted=len(accepted['baseline']),gatedAccepted=len(accepted['gated']),
        knownBaselineIdentities=dict(known),knownIdentitiesKept=dict(kept),knownBallObservationsLost=lost,
        fixedReferenceBaseline=dict(fixed_before),fixedReferenceGated=dict(fixed_after),
        unreviewedFixedObservations=unknown_fixed,newOnlyAcceptedObservations=len(new_only),
        productionRelease=False,
        decision='Rejected: previously verified ball observations lost.' if lost else 'Partial control passed; review new-only observations and further independent sequences before promotion.',
        notice='Identity labels on a known development subset, not exhaustive ball ground truth or recall. Counts alone are not accuracy.')
    with (root/'review-comparison.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))
