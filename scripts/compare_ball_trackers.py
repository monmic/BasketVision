"""Compare tracker policies on identical stored candidates; no inference or DB writes.

Shot annotations define inspection windows, not ball boxes or negative frames.
Only --ball-annotations can supply precision/recall ground truth.
"""
import argparse
import hashlib
import json
from pathlib import Path

from evaluate_ball_clip import evaluate
from replay_ball_tracker import WORKER, replay


def compare(report, shots=None, ball_annotations=None, confirm_window=None, camera_filter=False):
    baseline = replay(report, overrides={"BALL_TRACK_TEMPORAL_WINDOW": False, "BALL_CAMERA_MOTION_FILTER": False})
    overrides = {"BALL_TRACK_TEMPORAL_WINDOW": True, "BALL_CAMERA_MOTION_FILTER": camera_filter}
    if camera_filter and not any(r.get("cameraMotion") for r in report["frames"]):
        raise ValueError("Camera filter comparison requires measured camera motion")
    if confirm_window is not None:
        if not 0.05 <= confirm_window <= 1.5:
            raise ValueError("Confirmation window must be between 0.05 and 1.5 seconds")
        overrides["BALL_TRACK_CONFIRM_WINDOW_SECONDS"] = confirm_window
    experimental = replay(report, overrides=overrides)
    differences = []
    baseline_matches_saved = True
    for original, before, after in zip(report["frames"], baseline["frames"], experimental["frames"]):
        for index, (old, a, b) in enumerate(zip(original["candidates"], before["candidates"], after["candidates"])):
            baseline_matches_saved &= old["accepted"] == a["accepted"]
            if a["accepted"] != b["accepted"]:
                differences.append({"frame": before["frame"], "timestamp": before["timestamp"],
                                    "candidateIndex": index, "before": a, "after": b})
    summary = {
        "sourceVideo": report.get("sourceVideo"), "start": report["start"], "end": report["end"],
        "processedFrames": len(report["frames"]),
        "workerSha256": hashlib.sha256(WORKER.read_bytes()).hexdigest(),
        "experimentalSettings": experimental["settings"],
        "baselineMatchesSavedAcceptance": baseline_matches_saved,
        "baselineAccepted": baseline["accepted"], "experimentalAccepted": experimental["accepted"],
        "cameraExcludedFromShotMotion": [
            {"frame": r["frame"], "timestamp": r["timestamp"], "candidate": c}
            for r in experimental["frames"] for c in r["candidates"]
            if c["accepted"] and c.get("shotMotionEligible") is False],
        "added": sum(d["after"]["accepted"] for d in differences),
        "removed": sum(d["before"]["accepted"] for d in differences),
        "notice": "Accepted ball observations, not detected shots. Unannotated frames are not negatives.",
        "shotWindows": [],
    }
    if shots:
        if Path(shots["sourceVideo"]).name != report.get("sourceVideo"):
            raise ValueError("Shot annotations reference a different video")
        for shot in shots["shots"]:
            start, end = shot["timestampSeconds"] - 2, shot["timestampSeconds"] + 3
            if start < report["start"] or end >= report["end"]:
                raise ValueError("Shot inspection window is not fully covered by the report")
            row = {"id": shot["id"], "timestamp": shot["timestamp"], "start": start, "end": end}
            for label, data in (("baseline", baseline), ("experimental", experimental)):
                points = [c for r in data["frames"] if start <= r["timestamp"] <= end
                          for c in r["candidates"] if c["accepted"]]
                row[label] = {"accepted": len(points), "timestamps": [p["timestamp"] for p in points],
                              "shotMotionEligible": sum(p.get("shotMotionEligible") is not False for p in points)}
            summary["shotWindows"].append(row)
    if ball_annotations:
        summary["ballMetrics"] = {name: evaluate(data, ball_annotations)["metrics"]["accepted"]
                                  for name, data in (("baseline", baseline), ("experimental", experimental))}
    return summary, differences, baseline, experimental


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--shots", type=Path)
    parser.add_argument("--ball-annotations", type=Path)
    parser.add_argument("--confirm-window", type=float, help="Override experimental confirmation window in seconds")
    parser.add_argument("--camera-filter", action="store_true", help="Exclude background-consistent observations from shot motion, preserving detections")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; never overwrites a review")
    args = parser.parse_args()
    def read(path):
        return json.loads(path.read_text(encoding="utf-8-sig")) if path else None
    summary, differences, baseline, experimental = compare(read(args.report), read(args.shots), read(args.ball_annotations), args.confirm_window, args.camera_filter)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for name, data in (("summary", summary), ("differences", differences),
                       ("baseline", baseline), ("experimental", experimental)):
        (args.output_dir / f"{name}.json").write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("shotWindows", "ballMetrics", "experimentalSettings", "cameraExcludedFromShotMotion")}, indent=2))


if __name__ == "__main__":
    main()
