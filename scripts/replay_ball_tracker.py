"""Replay stored candidates without inference, database access or worker imports."""
import argparse
import ast
import copy
import json
import math
from pathlib import Path
from types import SimpleNamespace

WORKER = Path(__file__).resolve().parents[1] / "vision" / "worker.py"


def load_tracker(settings=None, worker=WORKER):
    # Compile the actual tracker and its BALL_* defaults, without importing the
    # worker's ML/database dependencies or starting its service loop.
    tree = ast.parse(worker.read_text(encoding="utf-8-sig"))
    nodes = [n for n in tree.body if
             (isinstance(n, ast.Assign) and len(n.targets) == 1
              and isinstance(n.targets[0], ast.Name) and n.targets[0].id.startswith("BALL_"))
             or (isinstance(n, ast.ClassDef) and n.name == "BallTracker")]
    namespace = {"math": math, "os": SimpleNamespace(getenv=lambda key, default=None: default),
                 "YOLO_MODEL": "unused"}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(worker), "exec"), namespace)
    namespace.update({k: v for k, v in (settings or {}).items() if k.startswith("BALL_")})
    return namespace


def replay(report, worker=WORKER, overrides=None):
    result = copy.deepcopy(report)
    settings = dict(report["settings"], **(overrides or {}))
    module = load_tracker(settings, worker)
    tracker = module["BallTracker"]()
    # Preserve detector evidence only; stale tracker fields would mislabel replay.
    evidence = {"timestamp", "confidence", "source", "x1", "y1", "x2", "y2",
                "centerX", "centerY", "width", "height", "aspectRatio",
                "softAspectPenalty", "softSizePenalty", "qualityScore"}
    previous = -math.inf
    for row in result["frames"]:
        if row["timestamp"] <= previous:
            raise ValueError("Replay frames must have strictly increasing timestamps")
        previous = row["timestamp"]
        row["candidates"] = [{k: v for k, v in c.items() if k in evidence}
                             for c in row["candidates"]]
        trackable = []
        for candidate in row["candidates"]:
            candidate["accepted"] = False
            if candidate["qualityScore"] >= module["BALL_TRACK_UPDATE_MIN_SCORE"]:
                trackable.append(candidate)
            else:
                candidate["rejectionReason"] = "score_below_track_update_threshold"
        if module.get("BALL_CAMERA_MOTION_FILTER"):
            tracker.update(trackable, row["timestamp"], row.get("cameraMotion"))
        else:
            tracker.update(trackable, row["timestamp"])
    result["accepted"] = sum(c["accepted"] for r in result["frames"] for c in r["candidates"])
    result["settings"] = {k: v for k, v in module.items() if k.startswith("BALL_")}
    result["replay"] = {"workerSource": str(worker), "notice": "Tracker reset at segment start; no new inference."}
    # Original inference timings do not measure replay performance.
    result.pop("elapsedSeconds", None)
    result.pop("stagesSeconds", None)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--worker", type=Path, default=WORKER)
    parser.add_argument("--temporal-window", action="store_true", help="Enable experimental temporal confirmation")
    parser.add_argument("--camera-filter", action="store_true", help="Tag shot motion using measured camera transforms")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8-sig"))
    overrides = {"BALL_TRACK_TEMPORAL_WINDOW": True} if args.temporal_window else {}
    if args.camera_filter:
        if not any(r.get("cameraMotion") for r in report["frames"]):
            parser.error("Camera filter requires measured camera transforms")
        overrides["BALL_CAMERA_MOTION_FILTER"] = True
    result = replay(report, args.worker, overrides)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, allow_nan=False)
    print(f"{result['accepted']} accepted; replay saved to {args.output}")


if __name__ == "__main__":
    main()
