"""Six-episode adapter around existing ROI inference, tracker replay and shot diagnostic."""
import argparse
import contextlib
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUTPUT=HERE/'rim-roi-trial'
VIDEO='35b68704-541f-4c6d-b8ab-45228266102a.mp4'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path,data):
    with path.open('x',encoding='utf-8') as stream:
        json.dump(data,stream,indent=2,allow_nan=False)


def prepare():
    OUTPUT.mkdir(exist_ok=False)
    episodes=[]
    for eid in range(6):
        folder=HERE/('original-temporal-review' if eid==0 else 'temporal-review')
        registration=next(e for e in read(folder/'rim-review-v2/rim-proposals.json') if e['episode']==eid)
        episodes.append(dict(id=eid,keyframes=[[r['timestamp'],r['x'],r['y'],r['width']] for r in registration['samples']]))
        report=read(HERE/f'ball-gap-audit/tile-cadence/baseline-{eid:02d}.json')
        report['sourceVideo']=VIDEO
        report['settings']['BALL_MODEL']='/models/yolo26n.pt'
        for row in report['frames']:
            row.update(width=854,height=480)
        write(OUTPUT/f'input-{eid:02d}.json',report)
    write(OUTPUT/'calibration.json',dict(gameId=Path(VIDEO).stem,video=dict(width=854,height=480),episodes=episodes,
        notice='Approximate template-derived rim samples visually reviewed previously; interpolated between samples. No automatic production calibration.'))


def infer():
    import numpy as np
    import diagnose_rim_roi
    sys.path.insert(0,'/app')
    import worker as w
    # Warm the ROI inference shape before measuring incremental work.
    w.get_ball_model().predict(np.zeros((208,208,3),dtype=np.uint8),classes=[32],
                               conf=.02,imgsz=640,verbose=False)
    timings=[]
    for eid in range(6):
        print(f'ROI E{eid}: starting',flush=True)
        sys.argv=['diagnose_rim_roi.py',f'/videos/{VIDEO}',str(OUTPUT/f'input-{eid:02d}.json'),
                  str(OUTPUT/'calibration.json'),str(OUTPUT/f'raw-{eid:02d}.json')]
        with (OUTPUT/f'inference-{eid:02d}.log').open('x') as log,contextlib.redirect_stdout(log):
            diagnose_rim_roi.main()
        result=read(OUTPUT/f'raw-{eid:02d}.json')
        timing=result['rimRoiExperiment']
        timings.append(dict(episode=eid,frames=timing['processedFrames'],elapsedSeconds=timing['elapsedSeconds'],cpuThreads=w.torch.get_num_threads()))
        print(f'ROI E{eid}: {timing["processedFrames"]} frames, {timing["elapsedSeconds"]:.2f}s, CPU threads {w.torch.get_num_threads()}',flush=True)
    write(OUTPUT/'timings.json',timings)


def compare():
    from replay_ball_tracker import replay
    from diagnose_reviewed_shots import diagnose
    calibration=read(OUTPUT/'calibration.json')
    summaries=[]
    for eid in range(6):
        base=read(OUTPUT/f'input-{eid:02d}.json')
        raw=read(OUTPUT/f'raw-{eid:02d}.json')
        result=replay(raw)
        write(OUTPUT/f'replayed-{eid:02d}.json',result)
        keys=next(e['keyframes'] for e in calibration['episodes'] if e['id']==eid)
        profiles={}
        for name,report in [('baseline',base),('roi',result)]:
            points=[c for row in report['frames'] for c in row['candidates'] if c['accepted']]
            tracks={}
            for c in points:
                tracks.setdefault(c['trackId'],[]).append(c['timestamp'])
            longest=0
            for times in tracks.values():
                previous=None
                run=0
                for timestamp in sorted(set(times)):
                    run=run+1 if previous is not None and timestamp-previous<=.25 else 1
                    longest=max(longest,run)
                    previous=timestamp
            profiles[name]=dict(accepted=len(points),rawCandidates=sum(len(r['candidates']) for r in report['frames']),
                                longestContinuousAcceptedRun=longest,shotCandidates=diagnose(points,keys,854,480))
        summaries.append(dict(episode=eid,profiles=profiles,baselineElapsedSeconds=base['elapsedSeconds'],
                              roiIncrementalSeconds=raw['rimRoiExperiment']['elapsedSeconds'],
                              roiFrames=raw['rimRoiExperiment']['processedFrames']))
    write(OUTPUT/'comparison.json',dict(episodes=summaries,
        notice='Incremental ROI cost measured separately from saved baseline; sum is an estimate, not a paired end-to-end timing. Approximate reviewed rim samples, unchanged model and tracker thresholds. Raw/accepted totals do not measure precision or recall.'))
    for row in summaries:
        print(row['episode'],[(k,p['accepted'],p['longestContinuousAcceptedRun'],len(p['shotCandidates'])) for k,p in row['profiles'].items()])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','infer','compare'])
    parser.add_argument('--scripts',type=Path,default=Path('../scripts').resolve())
    args=parser.parse_args()
    sys.path.insert(0,str(args.scripts))
    {'prepare':prepare,'infer':infer,'compare':compare}[args.mode]()
