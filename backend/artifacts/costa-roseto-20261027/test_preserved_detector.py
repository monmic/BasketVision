"""Real model/optimizer checks for classifier-only fine-tuning, offline CPU."""
import copy
import unittest
from pathlib import Path
import torch
from ultralytics import YOLO
from ultralytics.cfg import get_cfg
from preserve_detector_geometry import classifier_freeze_spec,original_single_class

BASE=Path(__file__).resolve().parent


class PreservationTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2);torch.manual_seed(20261027)
        self.model=original_single_class('/model.pt')

    def test_real_training_step_preserves_all_other_tensors(self):
        model=self.model;model.args=get_cfg();freeze,allowed=classifier_freeze_spec(model)
        prefixes=[f'model.{name}.' for name in freeze]+['.dfl']
        for name,param in model.named_parameters():param.requires_grad_(name in allowed)
        model.train()
        for name,module in model.named_modules():
            if isinstance(module,torch.nn.BatchNorm2d) and any(p in name for p in prefixes):module.eval()
        self.assertTrue(all(not m.training for m in model.modules() if isinstance(m,torch.nn.BatchNorm2d)))
        before={name:tensor.clone() for name,tensor in model.state_dict().items()}
        optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=.001)
        batch=dict(img=torch.rand(2,3,128,128),cls=torch.zeros(2,1),
            bboxes=torch.tensor([[.5,.5,.15,.15],[.4,.4,.1,.1]]),batch_idx=torch.tensor([0,1]))
        loss,_=model.loss(batch);loss.sum().backward();optimizer.step()
        changed={name for name,tensor in model.state_dict().items() if not torch.equal(tensor,before[name])}
        self.assertTrue(changed);self.assertTrue(changed<=allowed,changed-allowed)
        self.assertTrue(all(name in allowed for name,p in model.named_parameters() if p.grad is not None))

    def test_initialization_preserves_actual_reference_ball_predictions(self):
        baseline=YOLO('/model.pt');single=YOLO('/model.pt');single.model=self.model
        for path in [BASE/'benchmark/reference/frame-000779.png',BASE/'adapted-benchmark/reference/frame-002697.png',
                     BASE/'detector-pilot/evaluation/online-000045.png']:
            old=baseline.predict(str(path),classes=[32],conf=.02,imgsz=960,device='cpu',verbose=False)[0].boxes
            new=single.predict(str(path),classes=[0],conf=.02,imgsz=960,device='cpu',verbose=False)[0].boxes
            self.assertTrue(torch.equal(old.xyxy,new.xyxy))
            self.assertTrue(torch.equal(old.conf,new.conf))


if __name__=='__main__':unittest.main()
