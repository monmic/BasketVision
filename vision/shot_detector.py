"""Experimental rim-approach candidates, NOT made/missed shot classification.

Pure Python: consumes accepted worker ballTrack points in original video pixels.
Calibration is valid only inside an explicitly reviewed fixed-camera interval.
"""
import math
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Rim:
    x: float
    y: float
    width: float
    start: float
    end: float

    def validate(self, video_width, video_height):
        values = (self.x, self.y, self.width, self.start, self.end,
                  video_width, video_height)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Calibration and video dimensions must be finite")
        if not (video_width > 0 and video_height > 0
                and 0 < self.width <= video_width
                and self.width / 2 <= self.x <= video_width - self.width / 2
                and 0 <= self.y < video_height and 0 <= self.start < self.end):
            raise ValueError("Invalid rim geometry or calibration interval")


def detect_shot_candidates(points, rim, video_width, video_height):
    """Find a short rising approach to the rim or descending passage near it.

    Require three distinct observations on the same confirmed track, no gap >250ms,
    measurable vertical motion and proximity to the rim. Coordinates increase
    downward. Thresholds are experimental and scaled by the annotated rim width.
    """
    rim.validate(video_width, video_height)
    tracks = defaultdict(list)
    excluded_times = defaultdict(list)
    for p in points:
        if p.get("shotMotionEligible") is False and p.get("trackId") is not None:
            timestamp = p.get("timestamp")
            if isinstance(timestamp, (int, float)) and math.isfinite(timestamp):
                excluded_times[p["trackId"]].append(timestamp)
        if (p.get("trackId") is None or p.get("trackState") != "confirmed"
                or p.get("accepted") is False or p.get("shotMotionEligible") is False):
            continue
        values = [p.get(k) for k in ("timestamp", "centerX", "centerY")]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
            continue
        t, x, y = values
        if rim.start <= t <= rim.end and 0 <= x < video_width and 0 <= y < video_height:
            tracks[p["trackId"]].append((t, x, y))

    candidates = []
    for track_id, track in tracks.items():
        excluded = sorted(excluded_times[track_id])
        # Ambiguous duplicate observations cannot supply temporal evidence.
        by_time = defaultdict(list)
        for p in track:
            by_time[p[0]].append(p)
        track = [items[0] for _, items in sorted(by_time.items()) if len(items) == 1]
        for a, b, c in zip(track, track[1:], track[2:]):
            # Excluded scene motion breaks evidence; do not join observations
            # across a camera-consistent interval after removing its points.
            excluded_index = bisect_left(excluded, a[0])
            if excluded_index < len(excluded) and excluded[excluded_index] <= c[0]:
                continue
            # A fixed minimum span rejects every consecutive triplet at 30 fps
            # (67 ms) and above. Spatial displacement and speed checks below
            # supply the motion evidence independently of sampling frequency.
            if not (0 < b[0]-a[0] <= .25 and 0 < c[0]-b[0] <= .25):
                continue
            # Reject implausible association jumps (in rim widths per second).
            if any(math.hypot(q[1]-p[1], q[2]-p[2]) / (q[0]-p[0]) > 30*rim.width
                   for p, q in ((a, b), (b, c))):
                continue
            near = abs(c[1]-rim.x) <= 1.5*rim.width and abs(c[2]-rim.y) <= rim.width
            rising = (a[2] > b[2] > c[2] and a[2]-c[2] >= .5*rim.width
                      and math.hypot(c[1]-rim.x, c[2]-rim.y)
                      < math.hypot(a[1]-rim.x, a[2]-rim.y))
            falling = (a[2] < b[2] < c[2] and c[2]-a[2] >= .5*rim.width
                       and a[2] < rim.y and abs(a[1]-rim.x) <= 1.5*rim.width)
            if near and (rising or falling):
                candidates.append({
                    "timestamp": c[0], "startSeconds": a[0], "endSeconds": c[0],
                    "trackId": track_id, "type": "ShotCandidate",
                    "status": "NeedsReview", "teamId": None, "outcome": None,
                    "reason": "rising_rim_approach" if rising else "descending_near_rim",
                    "evidence": [{"timestamp": p[0], "x": p[1], "y": p[2]} for p in (a, b, c)],
                })
    # One review item per short episode, including fragmented track IDs.
    result = []
    for candidate in sorted(candidates, key=lambda c: c["timestamp"]):
        if result and candidate["timestamp"] - result[-1]["endSeconds"] <= 1:
            result[-1]["endSeconds"] = candidate["endSeconds"]
            continue
        result.append(candidate)
    return result
