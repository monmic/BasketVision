"""Explicit visual correspondence for this frozen experiment, not model labels.

Reviewed all 191 accepted boxes on five sheets plus native frame 36217.
Object identity is not an IoU ground truth or exhaustive video annotation.
"""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AUDIT=HERE.parent/'shot-evaluation-20261021'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))

def review():
    manifest_path=HERE/'continuous-review/accepted-manifest.json'
    accepted=read(manifest_path)
    assert len(accepted)==191 and [r['index'] for r in accepted]==list(range(191))
    assert [sum(r['episode']==e for r in accepted) for e in range(6)]==[63,30,42,13,27,16]
    background=set(range(7,33))|set(range(68,74))|set(range(108,113))|set(range(115,123))|{124,126,129}|set(range(148,153))|set(range(157,164))|set(range(172,175))
    heads=set(range(168,172))
    for c in accepted:
        c['visualObject']='background' if c['index'] in background else 'player_head' if c['index'] in heads else 'active_ball'
    ROI={0:[0,0,0,0,0,0],1:[0,None,0,0,0,0],2:[0,0,0,0,0,None],
         3:[None,None,0,0,None,0],4:[None,None,0,0,0,0],5:[None,0,0,None,0,0]}
    FULL={0:[None,None,None,2,2,None],1:[None,None,None,None,None,5],
          2:[0,None,None,1,None,1],3:[None,None,0,0,None,0],4:[None,None,None,1,1,1],5:[None,0,0,None,None,None]}
    base=read(AUDIT/'specialist-screening/visual-review.json')['frames']
    rows=[]
    for name,folder,prefix,mapping in [('attallaFull','attalla-screening','attalla',FULL),('automaticRoi','automatic-roi','attalla',ROI),('ebard','screening','ebard',{e:[None]*6 for e in range(6)})]:
        frames=read(HERE/f'{folder}/{prefix}-near-rim.json')['frames']
        assert [(r['episode'],r['frame']) for r in frames]==[(r['episode'],r['frame']) for r in base]
        model_rows=[]
        for e in range(6):
            for r,index in zip([r for r in frames if r['episode']==e],mapping[e]):
                if index is not None:assert index<len(r['candidates'])
                model_rows.append(dict(episode=e,frame=r['frame'],matchedCandidateIndex=index))
        rows.append(dict(model=name,matchedFrames=sum(r['matchedCandidateIndex'] is not None for r in model_rows),frames=model_rows))
    per_episode=[]
    for eid in range(6):
        b=read(AUDIT/f'ball-gap-audit/tile-cadence/baseline-{eid:02d}.json')
        old_frames={r['frame'] for r in b['frames'] if any(c.get('accepted') for c in r['candidates'])}
        ball_frames={c['frame'] for c in accepted if c['episode']==eid and c['visualObject']=='active_ball'}
        per_episode.append(dict(episode=eid,visualCounts={label:sum(c['episode']==eid and c['visualObject']==label for c in accepted)
                          for label in ('active_ball','background','player_head')},
                          baselineAcceptedFrames=len(old_frames),retainedBallFrames=len(old_frames&ball_frames),
                          baselineFramesWithoutAcceptedBall=sorted(old_frames-ball_frames),newBallFrames=len(ball_frames-old_frames)))
    return dict(policy=__doc__,manifestSha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                sampledBallCorrespondence=rows,accepted=accepted,episodes=per_episode,
                topHoopVisualReview=dict(correctObjectFrames=list(range(30)),wrongObjectEpisode=5,
                                        notice='All six episode-5 top proposals are the wall banner. Episode 2 frame 35286 is a hoop proposal below 0.25; ROI correctly abstains. Other top proposals reviewed on full-frame sheets.'),
                decision='No production promotion: automatic ROI improves ball coverage but adds background/head tracks; only one of six selected episodes yields a shot candidate with reviewed rim geometry. No automatic outcome or team attribution.')

if __name__=='__main__':
    data=review()
    with (HERE/'visual-review.json').open('x') as stream:json.dump(data,stream,indent=2)
    print(json.dumps(dict(samples=[(r['model'],r['matchedFrames']) for r in data['sampledBallCorrespondence']],episodes=data['episodes']),indent=2))
