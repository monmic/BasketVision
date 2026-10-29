"""One fixed CPU-only fine-tuning run; never touches operational models."""
import hashlib
import json
import os
import time
from pathlib import Path

os.environ['OMP_NUM_THREADS']='2'
os.environ['MKL_NUM_THREADS']='2'
import torch
from ultralytics import YOLO

HERE=Path(__file__).resolve().parent/'detector-pilot'
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--stable-warmup',action='store_true')
parser.add_argument('--expanded',action='store_true')
parser.add_argument('--preserve-geometry',action='store_true')
args=parser.parse_args()
if args.preserve_geometry and (args.expanded or args.stable_warmup):parser.error('Choose one training protocol')
if args.expanded:HERE=HERE.parent/'detector-expanded'
if args.preserve_geometry:HERE=HERE.parent/'detector-preserved'
run='training-stable-warmup' if args.stable_warmup and not args.expanded else 'training'
if (HERE/run).exists():raise FileExistsError('Training is frozen; use a new protocol for another run')
dataset=HERE.parent/'detector-expanded/dataset' if args.preserve_geometry else HERE/'dataset'
config=HERE/'container.yaml' if args.preserve_geometry else dataset/'container.yaml'
config.write_text('path: '+json.dumps(str(dataset))+
    '\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: sports ball\n')
torch.set_num_threads(2)
model=YOLO('/model.pt')
if model.names.get(32)!='sports ball':raise ValueError('Unexpected baseline mapping')
options=dict(data=str(config),device='cpu',epochs=15,imgsz=640,batch=2,workers=0,
    freeze=10,seed=20261027,deterministic=True,patience=0,amp=False,
    optimizer='AdamW',lr0=.001,lrf=.01,warmup_epochs=3,
    mosaic=0.,close_mosaic=0,mixup=0.,cutmix=0.,copy_paste=0.,
    hsv_h=0.,hsv_s=0.,hsv_v=0.,degrees=0.,translate=0.,scale=0.,shear=0.,
    perspective=0.,flipud=0.,fliplr=0.,bgr=0.,multi_scale=0.,
    cls_remap=True,project=str(HERE),name=run,exist_ok=False,
    plots=False,save=True,verbose=False)
if args.preserve_geometry:
    from preserve_detector_geometry import classifier_freeze_spec
    freeze,allowed=classifier_freeze_spec(model.model)
    options['freeze']=freeze
    checked=[]
    def verify_freeze(trainer):
        if checked:return
        actual={name for name,param in trainer.model.named_parameters() if param.requires_grad}
        if actual!=allowed:raise ValueError(f'Unexpected trainable tensors: {actual ^ allowed}')
        if any(module.training for module in trainer.model.modules() if isinstance(module,torch.nn.BatchNorm2d)):
            raise ValueError('BatchNorm statistics must remain frozen')
        checked.append(True)
    model.add_callback('on_train_batch_start',verify_freeze)
start=time.perf_counter()
if args.stable_warmup or args.expanded or args.preserve_geometry:
    options.update(warmup_epochs=0.,warmup_bias_lr=0.)
model.train(**options)
if args.preserve_geometry and not checked:raise ValueError('Freeze callback was not exercised')
best=HERE/run/'weights/best.pt'
report=dict(options=options,elapsedSeconds=time.perf_counter()-start,
    initializationSha256=hashlib.sha256(Path('/model.pt').read_bytes()).hexdigest(),
    datasetManifestSha256=hashlib.sha256((dataset/'manifest.json').read_bytes()).hexdigest(),
    selectedWeightsSha256=hashlib.sha256(best.read_bytes()).hexdigest(),
    notice='Best epoch selected by development validation only; expanded data uses known controls and separately frozen 180–230s samples.' if args.expanded else 'Best epoch selected by development validation only. Stable-warmup follow-up uses already seen test as a regression control, not a fresh blind test.' if args.stable_warmup else 'Best epoch selected by development validation only; test not used for selection.')
if args.preserve_geometry:
    report.update(trainableNames=sorted(allowed),notice='Classification outputs only; all existing cohorts are known controls. Verify every other tensor against the original single-class transfer before evaluating.')
(HERE/run/'frozen.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
