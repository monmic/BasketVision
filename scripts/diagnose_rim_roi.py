"""Offline rim-centred inference; run inside worker image, no DB writes.

Requires manually reviewed rim keyframes. Augments a raw minute report so the
tracker can be replayed with unchanged context outside calibrated intervals.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2

from diagnose_reviewed_shots import rim_at, validate_keyframes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("calibration", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists")
    read = lambda p: json.loads(p.read_text(encoding="utf-8-sig"))
    report, calibration = read(args.report), read(args.calibration)
    cap = cv2.VideoCapture(str(args.video))
    width, height = [int(cap.get(p)) for p in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT)]
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or fps <= 0 or calibration["video"] != dict(width=width, height=height):
        raise ValueError("Video cannot be read or calibration resolution differs")
    if args.video.name != report["sourceVideo"] or args.video.stem != calibration["gameId"]:
        raise ValueError("Video identity differs")
    for episode in calibration["episodes"]:
        validate_keyframes(episode["keyframes"], width, height)
    sys.path.insert(0, "/app")
    import worker as w
    # Match recorded detection settings, independent of container environment.
    for key in ("BALL_CONFIDENCE", "BALL_MODEL"):
        if key in report["settings"]:
            setattr(w, key, report["settings"][key])
    model = w.get_ball_model()
    started = time.perf_counter()
    processed = 0
    for row in report["frames"]:
        timestamp = row["timestamp"]
        rims = [rim_at(e["keyframes"], timestamp) for e in calibration["episodes"]]
        rim = next((r for r in rims if r is not None), None)
        if rim is None:
            continue
        if (row["width"], row["height"]) != (width, height):
            raise ValueError("Report coordinates are resized")
        cap.set(cv2.CAP_PROP_POS_FRAMES, row["frame"])
        ok, frame = cap.read()
        if not ok:
            raise ValueError(f"Cannot decode frame {row['frame']}")
        x, y, size = rim
        radius = 4 * size
        x1, y1 = max(0, int(x-radius)), max(0, int(y-radius))
        x2, y2 = min(width, int(x+radius)), min(height, int(y+radius))
        results = model.predict(frame[y1:y2, x1:x2], classes=[32],
                                conf=w.BALL_CONFIDENCE, imgsz=640, verbose=False)
        extra = w._extract_boxes(results[0] if results else None, 32, "rim_roi", timestamp, x1, y1)
        row["rimRoi"] = dict(bounds=[x1,y1,x2,y2], candidates=extra)
        row["candidates"] = w.merge_ball_candidates(row["candidates"]+extra)
        processed += 1
        if processed % 30 == 0:
            print(f"ROI: {processed} frames, t={timestamp:.3f}", flush=True)
    cap.release()
    report["rimRoiExperiment"] = dict(calibration=calibration, processedFrames=processed,
        elapsedSeconds=time.perf_counter()-started, imgsz=640, radiusRimWidths=4,
        notice="Raw detections require tracker replay. Manual calibration; no automatic rim tracking.")
    # Old tracker totals and timings no longer describe these candidates.
    for key in ("accepted", "elapsedSeconds", "stagesSeconds"):
        report.pop(key, None)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, allow_nan=False)
    print(json.dumps(report["rimRoiExperiment"]), flush=True)


if __name__ == "__main__":
    main()
