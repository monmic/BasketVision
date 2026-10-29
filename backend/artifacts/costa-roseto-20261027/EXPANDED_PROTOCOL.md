# Expanded detector dataset: frozen follow-up

Keep the operational worker unchanged. One CPU training run after reviewing
negatives; no inference threshold search. Continue the existing exporter and
training/benchmark scripts.

Training: the pilot's 11 Costa frames plus the 41 previously reviewed Home vs
Away train frames (episodes shot-001/002/003), using revised complete ball boxes.
Add up to 12 visually verified negative context crops per source, mined only
from these training frames using the frozen failed pilot. A crop must not
intersect a visible ball box padded by 16 pixels; inspect the whole crop for
unannotated/stored balls and reject uncertain examples. These are negative
**patches of game frames**, not claims that the original frame contains no ball.
Maximum two crops per frame and four per Home vs Away episode; confidence order
and frame index break ties, preventing a single scene from dominating selection.

Validation: pilot's 5 Costa validation frames plus 16 HVA shot-004 frames.
Controls excluded from training/mining: 6 pilot Costa test frames, 15 HVA
shot-005 frames, all 22 online 720p frames. These are known controls, not blind.
Freeze another six Costa samples at 180,190,200,210,220,230 seconds, before
inspection/inference; never use them for fitting or selection. Same-source
montage can repeat actions: inspect duplicates and state this limitation.

Training: initialize original YOLO26n, 15 epochs, CPU 2 threads/cores, batch 2,
input 640, freeze 10, AdamW .001, no warm-up, same seed and no augmentations as
the stable pilot. Keep full-frame positive samples at native resolution, and
keep all visible active-ball labels when merging datasets. Validation only
selects best epoch; freeze weights hash before scoring controls/fresh samples.
Evaluate baseline/pilot/expanded at 960, confidences .02 and .12, one-to-one
IoU .5 with existing evaluator; compare object losses as well as counts.

Complete this bounded queue: review negatives → export/audit → train → compare
known controls → score the six fresh frames → document integration decision.
Only if sample controls pass (preserve every baseline matched object, fewer
false positives without source regression) proceed to continuous tracking.
No promotion on training metrics or a single source, no manual shot labeling
required from the user, no database writes, downloads or operational config.
