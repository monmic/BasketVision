"""Check train-only negative provenance, split integrity, label and model hashes."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE.parents[2]/'scripts'))
from export_ball_dataset import yolo_label
from benchmark_ball_model import validate_annotations
from prepare_detector_negatives import excludes_balls
from export_detector_pilot import validate_row
from benchmark_detector_pilot import score,regressions
from decide_expanded_detector import decide


def audit():
    root=BASE/'detector-expanded';dataset=root/'dataset'
    read=lambda path:json.loads(Path(path).read_text())
    digest=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    manifest=read(dataset/'manifest.json');review=read(root/'negative-review/reviewed.json')
    assert manifest['negativeReviewSha256']==digest(root/'negative-review/reviewed.json')
    assert manifest['pilotManifestSha256']==digest(BASE/'detector-pilot/dataset/manifest.json')
    old_root=BASE.parents[2]/'storage/diagnostics/home-vs-away-dataset-v1'
    old_annotations=BASE.parents[2]/'vision/fixtures/home-vs-away-ball-annotations-revised-v1.json'
    assert manifest['oldManifestSha256']==digest(old_root/'manifest.json')
    assert manifest['oldAnnotationsSha256']==digest(old_annotations)
    rows=manifest['frames'];full=[r for r in rows if r['kind']=='full-frame']
    parents={(r['source'],r['frame']):r for r in full}
    assert len(parents)==len(full)==94
    expected={('costa',r['frame']):(r['split'],r['boxes']) for r in read(BASE/'detector-pilot/dataset/manifest.json')['frames']}
    old_targets={r['frame']:r['boxes'] for r in read(old_annotations)['frames']}
    old_rows=read(old_root/'manifest.json')['frames']
    expected.update({('home-away',r['frame']):(r['split'],old_targets[r['frame']]) for r in old_rows})
    assert parents.keys()==expected.keys()
    for key,row in parents.items():assert (row['split'],row['boxes'])==expected[key]
    assert {r['episode'] for r in full if r['source']=='home-away' and r['split']=='train'}=={'shot-001','shot-002','shot-003'}
    assert {r['episode'] for r in full if r['source']=='home-away' and r['split']=='val'}=={'shot-004'}
    assert {r['episode'] for r in full if r['source']=='home-away' and r['split']=='test'}=={'shot-005'}
    images=set()
    for row in rows:
        assert digest(dataset/row['image'])==row['sha256']
        assert row['sha256'] not in images
        images.add(row['sha256'])
        validate_annotations(dict(frames=[dict(frame=row['frame'],boxes=row['boxes'])]))
        assert (dataset/row['label']).read_text()==''.join(yolo_label(b)+'\n' for b in row['boxes'])
        if row['kind']=='negative-crop':
            parent=parents[row['source'],row['frame']]
            assert parent['split']==row['split']=='train'
            assert parent['sha256']==row['parentSha256']
            original=next(r for r in review['crops'] if r['index']==row['negativeIndex'])
            assert original['status']=='verified-negative'
            assert original['sha256']==row['sha256']
            assert original['ballBoxes']==parent['boxes']
            assert excludes_balls(row['cropBounds'],parent['boxes'],original['width'],original['height'])
            assert row['boxes']==[]
    assert dict(Counter(r['split'] for r in rows))==dict(train=75,val=21,test=21)
    for source in ['costa','home-away']:
        mined=[r for r in rows if r['kind']=='negative-crop' and r['source']==source]
        assert max(Counter(r['frame'] for r in mined).values())<=2
        if source=='home-away':assert max(Counter(r['episode'] for r in mined).values())<=4
    fresh_path=root/'fresh/reviewed.json';fresh=read(fresh_path)
    assert digest(fresh_path)=='c0d63db13003fccaf2ff74785886a44cd456ac1a3dc39e5007d1adecffdb3a2a'
    assert [r['requestedSeconds'] for r in fresh['frames']]==[180,190,200,210,220,230]
    assert sum(r['status']=='uncertain' for r in fresh['frames'])==1
    for row in fresh['frames']:
        validate_row(row)
        assert digest(root/'fresh'/row['file'])==row['sha256']
        assert ('costa',row['frame']) not in parents
    frozen_path=root/'training/frozen.json'
    if frozen_path.exists():
        frozen=read(frozen_path)
        assert frozen['datasetManifestSha256']==digest(dataset/'manifest.json')
        assert frozen['selectedWeightsSha256']==digest(root/'training/weights/best.pt')
    evaluation=root/'evaluation'
    if (evaluation/'summary.json').exists():
        summary=read(evaluation/'summary.json')
        pilot=read(BASE/'detector-pilot/dataset/manifest.json')['frames']
        truths={f'costa-{role}':dict(frames=[dict(frame=r['frame'],boxes=r['boxes']) for r in pilot if r['split']==role]) for role in ['train','val','test']}
        for name,role in [('home-away-control','test'),('home-away-validation','val')]:
            truths[name]=dict(frames=[dict(frame=r['frame'],boxes=old_targets[r['frame']]) for r in old_rows if r['split']==role])
        truths['online-control']=dict(frames=read(BASE.parents[2]/'storage/diagnostics/annotations.json')['frames'])
        truths['costa-fresh']=dict(frames=[dict(frame=r['frame'],boxes=validate_row(r)) for r in fresh['frames'] if r['status']!='uncertain'])
        for source,truth in truths.items():
            reports={name:read(evaluation/f'{source}-{name}.json') for name in ['baseline','pilot','expanded']}
            assert len({tuple(r['frame'] for r in report['frames']) for report in reports.values()})==1
            for threshold,row in summary[source]['thresholds'].items():
                for name,report in reports.items():assert score(report,truth,float(threshold))==row['models'][name]
                assert regressions(dict(baseline=reports['baseline'],pilot=reports['expanded']),truth,float(threshold))==row['baselineObjectsLost']
        assert read(evaluation/'decision.json')==decide(summary)
        provenance=read(evaluation/'provenance.json')
        assert provenance['freshAnnotationsSha256']==digest(fresh_path)
        assert provenance['expandedWeightsSha256']==frozen['selectedWeightsSha256']
        print('All three-model IoU metrics, excluded ambiguity, object losses and decision reproduced from cached boxes.')
    print('117 exported images verified; train-only negatives, splits, labels, hashes and 6 fresh samples checked.')


if __name__=='__main__':audit()
