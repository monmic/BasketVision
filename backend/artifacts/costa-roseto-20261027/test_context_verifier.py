import unittest
import numpy as np
from context_verifier import context_bounds, views, eligible


class ContextVerifierTests(unittest.TestCase):
    def test_missing_evaluations_cannot_pass(self):
        self.assertFalse(eligible({}, []))
        good = dict(ballRejected=0, falseKept=1, falseRejected=9)
        pair = dict(detail=good.copy(), context=good.copy())
        self.assertFalse(eligible(dict(a=pair), []))
        self.assertFalse(eligible({}, [pair]))

    def test_threefold_context_and_edge_clipping(self):
        self.assertEqual(context_bounds([20, 20, 30, 40], (100, 100, 3)), [10, 0, 40, 60])
        self.assertEqual(context_bounds([0, 0, 10, 10], (20, 20, 3)), [0, 0, 20, 20])
        with self.assertRaises(ValueError):
            context_bounds([10, 0, 10, 1], (20, 20, 3))

    def test_views_preserve_native_pixels(self):
        image = np.arange(50*60*3).reshape(50, 60, 3)
        before = image.copy()
        a, b, bounds = views(image, [20, 10, 30, 20])
        np.testing.assert_array_equal(a, image[10:20, 20:30])
        self.assertEqual(bounds, [10, 0, 40, 30])
        np.testing.assert_array_equal(b, image[0:30, 10:40])
        np.testing.assert_array_equal(image, before)

    def test_gate_requires_preservation_and_source_nonregression(self):
        good = dict(ballRejected=0, falseKept=1, falseRejected=9)
        pair = dict(detail=good.copy(), context=good.copy())
        self.assertTrue(eligible(dict(a=pair), [pair]))
        bad = dict(detail=good.copy(), context=dict(good, ballRejected=1))
        self.assertFalse(eligible(dict(a=bad), [pair]))
        self.assertFalse(eligible(dict(a=pair), [bad]))
        bad = dict(detail=good.copy(), context=dict(good, falseKept=2))
        self.assertFalse(eligible(dict(a=pair), [bad]))
        bad = dict(detail=good.copy(), context=dict(good, falseRejected=0))
        self.assertFalse(eligible(dict(a=bad), [pair]))


if __name__ == '__main__':
    unittest.main()
