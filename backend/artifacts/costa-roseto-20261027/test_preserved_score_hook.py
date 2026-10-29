"""Prove auxiliary scores match standalone inference and leave baseline intact."""
import unittest
from pathlib import Path
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from preserved_score_hook import PreservedScoreHook

BASE=Path(__file__).resolve().parent


class HookTests(unittest.TestCase):
    def test_full_frame_and_tile_equivalence_and_cleanup(self):
        torch.set_num_threads(2)
        baseline=YOLO('/model.pt');learned=YOLO(str(BASE/'detector-preserved/training/weights/best.pt'))
        frame=cv2.imread(str(BASE/'benchmark/reference/frame-000779.png'))
        options=dict(classes=[32],imgsz=960,conf=.02,device='cpu',verbose=False)
        original=baseline.predict(frame,**options)[0]
        baseline_head=baseline.predictor.model.model.model[-1]
        count=len(baseline_head._forward_hooks)
        hook=PreservedScoreHook(baseline,learned,.02)
        try:
            for image,size in [(frame,960),(frame[:260,:450],640),(frame[:300,400:],640)]:
                actual=baseline.predict(image,**dict(options,imgsz=size))[0]
                extra=hook.native_boxes(actual)
                reference=learned.predict(image,classes=[0],imgsz=size,conf=.02,device='cpu',verbose=False)[0]
                self.assertEqual(len(extra),len(reference.boxes))
                np.testing.assert_allclose(np.asarray([[r[k] for k in ['x1','y1','x2','y2']] for r in extra]).reshape(-1,4),reference.boxes.xyxy.numpy(),atol=1e-4,rtol=1e-5)
                np.testing.assert_allclose([r['confidence'] for r in extra],reference.boxes.conf.numpy(),atol=1e-6,rtol=1e-5)
            repeat=baseline.predict(frame,**options)[0]
            self.assertTrue(torch.equal(original.boxes.data,repeat.boxes.data))
        finally:hook.close()
        self.assertEqual(len(baseline_head._forward_hooks),count)


if __name__=='__main__':unittest.main()
