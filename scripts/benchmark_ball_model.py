"""Benchmark local detector weights on reviewed frames, without tracking or DB access.

Run in the worker image. Model files must exist locally: no implicit downloads.
All detections are evaluated at source resolution using the existing evaluator.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from evaluate_ball_clip import evaluate


def validate_annotations(annotations):
    from evaluate_ball_clip import box
    frames = annotations.get("frames", [])
    seen = set()
    for row in frames:
        index = row["frame"]
        if type(index) is not int or index < 0 or index in seen:
            raise ValueError("Frames must be unique nonnegative integers")
        seen.add(index)
        for value in row["boxes"]:
            box(value)
    if not seen:
        raise ValueError("No reviewed frames")
    return seen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("weights", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--class-id", type=int, required=True)
    parser.add_argument("--class-name", help="Expected model label; abort on an incorrect class mapping")
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--confidence", type=float, default=.02)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    if (not args.weights.is_file() or args.output.exists() or args.class_id < 0
            or args.imgsz < 32 or args.threads < 1 or not 0 < args.confidence <= 1):
        parser.error("Require local weights, new output, valid class/size/threads/confidence")
    annotations = json.loads(args.annotations.read_text(encoding="utf-8-sig"))
    wanted = validate_annotations(annotations)
    if annotations.get("source") != args.video.name:
        raise ValueError("Annotations belong to another video")
    import cv2
    import torch
    from ultralytics import YOLO
    torch.set_num_threads(args.threads)
    model = YOLO(str(args.weights))
    if args.class_id not in model.names:
        raise ValueError(f"Unknown class {args.class_id}; available: {model.names}")
    if args.class_name is not None and model.names[args.class_id] != args.class_name:
        raise ValueError(f"Expected {args.class_name!r}, got {model.names[args.class_id]!r}")
    cap = cv2.VideoCapture(str(args.video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or fps <= 0:
        raise ValueError("Cannot read video")
    rows, inference_seconds = [], 0.
    try:
        # Sequential decode preserves the exact frame-index annotation contract.
        for index in range(max(wanted)+1):
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f"Missing source frame {index}")
            if index not in wanted:
                continue
            options = dict(classes=[args.class_id], conf=args.confidence,
                           imgsz=args.imgsz, device="cpu", verbose=False)
            if not rows:
                model.predict(frame, **options)  # Warm-up excluded from timings.
            start = time.perf_counter()
            result = model.predict(frame, **options)[0]
            inference_seconds += time.perf_counter()-start
            candidates = []
            for detection in result.boxes:
                x1,y1,x2,y2 = detection.xyxy[0].tolist()
                candidates.append(dict(x1=x1,y1=y1,x2=x2,y2=y2,
                    confidence=float(detection.conf.item()), accepted=False))
            rows.append(dict(frame=index, timestamp=index/fps, width=frame.shape[1],
                             height=frame.shape[0], candidates=candidates))
    finally:
        cap.release()
    report = dict(sourceVideo=args.video.name, source=dict(fps=fps), frames=rows,
        settings=dict(weights=args.weights.name,
            weightsSha256=hashlib.sha256(args.weights.read_bytes()).hexdigest(),
            classId=args.class_id, className=model.names[args.class_id],
            imgsz=args.imgsz, confidence=args.confidence, threads=args.threads,
            device="cpu", inference="full-frame"))
    evaluation = evaluate(report, annotations)
    # No tracker was run: accepted metrics would be misleading.
    report["evaluation"] = dict(reviewedFrames=len(rows), iouThreshold=.5,
        raw=evaluation["metrics"]["raw"], inferenceSeconds=inference_seconds,
        meanInferenceSeconds=inference_seconds/len(rows),
        notice="Reviewed frames only; no tracker. Timing excludes warm-up, decode and model load.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, allow_nan=False)
    print(json.dumps(report["evaluation"], indent=2))


if __name__ == "__main__":
    main()
