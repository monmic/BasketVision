"""Add measured camera motion to stored candidates, without rerunning inference."""
import argparse
import json
import hashlib
import math
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vision"))
from camera_motion import CameraMotion


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output already exists")
    data = json.loads(args.report.read_text(encoding="utf-8-sig"))
    if data.get("sourceVideo") and data["sourceVideo"] != args.video.name:
        raise ValueError("Video does not match report")
    cap = cv2.VideoCapture(str(args.video))
    motion = CameraMotion()
    valid = 0
    started = time.perf_counter()
    try:
        if not cap.isOpened():
            raise ValueError("Cannot open video")
        if not math.isclose(cap.get(cv2.CAP_PROP_FPS), data["source"]["fps"], rel_tol=1e-6):
            raise ValueError("Video FPS does not match report")
        expected_index = -1
        for index, row in enumerate(data["frames"]):
            if row["frame"] != expected_index:
                cap.set(cv2.CAP_PROP_POS_FRAMES, row["frame"])
            ok, frame = cap.read()
            if not ok or (frame.shape[1], frame.shape[0]) != (row["width"], row["height"]):
                raise ValueError("Missing frame or mismatched video dimensions")
            expected_index = row["frame"] + 1
            row["cameraMotion"] = motion.update(frame, row["timestamp"])
            valid += row["cameraMotion"] is not None
            if index % 300 == 0:
                print(f"{index}/{len(data['frames'])} frames; {valid} reliable estimates", flush=True)
    finally:
        cap.release()
    data["cameraMotionSummary"] = {"reliableFrames": valid, "processedFrames": len(data["frames"]),
                                    "elapsedSeconds": time.perf_counter()-started,
                                    "estimatorSha256": hashlib.sha256(
                                        (Path(__file__).resolve().parents[1] / "vision/camera_motion.py").read_bytes()).hexdigest()}
    data["sourceVideo"] = args.video.name
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(data, out, indent=2, allow_nan=False)
    print(data["cameraMotionSummary"])


if __name__ == "__main__":
    main()
