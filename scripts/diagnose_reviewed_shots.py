"""Offline comparison on manually calibrated episodes; no events or DB writes.

Coordinates are normalized relative to the interpolated rim before applying the
existing detector. Keyframes are approximate annotations, not rim tracking.
"""
import argparse
from bisect import bisect_right
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vision"))
from shot_detector import Rim, detect_shot_candidates


def validate_keyframes(keyframes, width, height):
    if len(keyframes) < 2:
        raise ValueError("At least two reviewed keyframes are required")
    previous = -math.inf
    for t, x, y, size in keyframes:
        if t <= previous or t < 0:
            raise ValueError("Keyframes must have strictly increasing nonnegative times")
        Rim(x, y, size, t, t+1).validate(width, height)
        if previous != -math.inf and t-previous > 1.001:
            raise ValueError("Review keyframes at least once per second; split gaps/out-of-frame intervals")
        previous = t


def rim_at(keyframes, t):
    if not keyframes[0][0] <= t <= keyframes[-1][0]:
        return None
    index = min(bisect_right([k[0] for k in keyframes], t)-1, len(keyframes)-2)
    a, b = keyframes[index:index+2]
    weight = (t-a[0])/(b[0]-a[0])
    return tuple(a[i]+weight*(b[i]-a[i]) for i in (1, 2, 3))


def diagnose(points, keyframes, width, height):
    validate_keyframes(keyframes, width, height)
    origin, reference_width = 1_000_000., 100.
    normalized = []
    for point in points:
        t, x, y = (point.get(k) for k in ("timestamp", "centerX", "centerY"))
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (t, x, y)):
            continue
        if not (0 <= x < width and 0 <= y < height):
            continue
        rim = rim_at(keyframes, t)
        if rim is None:
            continue
        rx, ry, size = rim
        normalized.append(dict(point, centerX=origin+(x-rx)*reference_width/size,
                               centerY=origin+(y-ry)*reference_width/size))
    candidates = detect_shot_candidates(normalized, Rim(origin, origin, reference_width,
                                       keyframes[0][0], keyframes[-1][0]), 2*origin, 2*origin)
    for candidate in candidates:
        for evidence in candidate["evidence"]:
            rx, ry, size = rim_at(keyframes, evidence["timestamp"])
            evidence["x"] = (evidence["x"]-origin)*size/reference_width+rx
            evidence["y"] = (evidence["y"]-origin)*size/reference_width+ry
    return candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("replay", type=Path)
    parser.add_argument("calibration", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    read = lambda p: json.loads(p.read_text(encoding="utf-8-sig"))
    original, replay, calibration = map(read, (args.original, args.replay, args.calibration))
    width, height = original["video"]["width"], original["video"]["height"]
    if calibration["gameId"] != original["gameId"] or calibration["video"] != {"width": width, "height": height}:
        raise ValueError("Calibration does not match the analyzed game/video")
    if Path(original["video"]["path"]).name != replay["sourceVideo"]:
        raise ValueError("Replay belongs to a different video")
    points = {"original": original["ballTrack"], "experimental":
              [c for r in replay["frames"] for c in r["candidates"] if c["accepted"]]}
    result = {"analysisId": original["analysisId"], "calibration": calibration,
              "notice": "Approximate manual calibration. Candidates need visual review; no outcome classification or global accuracy estimate.",
              "episodes": []}
    for episode in calibration["episodes"]:
        keys = episode["keyframes"]
        if (keys[0][0] < max(original["video"]["analysisStartSeconds"], replay["start"])
                or keys[-1][0] > min(original["video"]["analysisEndSeconds"], replay["end"])):
            raise ValueError("Episode is outside analyzed interval")
        item = {"shotId": episode["shotId"], "start": keys[0][0], "end": keys[-1][0]}
        for name, observations in points.items():
            near = [p for p in observations if keys[0][0] <= p["timestamp"] <= keys[-1][0]]
            candidates = diagnose(observations, keys, width, height)
            sensitivity = []
            for dx, dy, dw in ((-3,0,0),(3,0,0),(0,-3,0),(0,3,0),(0,0,-2),(0,0,2)):
                shifted = [[t,x+dx,y+dy,w+dw] for t,x,y,w in keys]
                sensitivity.append({"offset": [dx,dy,dw], "candidates": len(diagnose(observations, shifted, width, height))})
            item[name] = {"points": len(near), "candidates": candidates, "sensitivity": sensitivity,
                          "observations": [{k:p.get(k) for k in ("timestamp","trackId","centerX","centerY","shotMotionEligible")} for p in near]}
        result["episodes"].append(item)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2, allow_nan=False)
    for item in result["episodes"]:
        print(item["shotId"], {name: {"points": item[name]["points"], "candidates": len(item[name]["candidates"])} for name in points})


if __name__ == "__main__":
    main()
