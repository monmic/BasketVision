"""Export a provenance-bound review and conservative dataset; rescore saved predictions.

Run with Python 3.12 on the host. No inference, training or production writes.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from evaluate_ball_clip import box, matches
from review_decisions import decision

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')

def main():
    source=ROOT/'vision/fixtures/home-vs-away-ball-annotations-revised-v1.json'
    data=OUT.parent/'ball-crops-20261011'
    audit=read(data/'dataset-audit.json')
    assert sha(source)==audit['annotationSha256']
    original=read(source)
    revised=copy.deepcopy(original)
    by_frame={r['frame']:r for r in revised['frames']}
    old={r['frame']:r for r in original['frames']}
    rows=sorted(audit['frames'],key=lambda r:r['frame'])
    assert len(rows)==len(by_frame)==72
    assert {r['frame'] for r in rows}==set(by_frame)
    reviews=[]
    for i,r in enumerate(rows):
        additions,eligible,reason=decision(r['frame'])
        assert eligible or not additions
        for coordinates in additions:
            a,b,c,d=coordinates
            value=box([a/854,b/480,c/854,d/480])
            assert value not in by_frame[r['frame']]['boxes']
            by_frame[r['frame']]['boxes'].append(value)
        reviews.append(dict(frame=r['frame'],split=r['split'],episode=r['episode'],
            image=r['image'],sourceImageSha256=sha(data/'dataset'/r['image']),
            sceneBoard=f'board-{i//6+1:02d}.jpg',reviewStatus='reviewed',
            exportEligible=eligible,additionalBoxesPixels=additions,
            additionalBoxRole='stationary_background_ball' if additions else None,
            reason=reason))
    for frame in old:
        assert by_frame[frame]['boxes'][:len(old[frame]['boxes'])]==old[frame]['boxes']
    review=dict(reviewer='assistant_visual_review',date='2026-10-13',width=854,height=480,
        source=original['source'],parentAnnotationsSha256=sha(source),
        decisionsSha256=sha(OUT/'review_decisions.py'),reviewedFrames=72,
        scope='All full scenes plus enlarged left-wall details; original primary boxes inherited.',
        limitations='Manual approximate bounds at 854x480; single reviewer; no independent exhaustive-label certification. Exclusions are whole-frame conservative exclusions, never negative labels.',
        evidenceSha256={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.suffix in ('.jpg','.png')},frames=reviews)
    save('review.json',review)
    revised.update(parentAnnotationsSha256=sha(source),reviewManifestSha256=sha(OUT/'review.json'),
                   fullyAudited=False,reviewedFrameCount=72,
                   usage='Diagnostic superset; use annotations-eligible.json or dataset for conservative evaluation/training.')
    save('annotations-reviewed.json',revised)
    eligible={r['frame'] for r in reviews if r['exportEligible']}
    clean=copy.deepcopy(revised)
    clean['frames']=[r for r in clean['frames'] if r['frame'] in eligible]
    clean['usage']='Conservative reviewed subset; same episodes and original primary boxes. Exploratory, not independent benchmark.'
    save('annotations-eligible.json',clean)
    dataset=OUT/'dataset'
    if dataset.exists():
        raise FileExistsError('Refusing to mix an existing dataset with a new export')
    counts={s:dict(frames=0,boxes=0,excluded=0) for s in ('train','val','test')}
    for r in rows:
        stats=counts[r['split']]
        if r['frame'] not in eligible:
            stats['excluded']+=1
            continue
        target=dataset/r['image']
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(data/'dataset'/r['image'],target)
        assert sha(target)==sha(data/'dataset'/r['image'])
        label=dataset/r['label']
        label.parent.mkdir(parents=True,exist_ok=True)
        truth=by_frame[r['frame']]['boxes']
        lines=[]
        for x1,y1,x2,y2 in truth:
            lines.append('32 '+' '.join(f'{v:.10f}' for v in ((x1+x2)/2,(y1+y2)/2,x2-x1,y2-y1)))
        label.write_text('\n'.join(lines)+'\n')
        stats['frames']+=1
        stats['boxes']+=len(truth)
    config=read(data/'dataset/data.yaml')
    config['path']=str(dataset)
    (dataset/'data.yaml').write_text(json.dumps(config,indent=2))
    config['path']='/output/dataset'
    (dataset/'data-container.yaml').write_text(json.dumps(config,indent=2))
    assert len(list(dataset.glob('images/*/*.png')))==len(eligible)==51
    assert len(list(dataset.glob('labels/*/*.txt')))==51
    assert sum(c['boxes'] for c in counts.values())==90
    assert sum(len(r['boxes']) for r in revised['frames'])==111
    report=dict(notice='Reference-only recalculation, no new inference or improved model. Eligible comparisons use identical frames before/after. All72 includes uncertain excluded frames and is diagnostic only.',iou=.5,counts=counts,models={})
    for name,folder,prefix in [('baseline','ball-pilot-20261011','baseline'),('crop_model','ball-crops-20261011','pilot')]:
        predictions=read(OUT.parent/folder/f'{prefix}-development-predictions.json')
        predictions.update(read(OUT.parent/folder/f'{prefix}-test-predictions.json'))
        results={}
        for scope,ids in [('all72_diagnostic',set(by_frame)),('eligible51',eligible)]:
            stages={}
            for stage,reference in [('original',old),('reviewed',by_frame)]:
                stages[stage]={}
                for split in counts:
                    assert {int(Path(p['image']).stem.split('-')[-1]) for p in predictions[split]}=={r['frame'] for r in rows if r['split']==split}
                    thresholds={}
                    for threshold in (.02,.1,.25,.5):
                        tp=fp=fn=n=0
                        for p in predictions[split]:
                            frame=int(Path(p['image']).stem.split('-')[-1])
                            if frame not in ids:
                                continue
                            assert len(p['boxes'])==len(p['confidence'])
                            truth=reference[frame]['boxes']
                            pred=[b for b,c in zip(p['boxes'],p['confidence']) if c>=threshold]
                            matched=matches(pred,truth,.5)
                            tp+=matched; fp+=len(pred)-matched; fn+=len(truth)-matched; n+=1
                        thresholds[str(threshold)]=dict(frames=n,matched=tp,unmatchedDetections=fp,missedReferenceBalls=fn)
                    stages[stage][split]=thresholds
            results[scope]=stages
        report['models'][name]=results
    save('reference-only-comparison.json',report)
    save('verification.json',dict(reviewedFrames=72,addedBoxes=39,preservedOriginalBoxes=72,
         counts=counts,exportedFrames=51,exportedBoxes=90,excludedFrames=21,
         classId=32,className='sports ball',originalUnchanged=sha(source)==audit['annotationSha256'],
         reviewSha256=sha(OUT/'review.json'),annotationSha256=sha(OUT/'annotations-reviewed.json'),
         checks=['unique frame coverage','unchanged original boxes','finite bounded additions',
                 'source image hashes','whole-frame exclusions','export image/label counts','prediction split coverage']))
    print(json.dumps(counts,indent=2))
    for model,result in report['models'].items():
        print(model,json.dumps({s:v['0.02'] for s,v in result['eligible51']['reviewed'].items()}))

if __name__=='__main__':
    main()
