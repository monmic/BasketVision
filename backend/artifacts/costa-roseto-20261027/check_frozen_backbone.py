"""Diagnostic: restore only frozen-layer BatchNorm buffers, without fitting."""
import hashlib
import json
from pathlib import Path
import torch
from ultralytics import YOLO

HERE=Path(__file__).resolve().parent/'detector-pilot'
torch.set_num_threads(2)
source=YOLO('/model.pt')
pilot=YOLO(str(HERE/'training/weights/best.pt'))
original=source.model.state_dict()
state=pilot.model.state_dict()
changes=[]
for key,value in state.items():
    parts=key.split('.')
    if parts[0]!='model' or int(parts[1])>=10:
        continue
    if not key.endswith(('running_mean','running_var','num_batches_tracked')):
        continue
    before=original[key]
    changes.append(dict(key=key,maxDifference=float((value.float()-before.float()).abs().max())))
    value.copy_(before)
pilot.model.load_state_dict(state)
out=HERE/'training/frozen-backbone-buffers.pt'
if out.exists():raise FileExistsError(out)
pilot.save(str(out))
report=dict(changedBuffers=changes,weightsSha256=hashlib.sha256(out.read_bytes()).hexdigest(),
    notice='Post-hoc diagnostic after first test; restores initial buffers of frozen layers only, no fitting or threshold change.')
(HERE/'frozen-backbone-check.json').write_text(json.dumps(report,indent=2))
print(json.dumps(dict(buffers=len(changes),changed=sum(r['maxDifference']>0 for r in changes),weightsSha256=report['weightsSha256'])))
