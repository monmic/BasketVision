"""Merge existing reviewed full frames and approved train-only negative crops."""
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

BASE=Path(__file__).resolve().parent
sys.path.insert(0,'/scripts')
from export_ball_dataset import yolo_label
from benchmark_ball_model import validate_annotations

if __name__=='__main__':
    root=BASE/'detector-expanded';out=root/'dataset';out.mkdir(exist_ok=False)
    read=lambda path:json.loads(Path(path).read_text())
    old=read('/old-dataset/manifest.json');truth=read('/old-annotations.json')
    targets={r['frame']:r['boxes'] for r in truth['frames']}
    pilot=read(BASE/'detector-pilot/dataset/manifest.json')
    negatives=read(root/'negative-review/reviewed.json')
    rows=[]
    for r in pilot['frames']:
        rows.append(dict(source='costa',frame=r['frame'],episode='first60' if r['split']=='train' else r['split'],
            split=r['split'],kind='full-frame',boxes=r['boxes'],path=str(BASE/'detector-pilot/dataset'/r['image'])))
    for r in old['frames']:
        rows.append(dict(source='home-away',frame=r['frame'],episode=r['episode'],split=r['split'],
            kind='full-frame',boxes=targets[r['frame']],path=str(Path('/old-dataset')/r['image'])))
    for r in negatives['crops']:
        if r['status']!='verified-negative':continue
        if hashlib.sha256((root/r['file']).read_bytes()).hexdigest()!=r['sha256']:raise ValueError('Changed crop')
        rows.append(dict(source=r['source'],frame=r['frame'],episode=r['episode'],split='train',kind='negative-crop',
            boxes=[],path=str(root/r['file']),cropBounds=r['cropBounds'],negativeIndex=r['index'],parentSha256=r['sourceSha256']))
    identities=set();hashes=set()
    for index,row in enumerate(rows):
        key=(row['source'],row['frame'],row['kind'],row.get('negativeIndex'))
        if key in identities:raise ValueError('Duplicate identity')
        identities.add(key)
        source=Path(row['path']);digest=hashlib.sha256(source.read_bytes()).hexdigest()
        if digest in hashes:raise ValueError('Duplicate image across exported samples')
        hashes.add(digest)
        validate_annotations(dict(frames=[dict(frame=row['frame'],boxes=row['boxes'])]))
        role=row['split'];stem=f'{index:04d}-{row["source"]}-{row["frame"]}'
        image=Path('images')/role/(stem+'.png');label=Path('labels')/role/(stem+'.txt')
        (out/image).parent.mkdir(parents=True,exist_ok=True);(out/label).parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,out/image)
        (out/label).write_text(''.join(yolo_label(b)+'\n' for b in row['boxes']))
        row.update(image=image.as_posix(),label=label.as_posix(),sha256=digest)
    manifest=dict(frames=rows,negativeReviewSha256=hashlib.sha256((root/'negative-review/reviewed.json').read_bytes()).hexdigest(),
        pilotManifestSha256=hashlib.sha256((BASE/'detector-pilot/dataset/manifest.json').read_bytes()).hexdigest(),
        oldManifestSha256=hashlib.sha256(Path('/old-dataset/manifest.json').read_bytes()).hexdigest(),
        oldAnnotationsSha256=hashlib.sha256(Path('/old-annotations.json').read_bytes()).hexdigest())
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (out/'data.yaml').write_text('path: '+json.dumps(str(out))+'\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: sports ball\n')
    print(json.dumps({role:dict(images=sum(r['split']==role for r in rows),balls=sum(len(r['boxes']) for r in rows if r['split']==role),
        gameNegativeCrops=sum(r['split']==role and r['kind']=='negative-crop' for r in rows)) for role in ['train','val','test']}))
