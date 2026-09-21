"""Tracker state transitions, using the worker class without ML dependencies."""
import copy
import json
from pathlib import Path
import unittest

from replay_ball_tracker import load_tracker, replay


def detection(x=100, confidence=.2):
    return dict(centerX=x, centerY=100, width=10, height=10,
                qualityScore=confidence, confidence=confidence)


class BallTrackerTests(unittest.TestCase):
    def camera_sequence(self, independent=False, missing_last=False):
        module = load_tracker({"BALL_TRACK_TEMPORAL_WINDOW": True, "BALL_CAMERA_MOTION_FILTER": True})
        tracker = module["BallTracker"]()
        for i in range(4):
            timestamp = i * .04
            candidate = detection(x=100 + i * (7 if independent else 3))
            motion = {"fromTimestamp": (i-1)*.04, "toTimestamp": timestamp,
                      "matrix": [[1, 0, 3], [0, 1, 0]]} if i else None
            if missing_last and i == 3:
                motion = None
            tracker.update([candidate], timestamp, motion)
        return candidate

    def test_camera_motion_excludes_shot_motion_but_preserves_ball_detection(self):
        candidate = self.camera_sequence()
        self.assertTrue(candidate["accepted"])
        self.assertFalse(candidate["shotMotionEligible"])
        self.assertEqual(candidate["sceneMotionState"], "background_consistent")

    def test_camera_motion_preserves_independent_ball_motion(self):
        candidate = self.camera_sequence(independent=True)
        self.assertTrue(candidate["accepted"])
        self.assertTrue(candidate["shotMotionEligible"])

    def test_unreliable_camera_motion_does_not_reject_ball(self):
        candidate = self.camera_sequence(missing_last=True)
        self.assertTrue(candidate["accepted"])
        self.assertEqual(candidate["sceneMotionState"], "unavailable")
        self.assertTrue(candidate["shotMotionEligible"])

    def test_reviewed_camera_motion_cases(self):
        path = Path(__file__).resolve().parents[1] / "vision/fixtures/camera-motion-review.json"
        cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
        for case in cases:
            with self.subTest(case=case["name"]):
                result = replay(case["report"], overrides={"BALL_TRACK_TEMPORAL_WINDOW": True,
                                                          "BALL_CAMERA_MOTION_FILTER": True})
                for label in case["expected"]:
                    row = next(r for r in result["frames"] if r["frame"] == label["frame"])
                    point = next(c for c in row["candidates"]
                                 if [c[k] for k in ("x1", "y1", "x2", "y2")] == label["box"])
                    self.assertEqual(point["accepted"], label["accepted"])
                    self.assertEqual(point["shotMotionEligible"], label["shotMotionEligible"])

    def tracker(self, enabled=True):
        module = load_tracker({"BALL_TRACK_TEMPORAL_WINDOW": enabled,
                               "BALL_TRACK_NEW_MIN_CONFIDENCE": .12})
        return module["BallTracker"]()

    def update(self, tracker, t, x=100, confidence=.2):
        candidate = detection(x, confidence)
        tracker.update([candidate], t)
        return candidate

    def confirm(self, tracker):
        for t in (0, .033, .067):
            result = self.update(tracker, t)
        self.assertTrue(result["accepted"])

    def test_interrupted_strong_hits_confirm_in_window(self):
        tracker = self.tracker()
        self.update(tracker, 0)
        tracker.update([], .033)
        self.assertFalse(self.update(tracker, .13)["accepted"])
        tracker.update([], .167)
        self.assertTrue(self.update(tracker, .18)["accepted"])

    def test_default_policy_still_requires_consecutive_hits(self):
        tracker = self.tracker(False)
        for t in (0, .13, .4):
            self.assertFalse(self.update(tracker, t)["accepted"])
            tracker.update([], t + .01)

    def test_old_hits_cannot_accumulate_indefinitely(self):
        tracker = self.tracker()
        for t in (0, .3, .6, .9):
            self.assertFalse(self.update(tracker, t)["accepted"])
            tracker.update([], t + .01)

    def test_weak_hits_cannot_confirm_tentative_track(self):
        tracker = self.tracker()
        self.update(tracker, 0)
        for t in (.033, .067, .1, .133):
            self.assertFalse(self.update(tracker, t, confidence=.05)["accepted"])

    def test_short_gap_accepts_nearby_weak_point(self):
        tracker = self.tracker()
        self.confirm(tracker)
        tracker.update([], .1)
        self.assertTrue(self.update(tracker, .133, confidence=.05)["accepted"])

    def test_short_gap_does_not_jump_to_distant_weak_object(self):
        tracker = self.tracker()
        self.confirm(tracker)
        tracker.update([], .1)
        self.assertFalse(self.update(tracker, .133, x=200, confidence=.05)["accepted"])

    def test_weak_recovery_cannot_jump_more_than_one_ball_size(self):
        tracker = self.tracker()
        self.confirm(tracker)
        tracker.update([], .1)
        self.assertFalse(self.update(tracker, .133, x=115, confidence=.05)["accepted"])

    def test_long_gap_requires_fresh_strong_evidence(self):
        tracker = self.tracker()
        self.confirm(tracker)
        self.assertFalse(self.update(tracker, .3, confidence=.05)["accepted"])
        self.assertFalse(self.update(tracker, .333)["accepted"])
        self.assertFalse(self.update(tracker, .367)["accepted"])
        self.assertTrue(self.update(tracker, .4)["accepted"])

    def test_weak_update_limit_survives_missing_frames(self):
        tracker = self.tracker()
        self.confirm(tracker)
        for i in range(1, 7):
            self.assertTrue(self.update(tracker, .067 + i * .033, x=100 + 3*i, confidence=.05)["accepted"])
        tracker.update([], .28)
        self.assertFalse(self.update(tracker, .3, x=121, confidence=.05)["accepted"])

    def test_duplicate_times_do_not_confirm(self):
        tracker = self.tracker()
        for _ in range(4):
            self.assertFalse(self.update(tracker, 0)["accepted"])

    def test_resume_preserves_temporal_evidence(self):
        tracker = self.tracker()
        self.update(tracker, 0)
        tracker.update([], .033)
        self.update(tracker, .13)
        resumed = self.tracker()
        resumed.restore(copy.deepcopy(tracker.snapshot()))
        self.assertEqual(self.update(tracker, .18), self.update(resumed, .18))

    def test_reviewed_background_candidates_remain_rejected(self):
        for name in ("tracker-background-motion.json", "tracker-shoe-recovery.json"):
            with self.subTest(fixture=name):
                path = Path(__file__).resolve().parents[1] / "vision/fixtures" / name
                report = json.loads(path.read_text(encoding="utf-8"))
                result = replay(report, overrides={"BALL_TRACK_TEMPORAL_WINDOW": True})
                for label in report["review"]["negativeCandidates"]:
                    row = next(r for r in result["frames"] if r["frame"] == label["frame"])
                    matches = [c for c in row["candidates"]
                               if [c[k] for k in ("x1", "y1", "x2", "y2")] == label["box"]]
                    self.assertEqual(len(matches), 1)
                    self.assertFalse(matches[0]["accepted"])

    def test_sparse_strong_hits_do_not_confirm_background_false_positive(self):
        tracker = self.tracker()
        # Three strong detections spread over 400 ms are insufficient.
        for t, x in ((0, 100), (.267, 90), (.4, 85)):
            self.assertFalse(self.update(tracker, t, x=x)["accepted"])
            tracker.update([], t + .01)

    def test_legacy_checkpoint_does_not_invent_strong_hits(self):
        tracker = self.tracker()
        self.update(tracker, 0)
        snapshot = copy.deepcopy(tracker.snapshot())
        for track in snapshot.values():
            del track["strongHitTimestamps"]
        resumed = self.tracker()
        resumed.restore(snapshot)
        self.assertFalse(self.update(resumed, .1)["accepted"])


if __name__ == "__main__":
    unittest.main()
