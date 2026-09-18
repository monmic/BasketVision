"""Tracker regression tests without loading YOLO or connecting to PostgreSQL."""
import ast
import math
import os
from pathlib import Path
import unittest


source = ast.parse(Path(__file__).with_name("worker.py").read_text(encoding="utf-8-sig"))
nodes = [node for node in source.body if
         (isinstance(node, ast.Assign) and any(
             isinstance(target, ast.Name) and target.id.startswith("BALL_")
             for target in node.targets))
         or (isinstance(node, ast.ClassDef) and node.name == "BallTracker")]
namespace = {"os": os, "math": math, "YOLO_MODEL": "unused"}
exec(compile(ast.Module(body=nodes, type_ignores=[]), "worker.py", "exec"), namespace)
BallTracker = namespace["BallTracker"]


class BallTrackerTests(unittest.TestCase):
    def candidate(self, strong=True):
        return {"centerX": 100.0, "centerY": 100.0,
                "qualityScore": 0.9 if strong else 0.03,
                "confidence": 0.9 if strong else 0.03}

    def step(self, tracker, frame, strong=True):
        return tracker.update([self.candidate(strong)], frame / 30)[0]

    def test_weak_candidates_cannot_confirm(self):
        tracker = BallTracker()
        self.step(tracker, 0)
        for frame in range(1, 20):
            self.assertFalse(self.step(tracker, frame, False)["accepted"])
        self.assertEqual(tracker.confirmed_count(), 0)

    def test_stationary_strong_ball_is_accepted(self):
        tracker = BallTracker()
        for frame in range(20):
            result = self.step(tracker, frame)
        self.assertTrue(result["accepted"])
        self.assertEqual(tracker.confirmed_count(), 1)

    def test_weak_updates_are_bounded_and_checkpointed(self):
        tracker = BallTracker()
        hits = namespace["BALL_TRACK_MIN_HITS"]
        for frame in range(hits):
            self.step(tracker, frame)
        limit = namespace["BALL_TRACK_MAX_WEAK_UPDATES"]
        for frame in range(hits, hits + limit):
            self.assertEqual(self.step(tracker, frame, False)["associationType"], "weak-track-update")
        restored = BallTracker()
        restored.restore(tracker.snapshot())
        result = self.step(restored, hits + limit, False)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["associationType"], "unmatched")

    def test_lost_track_requires_strong_reconfirmation(self):
        tracker = BallTracker()
        hits = namespace["BALL_TRACK_MIN_HITS"]
        for frame in range(hits):
            self.step(tracker, frame)
        tracker.update([], hits / 30)
        self.assertFalse(self.step(tracker, hits + 1, False)["accepted"])
        for frame in range(hits + 2, 2 * hits + 2):
            result = self.step(tracker, frame)
        self.assertTrue(result["accepted"])


if __name__ == "__main__":
    unittest.main()
