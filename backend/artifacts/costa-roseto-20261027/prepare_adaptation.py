"""Join reviewed proposal crops, preserving source/episode grouping and hashes."""
import hashlib
import json
import math
import shutil
from pathlib import Path

import cv2

HERE=Path(__file__).resolve().parent
out=HERE/'adapted-examples';out.mkdir(exist_ok=False)
old=Path('/examples');previous=json.loads((old/'manifest.json').read_text())
records=[]
for r in previous['examples']:
    source=old/r['file'];name=f'{len(records):03d}.png'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=r['sha256']:raise ValueError('Changed original example')
    shutil.copyfile(source,out/name);records.append(dict(r,file=name))
review=json.loads((HERE/'review.json').read_text())
reference=json.loads((HERE/'benchmark/raw.json').read_text())
frames={r['frame']:r for r in reference['frames']}
for profile in ('baseline','context'):
    for r in review[profile]['observations']:
        frame=frames[r['frame']]
        image=cv2.imread(str(HERE/'benchmark/reference'/frame['referenceFile']))
        c=r['candidate'];left,top=max(0,math.floor(c['x1'])),max(0,math.floor(c['y1']))
        right,bottom=min(image.shape[1],math.ceil(c['x2'])),min(image.shape[0],math.ceil(c['y2']))
        if left>=right or top>=bottom:raise ValueError('Invalid reviewed crop')
        file=f'{len(records):03d}.png';path=out/file
        if not cv2.imwrite(str(path),image[top:bottom,left:right]):raise ValueError('Write failed')
        records.append(dict(file=file,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            label='active_ball' if r['visualObject']=='ball' else 'non_ball',
            sourceVideo=reference['sourceVideo'],episode='costa-first60',frame=r['frame'],
            timestamp=frame['timestamp'],cropBounds=[left,top,right,bottom],reviewedProfile=profile))
assert len(records)==409
manifest=dict(examples=records,notice=__doc__+' Source-adaptation data, not an untouched Costa test; [60,120) remains unobserved at export.')
with (out/'manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2)
print(f'Prepared {len(records)} reviewed examples, 80 from Costa first minute, no full-frame negative labels')
