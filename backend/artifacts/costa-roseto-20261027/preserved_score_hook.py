"""Offline auxiliary class scores from the isolated ball predictor's features.

Reads only frozen features; leaves the original model outputs/parameters intact.
No person model or shared tracker/predictor state. Attach after model warm-up.
"""
import time
import torch
from ultralytics.utils import ops
from ultralytics.utils.nms import non_max_suppression


class PreservedScoreHook:
    def __init__(self,baseline,learned,threshold):
        # AutoBackend may use a fused copy; attach to the actual warmed predictor.
        self.head=baseline.predictor.model.model.model[-1]
        if self.head.end2end:raise ValueError('This frozen source uses its NMS/one-to-many inference branch')
        self.weights=[(sequence[-1].weight.detach().clone(),sequence[-1].bias.detach().clone())
                      for sequence in learned.model.model[-1].cv3]
        self.iou=baseline.predictor.args.iou;self.max_det=baseline.predictor.args.max_det
        self.threshold=threshold;self.logits=[];self.predictions=None;self.input_shape=None
        self.seconds=0.;self.hooks=[]
        if self.head.nc!=80 or learned.model.model[-1].nc!=1:raise ValueError('Wrong head mapping')
        for index,sequence in enumerate(self.head.cv3):
            def capture(module,inputs,output,index=index):
                started=time.perf_counter()
                weight,bias=self.weights[index]
                self.logits.append(torch.nn.functional.conv2d(inputs[0],weight,bias).flatten(2))
                self.seconds+=time.perf_counter()-started
            self.hooks.append(sequence[-1].register_forward_hook(capture))
        self.hooks.append(self.head.register_forward_pre_hook(self._start))
        self.hooks.append(self.head.register_forward_hook(self._finish))

    def _start(self,module,inputs):
        self.logits=[]

    def _finish(self,module,inputs,output):
        started=time.perf_counter()
        if module.training or not isinstance(output,tuple):raise ValueError('Inference-only feature hook')
        raw=output[1]
        scores=torch.cat(self.logits,2).sigmoid()
        boxes=module._get_decode_boxes(raw)
        if scores.shape[0]!=1:raise ValueError('Single frame/crop required')
        predictions=non_max_suppression(torch.cat((boxes,scores),1),conf_thres=self.threshold,
            iou_thres=self.iou,classes=[0],max_det=self.max_det,nc=1)[0]
        self.predictions=(predictions[:,:4].detach().clone(),predictions[:,4].detach().clone())
        stride=int(module.stride[0]);feature=raw['feats'][0]
        self.input_shape=(feature.shape[2]*stride,feature.shape[3]*stride)
        self.seconds+=time.perf_counter()-started

    def native_boxes(self,result,offset=(0,0)):
        started=time.perf_counter()
        boxes,scores=self.predictions
        boxes=ops.scale_boxes(self.input_shape,boxes.clone(),result.orig_shape)
        rows=[]
        for box,score in zip(boxes.tolist(),scores.tolist()):
            rows.append(dict(x1=box[0]+offset[0],y1=box[1]+offset[1],x2=box[2]+offset[0],y2=box[3]+offset[1],confidence=score))
        self.seconds+=time.perf_counter()-started
        return rows

    def close(self):
        for hook in self.hooks:hook.remove()
