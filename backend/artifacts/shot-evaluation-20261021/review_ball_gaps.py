"""Explicit visual audit of 36 selected visible active-ball observations."""
import json
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
SELECTED={0:[13053,13056,13065,13068,13071,13077],
          1:[17818,17822,17824,17828,17837,17842],
          2:[35259,35262,35265,35268,35271,35286],
          3:[35732,35735,35738,35744,35750,35756],
          4:[35971,35974,35977,35980,35989,35992],
          5:[36213,36216,36219,36225,36228,36240]}
# None = no saved candidate corresponds to the visible active ball, even when
# unrelated raw boxes are present elsewhere. Indices refer to samples.json.
MATCHES={0:[0,0,None,None,None,0],1:[None,None,None,None,0,0],
         2:[0,0,0,0,None,0],3:[None,None,0,None,None,0],
         4:[None,None,None,None,0,0],5:[None,None,None,None,None,None]}


def review():
    samples=json.loads((HERE/'ball-gap-audit/samples.json').read_text())
    rows=[]
    for episode in samples:
        eid=episode['episode']
        by_frame={r['frame']:r for r in episode['samples']}
        for frame,index in zip(SELECTED[eid],MATCHES[eid]):
            source=by_frame[frame]
            candidate=source['candidates'][index] if index is not None else None
            status=('no_corresponding_raw_candidate' if candidate is None else
                    'accepted' if candidate['accepted'] else 'rejected_by_tracker')
            rows.append(dict(episode=eid,frame=frame,timestamp=source['timestamp'],
                activeBallVisible=True,matchedRawCandidateIndex=index,status=status,
                reason=candidate.get('rejectionReason',candidate.get('acceptanceReason')) if candidate else None,
                source=candidate['source'] if candidate else None))
    return dict(policy='Visual active-ball audit, six selected frames per episode. Not exhaustive all-ball annotations; no FP/precision estimate. Uncertain/cropped observations omitted.',
        selectionBias='Targeted near-rim windows; 0.1s sampling can alias tiled-inference cadence. Counts describe only the selected observations.',
        frames=rows,counts=dict(Counter(r['status'] for r in rows)),
        rejectedReasons=dict(Counter(r['reason'] for r in rows if r['status']=='rejected_by_tracker')))


if __name__=='__main__':
    result=review()
    with (HERE/'ball-gap-audit/reviewed-gaps.json').open('x') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('frames','policy','selectionBias')},indent=2))
