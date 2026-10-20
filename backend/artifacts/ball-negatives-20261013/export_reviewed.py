"""Export only visually verified training negatives, without changing existing datasets."""
import hashlib
import json
from pathlib import Path
import cv2
from review_guard import select_reviewed,validate_window,validate_review_binding

root=Path('/output')
prior=Path('/repo/backend/artifacts/ball-crops-20261011')
proposals=json.loads((root/'proposals.json').read_text())
review=json.loads((root/'review.json').read_text())
validate_review_binding((root/'proposals.json').read_bytes(),review)
audit=json.loads((prior/'dataset-audit.json').read_text())
training={Path(r['image']).name:r for r in audit['frames'] if r['split']=='train'}
truth={r['image']:r['truth'] for r in json.loads((prior/'pilot-development-predictions.json').read_text())['train']}
selected=select_reviewed(proposals,review,training)
target=root/'dataset'
if target.exists():
    raise ValueError('Output already exists; preserve the previous export')
validated=[]
for proposal in selected:
    if proposal['frame']!=training[proposal['image']]['frame']:
        raise ValueError('Frame identity differs from training manifest')
    source=prior/'dataset/images/train'/proposal['image']
    image=cv2.imread(str(source))
    h,w=image.shape[:2]
    validate_window(proposal['window'],w,h,truth[proposal['image']])
    validated.append((proposal,source,image))
(target/'images/train').mkdir(parents=True)
(target/'labels/train').mkdir(parents=True)
manifest=[]
for row,source,image in validated:
    x,y,r,b=row['window']
    output=target/'images/train'/(row['id']+'.png')
    if not cv2.imwrite(str(output),image[y:b,x:r]):
        raise RuntimeError('Cannot save crop')
    (target/'labels/train'/(row['id']+'.txt')).write_text('')
    manifest.append(dict(id=row['id'],sourceImage=row['image'],sourceFrame=row['frame'],
                         episode=training[row['image']]['episode'],split='train',window=row['window'],
                         sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                         cropSha256=hashlib.sha256(output.read_bytes()).hexdigest()))
result=dict(notice='Supplement of visually reviewed train negatives, not a complete train/val/test dataset. Nine correlated floor crops, not nine independent scenes.',
            reviewSha256=hashlib.sha256((root/'review.json').read_bytes()).hexdigest(),
            proposalsSha256=hashlib.sha256((root/'proposals.json').read_bytes()).hexdigest(),
            count=len(manifest),frames=manifest)
(root/'negative-manifest.json').write_text(json.dumps(result,indent=2))
print('Exported verified negative crops:',len(manifest))
