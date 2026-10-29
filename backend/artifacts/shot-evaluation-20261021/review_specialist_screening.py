"""Persist explicit visual candidate correspondence; do not invent full-frame ground truth."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUTPUT=HERE/'specialist-screening'
BASE={0:[0,0,None,None,None,0],1:[None,None,None,None,0,0],
      2:[0,0,0,0,None,0],3:[None,None,0,None,None,0],
      4:[None,None,None,None,0,0],5:[None,None,None,None,None,None]}
SPECIALIST={0:[None,None,None,None,None,0],1:[None,None,0,None,1,1],
            2:[None,0,0,None,None,1],3:[0,None,0,None,None,0],
            4:[None,None,None,None,None,0],5:[None,0,None,None,None,None]}


def review():
    read=lambda name:json.loads((OUTPUT/name).read_text())
    baseline=read('baseline-near-rim.json')
    specialist=read('specialist-near-rim.json')
    assert [(r['episode'],r['frame']) for r in baseline['frames']]==[(r['episode'],r['frame']) for r in specialist['frames']]
    rows=[]
    for eid in range(6):
        a=[r for r in baseline['frames'] if r['episode']==eid]
        b=[r for r in specialist['frames'] if r['episode']==eid]
        for index,(ar,br) in enumerate(zip(a,b)):
            ai,bi=BASE[eid][index],SPECIALIST[eid][index]
            if ai is not None:
                assert ai<len(ar['candidates'])
            if bi is not None:
                assert bi<len(br['candidates'])
            rows.append(dict(episode=eid,frame=ar['frame'],timestamp=ar['timestamp'],
                             baselineCandidateIndex=ai,specialistCandidateIndex=bi,
                             status='both_match' if ai is not None and bi is not None else
                                    'specialist_gain' if bi is not None else
                                    'specialist_loss' if ai is not None else 'both_miss'))
    counts={k:sum(r['status']==k for r in rows) for k in ('both_match','specialist_gain','specialist_loss','both_miss')}
    return dict(policy='Visual correspondence to the visible active ball in 36 selected frames. Not IoU-scored annotations or exhaustive all-ball ground truth. The specialist box at frame 17824 is coarse.',
                frames=rows,counts=counts,
                decision='Do not promote specialist or start trajectory replay: fewer active-ball matches, worse separate-video metrics, much higher CPU inference cost.')


if __name__=='__main__':
    result=review()
    with (OUTPUT/'visual-review.json').open('x') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps(result['counts'],indent=2))
