"""Freeze every module except final class logits; inspect actual state drift."""
import hashlib
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent


def classifier_freeze_spec(model):
    head_index=len(model.model)-1
    head=model.model[-1]
    frozen=list(range(head_index))
    trainable=set()
    for branch,child in head.named_children():
        if branch not in {'cv3','one2one_cv3'}:
            frozen.append(f'{head_index}.{branch}')
            continue
        for scale,sequence in enumerate(child):
            for index,layer in enumerate(sequence):
                prefix=f'{head_index}.{branch}.{scale}.{index}'
                if index==len(sequence)-1:
                    trainable.update(f'model.{prefix}.{name}' for name,_ in layer.named_parameters())
                else:frozen.append(prefix)
    if len(trainable)!=12:raise ValueError('Expected six class-output convolutions, weight+bias')
    prefixes=[f'model.{name}.' for name in frozen]+['.dfl']
    actual={name for name,_ in model.named_parameters() if not any(p in name for p in prefixes)}
    if actual!=trainable:raise ValueError(f'Freeze specification mismatch: {actual ^ trainable}')
    return frozen,trainable


def original_single_class(weights):
    from ultralytics import YOLO
    from ultralytics.nn.tasks import DetectionModel
    source=YOLO(str(weights))
    if source.names.get(32)!='sports ball':raise ValueError('Unexpected baseline class')
    model=DetectionModel(source.model.yaml,nc=1,verbose=False)
    model.names={0:'sports ball'}
    model.load(source.model,verbose=False)
    return model


if __name__=='__main__':
    import torch
    from ultralytics import YOLO
    torch.set_num_threads(2)
    out=BASE/'detector-preserved';out.mkdir(exist_ok=False)
    anchor=original_single_class('/model.pt')
    frozen,trainable=classifier_freeze_spec(anchor)
    expanded_path=BASE/'detector-expanded/training/weights/best.pt'
    expanded=YOLO(str(expanded_path)).model.float().state_dict()
    groups={}
    for name,initial in anchor.state_dict().items():
        candidate=expanded[name]
        if initial.shape!=candidate.shape:raise ValueError(name)
        index=int(name.split('.')[1])
        group=('backbone-0-9' if index<10 else 'neck-10-22' if index<23 else
               'regression-head' if '.cv2.' in name or '.one2one_cv2.' in name else 'classification-head')
        kind='normalization-buffer' if name.endswith(('running_mean','running_var','num_batches_tracked')) else 'parameter'
        row=groups.setdefault(group+'/'+kind,dict(tensors=0,changed=0,maxAbsoluteChange=0.))
        delta=float((initial.float()-candidate.float()).abs().max())
        row['tensors']+=1;row['changed']+=delta>0;row['maxAbsoluteChange']=max(row['maxAbsoluteChange'],delta)
    wrapper=YOLO('/model.pt');wrapper.model=anchor
    wrapper.save(str(out/'initial.pt'))
    report=dict(groups=groups,freeze=frozen,trainableNames=sorted(trainable),
        originalWeightsSha256=hashlib.sha256(Path('/model.pt').read_bytes()).hexdigest(),
        expandedWeightsSha256=hashlib.sha256(expanded_path.read_bytes()).hexdigest(),
        notice='Tensor drift is diagnostic evidence of changes, not proof that one component caused the observed regressions.')
    (out/'diagnostic.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
