"""Validation-only operating-point feasibility, followed by a fixed control check."""
import copy
import hashlib
import json
from pathlib import Path
from benchmark_detector_pilot import score,regressions
from decide_expanded_detector import decide
from export_detector_pilot import validate_row

BASE=Path(__file__).resolve().parent


def choose_thresholds(reports,truths,original):
    boundaries=sorted({original,1.,*[c['confidence'] for pair in reports.values() for r in pair['pilot']['frames'] for c in r['candidates'] if c['confidence']>=.02]})
    baseline={name:score(pair['baseline'],truths[name],original) for name,pair in reports.items()}
    base_fp=sum(m['fp'] for m in baseline.values())
    feasible=[];retaining=[]
    for threshold in boundaries:
        metrics={name:score(pair['pilot'],truths[name],threshold) for name,pair in reports.items()}
        if any(regressions(pair,truths[name],threshold) or metrics[name]['fn']>baseline[name]['fn'] for name,pair in reports.items()):continue
        row=dict(rawThreshold=threshold,fp=sum(m['fp'] for m in metrics.values()),tp=sum(m['tp'] for m in metrics.values()),metrics=metrics)
        retaining.append(row)
        if row['fp']<base_fp and all(metrics[name]['fp']<=baseline[name]['fp'] for name in reports):feasible.append(row)
    return dict(originalThreshold=original,baseline=baseline,baselineFp=base_fp,feasible=feasible,
        bestRetainingBaseline=min(retaining,key=lambda r:(r['fp'],-r['tp'],abs(r['rawThreshold']-original))) if retaining else None)


def map_score(value,weak,strong):
    if not 0<weak<strong<1:raise ValueError('Require monotone interior knots')
    if value<=weak:return value/weak*.02
    if value<=strong:return .02+(value-weak)/(strong-weak)*(.12-.02)
    return .12+(value-strong)/(1-strong)*.88


if __name__=='__main__':
    root=BASE/'detector-preserved';evaluation=root/'evaluation';out=root/'operating-points';out.mkdir(exist_ok=False)
    read=lambda path:json.loads(Path(path).read_text())
    pilot=read(BASE/'detector-pilot/dataset/manifest.json')['frames']
    old=read(BASE.parents[2]/'storage/diagnostics/home-vs-away-dataset-v1/manifest.json')
    targets={r['frame']:r['boxes'] for r in read(BASE.parents[2]/'vision/fixtures/home-vs-away-ball-annotations-revised-v1.json')['frames']}
    truths={'costa-val':dict(frames=[dict(frame=r['frame'],boxes=r['boxes']) for r in pilot if r['split']=='val']),
        'home-away-validation':dict(frames=[dict(frame=r['frame'],boxes=targets[r['frame']]) for r in old['frames'] if r['split']=='val'])}
    reports={name:dict(baseline=read(evaluation/f'{name}-baseline.json'),pilot=read(evaluation/f'{name}-preserved.json')) for name in truths}
    choices={str(t):choose_thresholds(reports,truths,t) for t in [.02,.12]}
    pairs=[(w,s) for w in choices['0.02']['feasible'] for s in choices['0.12']['feasible'] if w['rawThreshold']<s['rawThreshold']<1]
    chosen=min(pairs,key=lambda pair:(pair[0]['fp']+pair[1]['fp'],-pair[0]['tp']-pair[1]['tp'],
        abs(pair[0]['rawThreshold']-.02)+abs(pair[1]['rawThreshold']-.12))) if pairs else None
    fit=dict(choices=choices,selected=dict(weak=chosen[0]['rawThreshold'],strong=chosen[1]['rawThreshold']) if chosen else None,
        validationReportsSha256={str(path.name):hashlib.sha256(path.read_bytes()).hexdigest() for name in truths for path in [evaluation/f'{name}-baseline.json',evaluation/f'{name}-preserved.json']},
        notice='Selection on validation only; no calibrated-probability claim. No threshold selected from controls.')
    with (out/'selection.json').open('x') as stream:json.dump(fit,stream,indent=2)
    if not chosen:
        print(json.dumps(dict(selected=None,reason='No monotone operating pair meets validation preservation and false-positive requirements.',
            bestRetaining={k:v['bestRetainingBaseline'] for k,v in choices.items()}),indent=2))
    else:
        weak,strong=chosen[0]['rawThreshold'],chosen[1]['rawThreshold']
        for role in ['train','test']:
            truths[f'costa-{role}']=dict(frames=[dict(frame=r['frame'],boxes=r['boxes']) for r in pilot if r['split']==role])
        truths['home-away-control']=dict(frames=[dict(frame=r['frame'],boxes=targets[r['frame']]) for r in old['frames'] if r['split']=='test'])
        truths['online-control']=dict(frames=read(BASE.parents[2]/'storage/diagnostics/annotations.json')['frames'])
        fresh=read(BASE/'detector-expanded/fresh/reviewed.json')
        truths['costa-fresh']=dict(frames=[dict(frame=r['frame'],boxes=validate_row(r)) for r in fresh['frames'] if r['status']!='uncertain'])
        summary={}
        for name,truth in truths.items():
            baseline=read(evaluation/f'{name}-baseline.json');candidate=read(evaluation/f'{name}-preserved.json')
            for row in candidate['frames']:
                for c in row['candidates']:c['confidence']=map_score(c['confidence'],weak,strong)
            summary[name]=dict(thresholds={str(t):dict(models=dict(baseline=score(baseline,truth,t),preserved=score(candidate,truth,t)),
                baselineObjectsLost=regressions(dict(baseline=baseline,pilot=candidate),truth,t)) for t in [.02,.12]})
            (out/f'{name}.json').write_text(json.dumps(candidate,indent=2))
        (out/'summary.json').write_text(json.dumps(summary,indent=2))
        decision=decide(summary,'preserved')
        (out/'decision.json').write_text(json.dumps(decision,indent=2))
        print(json.dumps(dict(selected=fit['selected'],decision=decision),indent=2))
