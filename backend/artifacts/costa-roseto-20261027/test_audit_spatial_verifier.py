import unittest
from audit_spatial_verifier import counts


class AuditSpatialTests(unittest.TestCase):
    def test_counts_excludes_uncertain_and_uses_frozen_threshold(self):
        rows = [dict(index=i, label=label) for i,label in enumerate(['ball', 'non_ball', 'uncertain', 'ball'])]
        scores = [dict(index=i, score=score) for i,score in enumerate([.5, .6, .9, .49])]
        self.assertEqual(counts(rows, scores, 'score'), dict(ballKept=1, ballRejected=1, falseKept=1, falseRejected=0))

    def test_misaligned_identity_fails(self):
        with self.assertRaises(AssertionError):
            counts([dict(index=1, label='ball')], [dict(index=2, score=.7)], 'score')

    def test_unknown_label_fails(self):
        with self.assertRaises(AssertionError):
            counts([dict(index=1, label='unreviewed')], [dict(index=1, score=.7)], 'score')


if __name__ == '__main__':
    unittest.main()
