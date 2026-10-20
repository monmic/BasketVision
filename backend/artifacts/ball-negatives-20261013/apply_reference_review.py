"""Create a diagnostic annotation copy and re-score saved train predictions only."""
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from evaluate_ball_clip import box,matches

out=Path(__file__).resolve().parent
source=ROOT/'vision/fixtures/home-vs-away-ball-annotations-revised-v1.json'
original=json.loads(source.read_text(encoding='utf-8-sig'))
revision=json.loads((out/'missing-ball-review.json').read_text())
assert original['source']==revision['source']
result=copy.deepcopy(original)
by_frame={r['frame']:r for r in result['frames']}
split=json.loads((out.parent/'ball-crops-20261011/dataset-audit.json').read_text())
train={r['frame'] for r in split['frames'] if r['split']=='train'}
seen=set()
for row in revision['additions']:
    frame=row['frame']
    assert frame in train and frame not in seen
    seen.add(frame)
    for x1,y1,x2,y2 in row['boxesPixels']:
        extra=box([x1/revision['width'],y1/revision['height'],x2/revision['width'],y2/revision['height']])
        by_frame[frame]['boxes'].append(extra)
for old in original['frames']:
    new=by_frame[old['frame']]
    assert new['boxes'][:len(old['boxes'])]==old['boxes']
    if old['frame'] not in seen:
        assert new==old
assert len(result['frames'])==72
assert sum(len(r['boxes']) for r in result['frames'])==74
result['targetedAdditionalBallReview']=revision
result['parentAnnotationsSha256']=hashlib.sha256(source.read_bytes()).hexdigest()
result['fullyAudited']=False
target=out/'annotations-targeted-review.json'
with target.open('x',encoding='utf-8') as f:
    json.dump(result,f,indent=2)

report={'notice':'Reference-only diagnostic correction on training frames; no new inference or improved model. Primary-ball boxes and val/test unchanged. Remaining unmatched detections are not certified false positives.',
        'addedBoxes':2,'originalTrainBoxes':41,'revisedTrainBoxes':43,'models':{}}
original_by_frame={r['frame']:r for r in original['frames']}
for name,folder,file in [
    ('baseline','ball-pilot-20261011','baseline-development-predictions.json'),
    ('crop_model','ball-crops-20261011','pilot-development-predictions.json')]:
    rows=json.loads((out.parent/folder/file).read_text())['train']
    stages={}
    for label,reference in [('original',original_by_frame),('targeted_review',by_frame)]:
        counts={'matched':0,'unmatchedDetections':0,'missedReferenceBalls':0}
        for row in rows:
            index=int(Path(row['image']).stem.split('-')[-1])
            truth=reference[index]['boxes']
            predictions=[b for b,c in zip(row['boxes'],row['confidence']) if c>=.02]
            tp=matches(predictions,truth,.5)
            counts['matched']+=tp
            counts['unmatchedDetections']+=len(predictions)-tp
            counts['missedReferenceBalls']+=len(truth)-tp
        stages[label]=counts
    report['models'][name]=stages
(out/'reference-only-comparison.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
