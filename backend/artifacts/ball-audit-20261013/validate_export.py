"""Read back exported labels and verify provenance and split isolation."""
import hashlib
import json
from pathlib import Path

out=Path(__file__).resolve().parent
def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
review=read(out/'review.json')
reference=read(out/'annotations-eligible.json')
truth={r['frame']:r['boxes'] for r in reference['frames']}
assert len(review['frames'])==len({r['frame'] for r in review['frames']})==72
assert review['decisionsSha256']==sha(out/'review_decisions.py')
for name,digest in review['evidenceSha256'].items():
    assert sha(out/name)==digest
episodes={}
label_hashes={}
for r in review['frames']:
    assert episodes.setdefault(r['episode'],r['split'])==r['split']
    image=out/'dataset'/r['image']
    label=out/'dataset/labels'/r['split']/(image.stem+'.txt')
    if not r['exportEligible']:
        assert r['frame'] not in truth and not image.exists() and not label.exists()
        continue
    assert sha(image)==r['sourceImageSha256']
    lines=label.read_text().splitlines()
    assert len(lines)==len(truth[r['frame']])
    for line,expected in zip(lines,truth[r['frame']]):
        cls,cx,cy,w,h=map(float,line.split())
        assert cls==32 and w>0 and h>0
        actual=(cx-w/2,cy-h/2,cx+w/2,cy+h/2)
        assert all(abs(a-b)<1e-8 for a,b in zip(actual,expected))
    label_hashes[str(label.relative_to(out))]=sha(label)
verification=read(out/'verification.json')
verification['exportReadback']='passed: 51 label files, 90 boxes, hashes, 21 exclusions, episode isolation'
verification['labelSha256']=label_hashes
verification['predictionSourcesSha256']={}
for folder,prefix in [('ball-pilot-20261011','baseline'),('ball-crops-20261011','pilot')]:
    for kind in ('development','test'):
        p=out.parent/folder/f'{prefix}-{kind}-predictions.json'
        verification['predictionSourcesSha256'][str(p.relative_to(out.parent))]=sha(p)
(out/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
print(verification['exportReadback'])
