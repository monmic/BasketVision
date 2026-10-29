# Pilot detector, frozen sampling plan

Purpose: test whether full-frame ball supervision can improve the detector;
not a release benchmark or a claim that 27 frames suffice for production.
Keep the operational worker unchanged, CPU-only, no database writes.

Fix the following requested seconds before inspecting new frames:

- train: 0, 6, 10, 14, 18, 22, 26, 30, 34, 38, 42, 46, 50, 54, 58;
- validation: 60, 70, 80, 90, 100, 110;
- test: 120, 130, 140, 150, 160, 170.

The first two minutes were already explored for proposal verification; validation
is a development control, not blind. The test interval has not been used for
training or verifier selection. All splits share one edited source and may
contain replayed actions: report this limitation, check visual duplicates and
never call this source-independent generalization.

Inspect pristine native frames for **all visible active court basketballs**
(exclude stored balls on racks), without using
detector proposals as ground truth. Use empty boxes only for verified absence;
ambiguous visibility is excluded explicitly, not labeled negative. Record pixel
boxes and visible/absent/uncertain status, review overlay geometry before export.
No object-identity or event labels inferred from these boxes.

One bounded training run: existing YOLO26n initialization, single ball class,
CPU two threads, 15 epochs, 640 input, batch 2, freeze first 10 backbone layers,
seed 20261027, no early stopping, no mosaic/mixup/cutmix/copy-paste, no color or
geometric augmentation. Tiny pilot deliberately isolates supervised adaptation.
No external downloads during training. Validation only for best-epoch selection;
freeze its hash before scoring test. Evaluate baseline and selected model with
same full-frame input 960, confidence .02, one-to-one IoU .5 on reviewed frames.
Also compare at .12, an existing new-track confidence threshold, without tuning.
Report elapsed CPU time, all TP/FP/FN and missed/false boxes, not just AP or totals.

Integration gate: no lost baseline matched objects, fewer false positives, no
regression on existing source controls. Passing this tiny test is insufficient
for promotion: continuous tracking and an independent source still needed.

## Follow-up fixed before the second fit

The first run failed controls. Single-class initialization preserves candidate
counts on three checked images. All 99 frozen-backbone BatchNorm buffers are
unchanged, rejecting the running-statistics hypothesis. Training CSV instead
shows a bias learning rate of 0.0725 at epoch 1 despite configured AdamW lr0=.001:
the default warm-up bias rate .1 dominates this tiny, 90-step run.

One diagnostic repeat uses the identical dataset, seed, optimizer, epochs and
augmentations, with warmup_epochs=0 and warmup_bias_lr=0. Freeze a new checkpoint
before evaluation. Do not change inference or tracker thresholds. The already
scored 120–170 second samples are now a known regression control for this repeat,
not a fresh blind test; they remain excluded from training. No parameter sweep.
