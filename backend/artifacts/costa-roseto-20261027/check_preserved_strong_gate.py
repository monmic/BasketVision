"""Check classifier evidence only for baseline strong-hit eligibility, cached."""
import copy
import json
from pathlib import Path
from benchmark_detector_pilot import score,regressions,iou
from export_detector_pilot import validate_row

BASE=Path(__file__).resolve().parent


if __name__=='__main__':
    root=BASE/'detector-preserved';evaluation=root/'evaluation'
    out=root/'strong-gate';out.mkdir(exist_ok=False)
    read=lambda path:json.loads(Path(path).read_text())
    selected=read(root/'operating-points/selection.json')['selected']
    if selected is None:raise ValueError('No validation-selected operating point')
    threshold=selected['strong']
    pilot=read(BASE/'detector-pilot/dataset/manifest.json')['frames']
    truths={'costa-test':dict(frames=[dict(frame=r['frame'],boxes=r['boxes']) for r in pilot if r['split']=='test'])}
    old=read(BASE.parents[2]/'storage/diagnostics/home-vs-away-dataset-v1/manifest.json')
    targets={r['frame']:r['boxes'] for r in read(BASE.parents[2]/'vision/fixtures/home-vs-away-ball-annotations-revised-v1.json')['frames']}
    truths['home-away-control']=dict(frames=[dict(frame=r['frame'],boxes=targets[r['frame']]) for r in old['frames'] if r['split']=='test'])
    truths['online-control']=dict(frames=read(BASE.parents[2]/'storage/diagnostics/annotations.json')['frames'])
    fresh=read(BASE/'detector-expanded/fresh/reviewed.json')
    truths['costa-fresh']=dict(frames=[dict(frame=r['frame'],boxes=validate_row(r)) for r in fresh['frames'] if r['status']!='uncertain'])
    summary={};reasons=[];base_fp=gate_fp=0
    xyxy=lambda c:[c[k] for k in ['x1','y1','x2','y2']]
    for source,truth in truths.items():
        baseline=read(evaluation/f'{source}-baseline.json')
        learned=read(evaluation/f'{source}-preserved.json')
        support={r['frame']:[c for c in r['candidates'] if c['confidence']>=threshold] for r in learned['frames']}
        filtered=copy.deepcopy(baseline)
        for row in filtered['frames']:
            row['candidates']=[c for c in row['candidates'] if any(iou(xyxy(c),xyxy(s))>=.5 for s in support[row['frame']])]
        old_metrics=score(baseline,truth,.12);new_metrics=score(filtered,truth,.12)
        lost=regressions(dict(baseline=baseline,pilot=filtered),truth,.12)
        if lost or new_metrics['fn']>old_metrics['fn'] or new_metrics['fp']>old_metrics['fp']:
            reasons.append(dict(source=source,lost=lost,baseline=old_metrics,candidate=new_metrics))
        base_fp+=old_metrics['fp'];gate_fp+=new_metrics['fp']
        summary[source]=dict(baseline=old_metrics,strongGate=new_metrics,baselineStrongObjectsLost=lost)
    if gate_fp>=base_fp:reasons.append(dict(reason='No aggregate strong-FP reduction',baseline=base_fp,candidate=gate_fp))
    report=dict(eligibleForContinuousReplay=not reasons,productionRelease=False,strongRawThreshold=threshold,
        results=summary,reasons=reasons,notice='Cached strong-hit feasibility only; full weak baseline stream would be preserved. No tracker or production change.')
    (out/'decision.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
