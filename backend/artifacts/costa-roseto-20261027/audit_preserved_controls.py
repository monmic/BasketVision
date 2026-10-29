"""Reproduce all sample metrics and verify frozen checkpoint/data provenance."""
import hashlib
import json
from pathlib import Path
from benchmark_detector_pilot import score,regressions
from decide_expanded_detector import decide
from export_detector_pilot import validate_row

BASE=Path(__file__).resolve().parent


if __name__=='__main__':
    read=lambda path:json.loads(Path(path).read_text())
    digest=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    root=BASE/'detector-preserved';evaluation=root/'evaluation'
    frozen=read(root/'training/frozen.json');preservation=read(root/'preservation.json')
    assert digest(root/'training/weights/best.pt')==frozen['selectedWeightsSha256']==preservation['selectedWeightsSha256']
    assert digest(BASE/'detector-expanded/dataset/manifest.json')==frozen['datasetManifestSha256']==preservation['datasetManifestSha256']
    assert digest(root/'initial.pt')==preservation['initialSingleClassSha256']
    allowed=set(read(root/'diagnostic.json')['trainableNames'])
    assert set(preservation['changedTensors'])<=allowed
    assert preservation['denseRegressionOutputsIdentical'] is True
    pilot=read(BASE/'detector-pilot/dataset/manifest.json')['frames']
    truths={f'costa-{role}':dict(frames=[dict(frame=r['frame'],boxes=r['boxes']) for r in pilot if r['split']==role]) for role in ['train','val','test']}
    old=read(BASE.parents[2]/'storage/diagnostics/home-vs-away-dataset-v1/manifest.json')
    old_targets={r['frame']:r['boxes'] for r in read(BASE.parents[2]/'vision/fixtures/home-vs-away-ball-annotations-revised-v1.json')['frames']}
    for name,role in [('home-away-control','test'),('home-away-validation','val')]:
        truths[name]=dict(frames=[dict(frame=r['frame'],boxes=old_targets[r['frame']]) for r in old['frames'] if r['split']==role])
    truths['online-control']=dict(frames=read(BASE.parents[2]/'storage/diagnostics/annotations.json')['frames'])
    fresh_path=BASE/'detector-expanded/fresh/reviewed.json'
    fresh=read(fresh_path)
    truths['costa-fresh']=dict(frames=[dict(frame=r['frame'],boxes=validate_row(r)) for r in fresh['frames'] if r['status']!='uncertain'])
    provenance=read(evaluation/'provenance.json')
    assert provenance['freshAnnotationsSha256']==digest(fresh_path)
    assert provenance['preservedWeightsSha256']==frozen['selectedWeightsSha256']
    summary=read(evaluation/'summary.json')
    for source,truth in truths.items():
        reports={name:read(evaluation/f'{source}-{name}.json') for name in ['baseline','pilot','preserved']}
        assert len({tuple((r['frame'],r['width'],r['height']) for r in report['frames']) for report in reports.values()})==1
        assert summary[source]['reviewedFrames']==len(truth['frames'])
        for threshold,row in summary[source]['thresholds'].items():
            for name,report in reports.items():assert score(report,truth,float(threshold))==row['models'][name]
            assert regressions(dict(baseline=reports['baseline'],pilot=reports['preserved']),truth,float(threshold))==row['baselineObjectsLost']
    assert read(evaluation/'decision.json')==decide(summary,'preserved')
    print('Seven three-model cohorts, object losses, frozen hashes, ambiguity exclusions and decision reproduced.')
