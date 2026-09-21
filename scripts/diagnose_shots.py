"""Offline shot-candidate experiment. Never writes to the database or input report."""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vision"))
from shot_detector import Rim, detect_shot_candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Worker vision JSON")
    parser.add_argument("--rim", type=float, nargs=3, required=True, metavar=("X", "Y", "WIDTH"),
                        help="Centre and width of the rim in original video pixels")
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.resolve() == args.report.resolve():
            raise ValueError("Output must differ from the original report")
        data = json.loads(args.report.read_text(encoding="utf-8-sig"))
        video = data["video"]
        rim = Rim(*args.rim, args.start, args.end)
        if rim.end > video["durationSeconds"]:
            raise ValueError("Calibration interval exceeds video duration")
        if (rim.start < (video.get("analysisStartSeconds") or 0)
                or rim.end > (video.get("analysisEndSeconds") or video["durationSeconds"])):
            raise ValueError("Calibration interval exceeds the analyzed interval")
        candidates = detect_shot_candidates(data["ballTrack"], rim, video["width"], video["height"])
        result = {"version": "shot-candidates-0.1", "analysisId": data.get("analysisId"),
                  "calibration": asdict(rim), "candidates": candidates,
                  "notice": "Experimental candidates only; no made/missed classification or team attribution. "
                            "No candidates does not mean no shots. Requires fixed camera throughout calibration interval."}
        # Exclusive creation protects previous review work.
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(result, out, indent=2, allow_nan=False)
        print(f"{len(candidates)} candidates to review: {args.output}")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
