"""Paired frozen-detector evaluation using the repository's IoU evaluator."""
import copy
import hashlib
import json
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent/'detector-pilot'
scripts=Path('/scripts')
sys.path.insert(0,str(scripts if scripts.exists() else HERE.parents[3]/'scripts'))
from evaluate_ball_clip import evaluate, iou


def score(report, truth, confidence):
    filtered=copy.deepcopy(report)
    for row in filtered['frames']:
        row['candidates']=[c for c in row['candidates'] if c['confidence']>=confidence]
    return evaluate(filtered,truth)['metrics']['raw']


def regressions(reports,truth,confidence):
    lost=[]
    for frame in truth['frames']:
        hits={}
        for name,report in reports.items():
            row=next(r for r in report['frames'] if r['frame']==frame['frame'])
            boxes=[[c['x1']/row['width'],c['y1']/row['height'],c['x2']/row['width'],c['y2']/row['height']]
                   for c in row['candidates'] if c['confidence']>=confidence]
            hits[name]={i for i,b in enumerate(frame['boxes']) if any(iou(b,p)>=.5 for p in boxes)}
        lost.extend(dict(frame=frame['frame'],truthBox=i) for i in sorted(hits['baseline']-hits['pilot']))
    return lost


if __name__=='__main__':
    import argparse
    import cv2
    import numpy as np
    import torch
    from ultralytics import YOLO
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restored-buffers',action='store_true')
    parser.add_argument('--stable-warmup',action='store_true')
    parser.add_argument('--expanded',action='store_true')
    parser.add_argument('--preserve-geometry',action='store_true')
    args=parser.parse_args()
    torch.set_num_threads(2)
    if sum([args.restored_buffers,args.stable_warmup,args.expanded,args.preserve_geometry])>1:parser.error('Choose one diagnostic')
    extended=args.expanded or args.preserve_geometry
    candidate_name='preserved' if args.preserve_geometry else 'expanded' if args.expanded else 'pilot'
    run='training-stable-warmup' if args.stable_warmup else 'training'
    experiment=HERE.parent/'detector-expanded' if args.expanded else HERE
    if args.preserve_geometry:experiment=HERE.parent/'detector-preserved'
    out=experiment/('evaluation-restored-buffers' if args.restored_buffers else 'evaluation-stable-warmup' if args.stable_warmup else 'evaluation');out.mkdir(exist_ok=False)
    frozen=json.loads((experiment/run/'frozen.json').read_text())
    best=experiment/run/'weights/best.pt'
    assert hashlib.sha256(best.read_bytes()).hexdigest()==frozen['selectedWeightsSha256']
    if args.preserve_geometry:
        preservation=json.loads((experiment/'preservation.json').read_text())
        assert preservation['selectedWeightsSha256']==frozen['selectedWeightsSha256']
        assert preservation['denseRegressionOutputsIdentical'] is True
    if args.restored_buffers:
        best=HERE/'training/frozen-backbone-buffers.pt'
        diagnostic=json.loads((HERE/'frozen-backbone-check.json').read_text())
        assert hashlib.sha256(best.read_bytes()).hexdigest()==diagnostic['weightsSha256']
    if extended:
        previous=HERE/'training-stable-warmup/weights/best.pt'
        previous_frozen=json.loads((HERE/'training-stable-warmup/frozen.json').read_text())
        assert hashlib.sha256(previous.read_bytes()).hexdigest()==previous_frozen['selectedWeightsSha256']
        models={'baseline':(YOLO('/model.pt'),32),'pilot':(YOLO(str(previous)),0),candidate_name:(YOLO(str(best)),0)}
    else:models={'baseline':(YOLO('/model.pt'),32),'pilot':(YOLO(str(best)),0)}
    for model,cls in models.values():
        assert model.names[cls]=='sports ball'
        model.predict(np.zeros((480,854,3),np.uint8),classes=[cls],imgsz=960,conf=.02,device='cpu',verbose=False)
    manifest=json.loads((HERE/'dataset/manifest.json').read_text())
    sources=[]
    for role in ('train','val','test'):
        rows=[r for r in manifest['frames'] if r['split']==role]
        truth=dict(frames=[dict(frame=r['frame'],boxes=r['boxes']) for r in rows])
        images=[(r['frame'],HERE/'dataset'/r['image']) for r in rows]
        sources.append((f'costa-{role}',truth,images))
    old=json.loads(Path('/old-dataset/manifest.json').read_text())
    annotations=json.loads(Path('/old-annotations.json').read_text())
    targets={r['frame']:r['boxes'] for r in annotations['frames']}
    rows=[r for r in old['frames'] if r['split']=='test']
    sources.append(('home-away-control',dict(frames=[dict(frame=r['frame'],boxes=targets[r['frame']]) for r in rows]),
        [(r['frame'],Path('/old-dataset')/r['image']) for r in rows]))
    if extended:
        rows=[r for r in old['frames'] if r['split']=='val']
        sources.append(('home-away-validation',dict(frames=[dict(frame=r['frame'],boxes=targets[r['frame']]) for r in rows]),
            [(r['frame'],Path('/old-dataset')/r['image']) for r in rows]))
        fresh_root=HERE.parent/'detector-expanded/fresh'
        fresh_path=fresh_root/'reviewed.json'
        fresh=json.loads(fresh_path.read_text())
        truth=dict(frames=[dict(frame=r['frame'],boxes=[[x1/r['width'],y1/r['height'],x2/r['width'],y2/r['height']]
            for x1,y1,x2,y2 in r['pixelBoxes']]) for r in fresh['frames'] if r['status']!='uncertain'])
        sources.append(('costa-fresh',truth,[(r['frame'],fresh_root/r['file']) for r in fresh['frames']]))
        (out/'provenance.json').write_text(json.dumps(dict(
            **{candidate_name+'WeightsSha256':frozen['selectedWeightsSha256']},pilotWeightsSha256=previous_frozen['selectedWeightsSha256'],
            datasetManifestSha256=frozen['datasetManifestSha256'],freshAnnotationsSha256=hashlib.sha256(fresh_path.read_bytes()).hexdigest(),
            excludedFresh=[r for r in fresh['frames'] if r['status']=='uncertain']),indent=2))
    online=json.loads(Path('/online-annotations.json').read_text())
    cap=cv2.VideoCapture('/online.mp4')
    images=[]
    try:
        for row in online['frames']:
            cap.set(cv2.CAP_PROP_POS_FRAMES,row['frame']);ok,frame=cap.read()
            if not ok:raise ValueError('Missing control frame')
            path=out/f'online-{row["frame"]:06d}.png'
            cv2.imwrite(str(path),frame);images.append((row['frame'],path))
    finally:cap.release()
    sources.append(('online-control',dict(frames=online['frames']),images))
    summary={}
    for source,truth,images in sources:
        reports={}
        for name,(model,cls) in models.items():
            rows=[];elapsed=0.
            for index,path in images:
                frame=cv2.imread(str(path));start=time.perf_counter()
                result=model.predict(frame,classes=[cls],imgsz=960,conf=.02,device='cpu',verbose=False)[0]
                elapsed+=time.perf_counter()-start
                candidates=[]
                for box in result.boxes:
                    x1,y1,x2,y2=box.xyxy[0].tolist()
                    candidates.append(dict(x1=x1,y1=y1,x2=x2,y2=y2,confidence=float(box.conf.item()),accepted=True))
                rows.append(dict(frame=index,width=frame.shape[1],height=frame.shape[0],candidates=candidates))
                if source in {'costa-test','costa-fresh'}:
                    for c in candidates:
                        color=(0,255,255) if c['confidence']>=.12 else (255,100,0)
                        cv2.rectangle(frame,(round(c['x1']),round(c['y1'])),(round(c['x2']),round(c['y2'])),color,1)
                    cv2.imwrite(str(out/f'{source}-{name}-{index:06d}.png'),frame)
            report=dict(frames=rows,elapsedSeconds=elapsed)
            reports[name]=report
            (out/f'{source}-{name}.json').write_text(json.dumps(report,indent=2))
        comparison=reports[candidate_name]
        summary[source]=dict(frames=len(images),reviewedFrames=len(truth['frames']),balls=sum(len(r['boxes']) for r in truth['frames']),
            inferenceSeconds={name:r['elapsedSeconds'] for name,r in reports.items()},
            thresholds={str(conf):dict(models={name:score(r,truth,conf) for name,r in reports.items()},
                baselineObjectsLost=regressions(dict(baseline=reports['baseline'],pilot=comparison),truth,conf)) for conf in [.02,.12]})
        print(json.dumps({source:summary[source]}),flush=True)
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
