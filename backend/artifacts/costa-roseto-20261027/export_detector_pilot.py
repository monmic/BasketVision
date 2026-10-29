"""Export reviewed full frames, preserving split, hashes and excluded ambiguity."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/'scripts'))
from export_ball_dataset import yolo_label
from benchmark_ball_model import validate_annotations


def validate_row(row):
    if row['status'] not in {'visible','absent','uncertain'}:
        raise ValueError('Unknown visibility')
    boxes=row['pixelBoxes']
    if (row['status']=='visible') != bool(boxes):
        raise ValueError('Visibility and boxes disagree')
    if row['split'] not in {'train','val','test'}:
        raise ValueError('Unknown split')
    for x1,y1,x2,y2 in boxes:
        if not (0<=x1<x2<=row['width'] and 0<=y1<y2<=row['height']):
            raise ValueError('Out of bounds')
    return [[x1/row['width'],y1/row['height'],x2/row['width'],y2/row['height']]
            for x1,y1,x2,y2 in boxes]


if __name__=='__main__':
    base=HERE/'detector-pilot'
    source=base/'annotations-draft.json'
    data=json.loads(source.read_text())
    out=base/'dataset';out.mkdir(exist_ok=False)
    manifest=dict(annotationsSha256=hashlib.sha256(source.read_bytes()).hexdigest(),frames=[],excluded=[])
    seen=set();hashes=set()
    for row in data['frames']:
        boxes=validate_row(row)
        digest=hashlib.sha256((base/row['file']).read_bytes()).hexdigest()
        if digest!=row['sha256'] or row['frame'] in seen or digest in hashes:
            raise ValueError('Changed or duplicated frame')
        seen.add(row['frame']);hashes.add(digest)
        if row['status']=='uncertain':
            manifest['excluded'].append(row);continue
        role=row['split'];stem=Path(row['file']).stem
        image=Path('images')/role/(stem+'.png');label=Path('labels')/role/(stem+'.txt')
        (out/image).parent.mkdir(parents=True,exist_ok=True)
        (out/label).parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(base/row['file'],out/image)
        (out/label).write_text(''.join(yolo_label(b)+'\n' for b in boxes))
        manifest['frames'].append(dict(row,boxes=boxes,image=image.as_posix(),label=label.as_posix()))
    for role in ('train','val','test'):
        annotations=dict(frames=[dict(frame=r['frame'],boxes=r['boxes']) for r in manifest['frames'] if r['split']==role])
        validate_annotations(annotations)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    # Match the pretrained class name to retain the sports-ball head via cls_remap.
    (out/'data.yaml').write_text('path: '+json.dumps(out.resolve().as_posix())+
        '\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: sports ball\n')
    print(json.dumps({role:dict(frames=sum(r['split']==role for r in manifest['frames']),
        balls=sum(len(r['boxes']) for r in manifest['frames'] if r['split']==role)) for role in ('train','val','test')}))
