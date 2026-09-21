import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vision"))
from shot_detector import Rim, detect_shot_candidates


class ShotDetectorTests(unittest.TestCase):
    def points(self, ys, times=(1, 1.1, 1.2), x=500):
        return [dict(timestamp=t, centerX=x, centerY=y, trackId=1, trackState="confirmed")
                for t, y in zip(times, ys)]

    def detect(self, points):
        return detect_shot_candidates(points, Rim(500, 200, 40, 0, 5), 1280, 720)

    def test_rising_candidate_has_no_result_or_team(self):
        result = self.detect(self.points([260, 235, 215]))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "NeedsReview")
        self.assertIsNone(result[0]["outcome"])
        self.assertIsNone(result[0]["teamId"])

    def test_descending_candidate_is_not_a_made_shot(self):
        self.assertEqual(self.detect(self.points([170, 190, 215]))[0]["reason"], "descending_near_rim")

    def test_30fps_motion_is_not_rejected_by_triplet_duration(self):
        points = self.points([170, 182, 195], (1, 1.033, 1.067))
        self.assertEqual(len(self.detect(points)), 1)
        # The same sampling rate must still reject jitter and association jumps.
        self.assertEqual(self.detect(self.points([195, 196, 197], (1, 1.033, 1.067))), [])
        self.assertEqual(self.detect(self.points([100, 150, 195], (1, 1.033, 1.067))), [])

    def test_stationary_far_and_jitter_are_rejected(self):
        for points in (self.points([200, 200, 200]), self.points([260, 235, 215], x=900),
                       self.points([200, 203, 205]), self.points([240, 210, 225])):
            self.assertEqual(self.detect(points), [])

    def test_gaps_ids_and_duplicate_timestamps_cannot_supply_evidence(self):
        self.assertEqual(self.detect(self.points([260, 235, 215], (1, 2, 3))), [])
        points = self.points([260, 235, 215])
        points[1]["trackId"] = 2
        self.assertEqual(self.detect(points), [])
        points = self.points([260, 235, 215])
        self.assertEqual(self.detect(points + [points[1]]), [])

    def test_unconfirmed_rejected_and_invalid_points_ignored(self):
        for key, value in (("trackState", "tentative"), ("accepted", False),
                           ("centerX", float("nan")), ("trackId", None), ("shotMotionEligible", False)):
            points = self.points([260, 235, 215])
            points[1][key] = value
            self.assertEqual(self.detect(points), [])

    def test_calibration_interval(self):
        self.assertEqual(self.detect(self.points([260, 235, 215], (6, 6.1, 6.2))), [])
        with self.assertRaises(ValueError):
            detect_shot_candidates([], Rim(500, 200, 0, 0, 5), 1280, 720)

    def test_camera_exclusion_breaks_temporal_evidence(self):
        points = self.points([260, 235, 215])
        points.append(dict(points[0], timestamp=1.05, shotMotionEligible=False))
        self.assertEqual(self.detect(points), [])

    def test_fragmented_tracks_deduplicated(self):
        points = self.points([260, 235, 215])
        other = self.points([260, 235, 215], (1.3, 1.4, 1.5))
        for p in other:
            p["trackId"] = 2
        self.assertEqual(len(self.detect(points + other)), 1)

    def test_scale_invariance_and_separate_episodes(self):
        points = self.points([260, 235, 215])
        scaled = [dict(p, centerX=p["centerX"]*2, centerY=p["centerY"]*2) for p in points]
        self.assertEqual(len(detect_shot_candidates(scaled, Rim(1000, 400, 80, 0, 5), 2560, 1440)), 1)
        self.assertEqual(len(self.detect(points + self.points([260, 235, 215], (3, 3.1, 3.2)))), 2)

    def test_cli_preserves_input_and_existing_output(self):
        import json
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "vision.json"
            output = Path(folder) / "shots.json"
            content = json.dumps({"video": {"width": 1280, "height": 720, "durationSeconds": 5},
                                  "ballTrack": self.points([260, 235, 215])})
            source.write_text(content, encoding="utf-8")
            command = [sys.executable, str(Path(__file__).with_name("diagnose_shots.py")), str(source),
                       "--rim", "500", "200", "40", "--start", "0", "--end", "5", "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            saved = output.read_text(encoding="utf-8")
            self.assertEqual(len(json.loads(saved)["candidates"]), 1)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), saved)
            self.assertEqual(source.read_text(encoding="utf-8"), content)


if __name__ == "__main__":
    unittest.main()
