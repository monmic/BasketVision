"""Prove tensor and dense-box preservation before scoring a classifier-only model."""
import hashlib
import json
from pathlib import Path

import torch
from ultralytics import YOLO
from preserve_detector_geometry import classifier_freeze_spec

BASE=Path(__file__).resolve().parent


def regression_outputs(model,image):
    captured=[];hooks=[]
    for branch in ['cv2','one2one_cv2']:
        for sequence in getattr(model.model[-1],branch):
            hooks.append(sequence.register_forward_hook(lambda module,inputs,output:captured.append(output.detach().clone())))
    # Training forward exercises both heads; frozen BatchNorm remains in eval.
    model.train()
    for module in model.modules():
        if isinstance(module,torch.nn.BatchNorm2d):module.eval()
    try:
        with torch.no_grad():model(image)
    finally:
        for hook in hooks:hook.remove()
    return captured


if __name__=='__main__':
    torch.set_num_threads(2)
    root=BASE/'detector-preserved'
    metadata=json.loads((root/'training/frozen.json').read_text())
    best=root/'training/weights/best.pt'
    if hashlib.sha256(best.read_bytes()).hexdigest()!=metadata['selectedWeightsSha256']:raise ValueError('Changed selected checkpoint')
    dataset=BASE/'detector-expanded/dataset/manifest.json'
    if hashlib.sha256(dataset.read_bytes()).hexdigest()!=metadata['datasetManifestSha256']:raise ValueError('Changed training data')
    anchor=YOLO(str(root/'initial.pt')).model.float()
    trained=YOLO(str(best)).model.float()
    _,allowed=classifier_freeze_spec(anchor)
    state=trained.state_dict();original=anchor.state_dict()
    if state.keys()!=original.keys():raise ValueError('Model structure changed')
    changed=[name for name,tensor in state.items() if not torch.equal(tensor,original[name])]
    unexpected=set(changed)-allowed
    if unexpected:raise ValueError(f'Frozen tensors changed: {sorted(unexpected)}')
    if not changed:raise ValueError('No classifier learning observed')
    if not torch.equal(anchor.stride,trained.stride):raise ValueError('Stride changed')
    torch.manual_seed(20261027);image=torch.rand(2,3,128,128)
    before=regression_outputs(anchor,image);after=regression_outputs(trained,image)
    if len(before)!=6 or len(after)!=6 or any(not torch.equal(a,b) for a,b in zip(before,after)):
        raise ValueError('Dense regression outputs changed')
    report=dict(changedTensors=changed,unchangedTensors=len(state)-len(changed),
        trainableParameters=sum(p.numel() for name,p in trained.named_parameters() if name in allowed),
        denseRegressionOutputsIdentical=True,initialSingleClassSha256=hashlib.sha256((root/'initial.pt').read_bytes()).hexdigest(),
        selectedWeightsSha256=metadata['selectedWeightsSha256'],datasetManifestSha256=metadata['datasetManifestSha256'],
        notice='Exact tensor and synthetic dense-box preservation; confidence/order/threshold can still lose a baseline object, so real-frame controls remain mandatory.')
    with (root/'preservation.json').open('x') as stream:json.dump(report,stream,indent=2)
    print(json.dumps(report,indent=2))
