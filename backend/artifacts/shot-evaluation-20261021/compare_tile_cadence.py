"""Summarize paired inference profiles and reuse existing temporal-rim diagnostic."""
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/'scripts'))
from diagnose_reviewed_shots import diagnose

OUTPUT=HERE/'ball-gap-audit/tile-cadence'


def compare():
    rows=[]
    for eid in range(6):
        folder=HERE/('original-temporal-review' if eid==0 else 'temporal-review')
        registration=next(e for e in json.loads((folder/'rim-review-v2/rim-proposals.json').read_text()) if e['episode']==eid)
        keyframes=[[r['timestamp'],r['x'],r['y'],r['width']] for r in registration['samples']]
        profiles={}
        for profile in ('baseline','every-frame'):
            report=json.loads((OUTPUT/f'{profile}-{eid:02d}.json').read_text())
            accepted=[c for r in report['frames'] for c in r['candidates'] if c['accepted']]
            candidates=diagnose(accepted,keyframes,854,480)
            longest=0
            tracks={}
            for c in accepted:
                tracks.setdefault(c['trackId'],[]).append(c['timestamp'])
            for times in tracks.values():
                run=0
                previous=None
                for timestamp in sorted(set(times)):
                    run=run+1 if previous is not None and timestamp-previous<=.25 else 1
                    longest=max(longest,run)
                    previous=timestamp
            profiles[profile]=dict(frames=len(report['frames']),rawCandidates=sum(len(r['candidates']) for r in report['frames']),
                accepted=len(accepted),longestContinuousAcceptedRun=longest,shotCandidates=candidates,
                elapsedSeconds=report['elapsedSeconds'],stagesSeconds=report['stagesSeconds'])
        a,b=[json.loads((OUTPUT/f'{p}-{eid:02d}.json').read_text()) for p in ('baseline','every-frame')]
        assert [r['frame'] for r in a['frames']]==[r['frame'] for r in b['frames']]
        differing=[k for k in a['settings'] if a['settings'][k]!=b['settings'][k]]
        assert differing==['BALL_TILE_STRIDE'],differing
        rows.append(dict(episode=eid,profiles=profiles))
    totals={profile:dict(elapsedSeconds=sum(r['profiles'][profile]['elapsedSeconds'] for r in rows),
        accepted=sum(r['profiles'][profile]['accepted'] for r in rows),
        rawCandidates=sum(r['profiles'][profile]['rawCandidates'] for r in rows),
        shotCandidates=sum(len(r['profiles'][profile]['shotCandidates']) for r in rows)) for profile in ('baseline','every-frame')}
    return dict(episodes=rows,totals=totals,notice='Local paired single run, 2 CPU threads/cores. Accepted/raw totals are not active-ball recall or precision. Existing reviewed approximate rim keyframes interpolated using diagnose_reviewed_shots; no worker integration.')


if __name__=='__main__':
    result=compare()
    with (OUTPUT/'comparison.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps(result['totals'],indent=2))
