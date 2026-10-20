"""Crop-augmented fine-tuning with full-frame validation and evaluation."""
import hashlib
import importlib.util
import json
import logging
from pathlib import Path
import random
import time

import cv2
import torch
import ultralytics
from ultralytics import YOLO
from ultralytics.utils import LOGGER

from crop_geometry import crop_window, transform_boxes

ROOT = Path('/repo/backend/artifacts')
OUT = Path('/output')
spec = importlib.util.spec_from_file_location('previous_experiment',ROOT/'ball-pilot-20261011/run_experiment.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)


class FullFrameValidationTrainer(previous.VerifiedTrainer):
    def build_dataset(self, img_path, mode='train', batch=None):
        original = self.args.imgsz
        if mode == 'val':
            self.args.imgsz = 960
        try:
            dataset = super().build_dataset(img_path,mode,batch)
            if mode == 'val':
                assert dataset.imgsz == 960
                previous.save('validation-input-audit.json',dict(
                    imgsz=dataset.imgsz,batchShapes=dataset.batch_shapes.tolist(),
                    images=[Path(p).name for p in dataset.im_files]))
            return dataset
        finally:
            self.args.imgsz = original

    def get_validator(self):
        validator = super().get_validator()
        validator.args.imgsz = 960
        return validator


def add_crops(dataset):
    manifest = json.loads((OUT/'dataset-audit.json').read_text())
    rows = []
    rng = random.Random(42)
    for source in manifest['frames']:
        if source['split'] != 'train':
            continue
        image = cv2.imread(str(dataset/source['image']))
        h,w = image.shape[:2]
        labels = (dataset/source['label']).read_text().splitlines()
        boxes = []
        for line in labels:
            cls,x,y,bw,bh=map(float,line.split())
            assert cls==32
            boxes.append([x-bw/2,y-bh/2,x+bw/2,y+bh/2])
        assert len(boxes)==1, 'This pilot expects one annotated ball per source frame'
        for size in [256,512]:
            anchor=(rng.uniform(.25,.75),rng.uniform(.25,.75))
            window=crop_window(boxes[0],w,h,size,anchor)
            mapped=transform_boxes(boxes,w,h,window)
            x,y,r,b=window
            name=Path(source['image']).stem+f'-crop{size}'
            image_path=dataset/'images/train'/(name+'.png')
            label_path=dataset/'labels/train'/(name+'.txt')
            assert not image_path.exists() and not label_path.exists()
            assert cv2.imwrite(str(image_path),image[y:b,x:r])
            label_path.write_text(''.join(
                f'32 {(u+s)/2:.8f} {(v+t)/2:.8f} {s-u:.8f} {t-v:.8f}\n'
                for u,v,s,t in mapped))
            rows.append(dict(sourceFrame=source['frame'],episode=source['episode'],split='train',
                             image=image_path.name,window=window,anchor=anchor,boxes=mapped))
    assert len(rows)==82
    assert len(list((dataset/'images/train').glob('*.png')))==123
    assert len(list((dataset/'images/val').glob('*.png')))==16
    assert len(list((dataset/'images/test').glob('*.png')))==15
    previous.save('crop-manifest.json',dict(seed=42,originalTrain=41,crops=rows,
                    trainImages=123,valFullFrames=16,testFullFrames=15))


def main():
    if (OUT/'dataset').exists() or (OUT/'train').exists():
        raise ValueError('Use a new output directory')
    started=time.monotonic()
    LOGGER.addHandler(logging.FileHandler(OUT/'training.log'))
    torch.set_num_threads(2)
    model=YOLO(str(previous.WEIGHTS))
    dataset=previous.prepare(model.names)
    add_crops(dataset)
    model.train(trainer=FullFrameValidationTrainer,data=str(dataset/'data.yaml'),
                epochs=20,patience=8,imgsz=640,batch=8,device='cpu',workers=0,
                seed=42,deterministic=True,project=str(OUT),name='train',
                exist_ok=False,pretrained=True,freeze=10,optimizer='AdamW',
                lr0=0.0001,warmup_bias_lr=0.0,amp=False,
                mosaic=0.0,close_mosaic=0,mixup=0.0,scale=0.2,translate=0.05,
                plots=False,save=True,classes=[32])
    # Evaluate exclusively the original full frames, never annotation-centered crops.
    full=ROOT/'ball-pilot-20261011/dataset'
    best=OUT/'train/weights/best.pt'
    pilot=previous.score(best,full,['train','val'],'pilot-development')
    last=previous.score(OUT/'train/weights/last.pt',full,['train','val'],'last-development')
    pilot.update(previous.score(best,full,['test'],'pilot-test'))
    baseline=json.loads((ROOT/'ball-pilot-20261011/comparison.json').read_text())['models']['baseline']
    previous.save('comparison.json',dict(
        notice='Exploratory same-game, previously inspected data. No new annotations or verified negatives.',
        selection='Best validation mAP50-95 on full frames at 960; max 20 epochs, patience 8. Test not used for selection.',
        trainInputSize=640,validationInputSize=960,evaluationInputSize=960,
        baselineSha256=hashlib.sha256(previous.WEIGHTS.read_bytes()).hexdigest(),
        pilotSha256=hashlib.sha256(best.read_bytes()).hexdigest(),
        versions=dict(ultralytics=ultralytics.__version__,torch=torch.__version__),
        models=dict(baseline=baseline,pilot=pilot),lastDevelopment=last,
        elapsedSeconds=time.monotonic()-started))


if __name__=='__main__':
    main()
