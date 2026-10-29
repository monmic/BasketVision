"""Contracts for rejecting unsafe motion-only recovery, without ML."""
import unittest
import json
from replay_motion_support import BASE, motion_support, compare, replay


class MotionSupportTests(unittest.TestCase):
    def test_cached_replay_is_causal_and_reproducible(self):
        report = json.loads((BASE / 'detector-preserved/continuous/baseline.json').read_text())
        full = replay(report)
        prefix = replay(dict(report, frames=report['frames'][:1000]))
        self.assertEqual(full['frames'][:1000], prefix['frames'])
        reviewed = json.loads((BASE / 'continuous-review/review.json').read_text())['observations']
        summary = compare(full, reviewed)
        self.assertEqual(summary['knownKept'], dict(ball=54, non_ball=28))
        self.assertEqual(len(summary['lostBallIndices']), 14)
        self.assertFalse(summary['eligibleForFurtherReview'])

    def test_only_mature_continuous_moving_tracks_support(self):
        settings = dict(BALL_STATIC_MIN_HITS=6, BALL_STATIC_MAX_SPEED_PX_PER_SECOND=12)
        candidate = dict(accepted=True, trackAverageSpeedPxPerSecond=13)
        self.assertTrue(motion_support(candidate, dict(hits=6, consecutiveHits=6), settings))
        for track in (None, dict(hits=5, consecutiveHits=5), dict(hits=20, consecutiveHits=2)):
            self.assertFalse(motion_support(candidate, track, settings))
        self.assertFalse(motion_support(dict(candidate, accepted=False), dict(hits=6, consecutiveHits=6), settings))
        self.assertFalse(motion_support(dict(candidate, trackAverageSpeedPxPerSecond=12), dict(hits=6, consecutiveHits=6), settings))

    def test_false_positives_fail_even_if_all_balls_kept(self):
        candidates = [dict(x1=i, y1=0, x2=i+1, y2=1, accepted=True) for i in range(10)]
        rows = [dict(frame=1, candidate=c, baseline=True, label='ball' if i == 0 else 'non_ball', index=i, selectedReference=True)
                for i, c in enumerate(candidates)]
        result = compare(dict(frames=[dict(frame=1, candidates=candidates)]), rows)
        self.assertFalse(result['eligibleForFurtherReview'])
        self.assertEqual(result['knownKept']['non_ball'], 9)

    def test_lost_ball_fails(self):
        c = dict(x1=0, y1=0, x2=1, y2=1)
        rows = [dict(frame=1, candidate=c, baseline=True, label='ball', index=7, selectedReference=True)]
        result = compare(dict(frames=[]), rows)
        self.assertEqual(result['lostBallIndices'], [7])
        self.assertFalse(result['eligibleForFurtherReview'])

    def test_unreviewed_fixed_observation_requires_review(self):
        c = dict(x1=0, y1=0, x2=1, y2=1, accepted=True)
        rows = [dict(frame=1, candidate=dict(c, x1=2), baseline=False, label='non_ball', index=1, selectedReference=True)]
        result = compare(dict(frames=[dict(frame=1, candidates=[c])]), rows)
        self.assertFalse(result['eligibleForFurtherReview'])


if __name__ == '__main__':
    unittest.main()
