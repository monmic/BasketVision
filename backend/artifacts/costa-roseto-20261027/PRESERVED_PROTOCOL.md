# Preserve pretrained geometry: fixed diagnostic and training queue

The expanded detector changes the neck, regression head, classification feature
extractors and their normalization buffers. It loses baseline balls across
sources. Test a narrow hypothesis, not another threshold: learn only the final
classification convolutions, keeping every other parameter and buffer fixed.
Changing classification can still remove a baseline proposal or alter ordering;
frozen geometry is not a guarantee of detector quality or retention.

Queue:
1. Compare expanded tensors against a single-class transfer of the original
   YOLO26n, and quantify neck/regression/normalization drift. Verify classifier
   transfer preserves baseline ball predictions on the three previous references.
2. Construct a freeze list covering all modules except the six final class
   convolutions (one-to-many and one-to-one, three scales). Check actual gradients,
   optimizer updates and BatchNorm buffers before starting the full run.
3. Train once, same frozen 75/21 expanded dataset, same 15 epochs, 640, batch 2,
   AdamW .001, seed, no warm-up/augmentation, CPU quota 2. Initialize original
   pretrained weights, not the expanded failed checkpoint. Select epoch only on
   validation. Verify exact tensor preservation outside class outputs afterward.
4. Freeze checkpoint hash; compare against baseline and prior pilot with the
   existing 960 full-frame evaluator at .02/.12, one-to-one IoU .5. All existing
   references, including 180–230s, are now known development controls.
5. Apply the same no-lost-object/no-source-regression/false-reduction gate. If
   it fails, do not spend CPU on continuous replay or consume more holdout frames.
   If it passes, inspect and score six preselected Costa frames at 240,250,260,
   270,280,290 seconds, then continuous tracking only if these also pass.
6. Record results and integration decision. Passing sample controls is insufficient
   for production. No database, runtime model/config or UI changes in this run.

No further epoch/learning-rate search and no training on control/test frames.

## Follow-up after the raw sample gate

The classifier-only detector preserved all baseline matched objects in the known
controls at both preset confidences, but increased false positives. Before any
further training, assess operating-point feasibility using only the 21 validation
frames. For weak and strong thresholds separately, enumerate emitted validation
score boundaries; require every baseline object, no per-source FP/FN regression,
and strictly fewer aggregate validation FP. Select a monotone pair weak<strong
by total FP, then more TP, then minimal displacement from the original thresholds.
If no such pair exists, stop this follow-up: a monotone score change cannot
meet those validation constraints. Do not adjust constraints on known controls.
If a pair exists, freeze a piecewise-linear monotone score mapping through
(0,0),(weak,.02),(strong,.12),(1,1), then evaluate the already known controls
once with the unchanged gate. Consume 240–290s and continuous replay only on pass.
This is validation-based operating-point selection, not calibrated probability
or a fresh blind test on the previously examined frames. Runtime stays unchanged.

## Strong-hit-only feasibility

The selected mapping reduces false boxes but loses two weak baseline balls.
Before any replay, assess a narrower use of the learned score: retain the entire
baseline proposal stream unchanged, and only allow original strong proposals
(confidence ≥ .12) to start/confirm tracks if supported by a mapped strong box
from the frozen classifier-only model (IoU ≥ .5, same existing object-matching
criterion). Weaker proposals remain available for existing-track updates under
the existing worker rules. No new proposals, no new threshold fitting.

First evaluate cached full-frame controls: every baseline strong object must
remain supported and strong false positives must decrease without any source
regression. If this narrower gate fails, do not run continuous tracking or
consume holdout frames. It does not turn either failed detector gate into a pass.

On strong-only sample pass: replay the known [60,120) interval continuously,
same full/tiled proposals, two independent trackers (legacy and isolated weak-hit
prototype). Only strong-hit eligibility changes; existing weak updates and budgets
remain intact. Compute auxiliary class logits from the actual isolated ball
predictor's frozen features; first prove equivalence to standalone learned-model
inference on full frames/tiles and unchanged baseline outputs. No second CNN pass,
no person predictor changes, no runtime worker edits. Report paired elapsed time
and auxiliary overhead without treating paired time as either full job runtime.
Check all previously verified baseline ball observations and fixed reference
negatives; any lost known ball observation rejects this prototype. Further review
is required even if this partial control passes; counts alone never prove accuracy.
