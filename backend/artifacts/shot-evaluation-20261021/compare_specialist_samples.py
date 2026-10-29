"""Paired raw-detector screening on the 36 audited frames and a separate reviewed video."""
import hashlib
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

sys.path.insert(0,'/scripts')
from evaluate_ball_clip import evaluate

HERE=Path(__file__).resolve().parent
OUTPUT=HERE/'specialist-screening'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--corrected-checkpoint',action='store_true',help='Screen the latest local fine-tuning without overwriting the paired baseline/specialist run')
parser.add_argument('--model',help='Additional local weights; runs in isolation, never changes worker configuration')
parser.add_argument('--class-id',type=int)
parser.add_argument('--class-label')
parser.add_argument('--profile',default='candidate')
parser.add_argument('--output-dir',type=Path)
parser.add_argument('--hoop-class-id',type=int)
args=parser.parse_args()
if args.model and (args.corrected_checkpoint or args.class_id is None or not args.class_label):
    parser.error('--model requires --class-id/--class-label and excludes --corrected-checkpoint')
if args.hoop_class_id is not None and (not args.model or args.hoop_class_id == args.class_id):
    parser.error('--hoop-class-id requires a custom model and a distinct class')
if args.output_dir:
    OUTPUT=args.output_dir
OUTPUT.mkdir(exist_ok=args.corrected_checkpoint)
read=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
audit=read(HERE/'ball-gap-audit/reviewed-gaps.json')
samples=read(HERE/'ball-gap-audit/samples.json')
context={(e['episode'],r['frame']):r for e in samples for r in e['samples']}
annotations=read(Path('/control-annotations.json'))
datasets=[dict(name='near-rim',source='35b68704-541f-4c6d-b8ab-45228266102a.mp4',fps=30,
               rows=[dict(episode=r['episode'],frame=r['frame']) for r in audit['frames']]),
          dict(name='control',source=annotations['source'],fps=annotations['fps'],
               rows=[dict(frame=r['frame']) for r in annotations['frames']])]
for dataset in datasets:
    cap=cv2.VideoCapture('/videos/'+dataset['source'])
    if not cap.isOpened() or cap.get(cv2.CAP_PROP_FPS)!=dataset['fps']:
        raise ValueError('Source FPS mismatch')
    try:
        for row in dataset['rows']:
            cap.set(cv2.CAP_PROP_POS_FRAMES,row['frame'])
            ok,frame=cap.read()
            if not ok:
                raise RuntimeError(row['frame'])
            row['pixels']=frame
    finally:
        cap.release()

def enforce_threads(predictor):
    if predictor.device.type!='cpu':
        raise RuntimeError('CPU benchmark required')
    if torch.get_num_threads()!=2:
        torch.set_num_threads(2)


summary=[]
profiles=([(args.profile,args.model,args.class_id,args.class_label)] if args.model else
          [('fine-tuned','/corrected.pt',32,'sports ball')] if args.corrected_checkpoint else
          [('baseline','/models/yolo26n.pt',32,'sports ball'),
           ('specialist','/models/university-basketball/best.pt',0,'Ball')])
for name,weights,class_id,label in profiles:
    if any((OUTPUT/f'{name}-{dataset["name"]}.json').exists() for dataset in datasets):
        raise RuntimeError(f'Preserve existing outputs for {name}')
    model=YOLO(weights)
    if model.names.get(class_id)!=label:
        raise ValueError(f'Class mapping mismatch: {model.names}')
    if args.hoop_class_id is not None and 'hoop' not in model.names.get(args.hoop_class_id,'').lower():
        raise ValueError(f'Hoop class mapping mismatch: {model.names}')
    model.add_callback('on_predict_start',enforce_threads)
    settings=dict(model=name,weightsSha256=hashlib.sha256(Path(weights).read_bytes()).hexdigest(),
                  classId=class_id,className=label,hoopClassId=args.hoop_class_id,classes=model.names,imgsz=960,confidence=.02,threads=2,device='cpu',inference='full-frame only')
    for dataset in datasets:
        rows=[]
        inference_seconds=0.
        for n,row in enumerate(dataset['rows']):
            options=dict(classes=[class_id]+([] if args.hoop_class_id is None else [args.hoop_class_id]),conf=.02,imgsz=960,device='cpu',verbose=False)
            if n==0:
                model.predict(row['pixels'],**options)
            started=time.perf_counter()
            result=model.predict(row['pixels'],**options)[0]
            inference_seconds+=time.perf_counter()-started
            candidates=[]
            hoops=[]
            for box in result.boxes:
                x1,y1,x2,y2=box.xyxy[0].tolist()
                destination=candidates if int(box.cls.item())==class_id else hoops
                destination.append(dict(x1=x1,y1=y1,x2=x2,y2=y2,centerX=(x1+x2)/2,centerY=(y1+y2)/2,
                                       confidence=float(box.conf.item()),accepted=False))
            height,width=row['pixels'].shape[:2]
            rows.append(dict(frame=row['frame'],timestamp=row['frame']/dataset['fps'],
                             width=width,height=height,candidates=candidates,hoopCandidates=hoops,
                             **({'episode':row['episode']} if 'episode' in row else {})))
        report=dict(sourceVideo=dataset['source'],source=dict(fps=dataset['fps']),frames=rows,settings=settings,
                    inferenceSeconds=inference_seconds,actualThreads=torch.get_num_threads())
        if dataset['name']=='control':
            report['evaluation']=evaluate(report,annotations)['metrics']['raw']
        else:
            report['notice']='Active-ball visual review only, no exhaustive annotations; raw counts are not recall or precision. No tracker run.'
            for eid in range(6):
                pairs=[(sample,prediction) for sample,prediction in zip(dataset['rows'],rows) if sample['episode']==eid]
                sheet=np.zeros((660,1200,3),dtype=np.uint8)
                for n,(sample,prediction) in enumerate(pairs):
                    left,top=context[(eid,sample['frame'])]['cropOrigin']
                    crop=sample['pixels'][top:top+200,left:left+200].copy()
                    for index,c in enumerate(prediction['candidates']):
                        if c['x2']<left or c['x1']>=left+200 or c['y2']<top or c['y1']>=top+200:
                            continue
                        x1,y1,x2,y2=[round(c[k]) for k in ('x1','y1','x2','y2')]
                        cv2.rectangle(crop,(x1-left,y1-top),(x2-left,y2-top),(0,255,255),1)
                        cv2.putText(crop,str(index),(x1-left,max(10,y1-top-3)),0,.35,(0,255,255),1)
                    x,y=n%4*300,n//4*330
                    sheet[y:y+300,x:x+300]=cv2.resize(crop,(300,300))
                    cv2.putText(sheet,f'{prediction["timestamp"]:.3f} f{sample["frame"]}',(x+2,y+320),0,.45,(255,255,255),1)
                path=OUTPUT/f'{name}-episode-{eid:02d}.jpg'
                if path.exists() or not cv2.imwrite(str(path),sheet):
                    raise RuntimeError(path)
        with (OUTPUT/f'{name}-{dataset["name"]}.json').open('x') as stream:
            json.dump(report,stream,indent=2,allow_nan=False)
        item=dict(model=name,dataset=dataset['name'],frames=len(rows),inferenceSeconds=inference_seconds,
                  rawCandidates=sum(len(r['candidates']) for r in rows),evaluation=report.get('evaluation'))
        summary.append(item)
        print(json.dumps(item),flush=True)
with (OUTPUT/('fine-tuned-summary.json' if args.corrected_checkpoint else 'summary.json')).open('x') as stream:
    json.dump(summary,stream,indent=2)
