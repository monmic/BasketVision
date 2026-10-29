import unittest
import torch
from spatial_verifier import spatial_pool, crop_bounds


class SpatialVerifierTests(unittest.TestCase):
    def test_pool_retains_quadrant_information_discarded_by_mean(self):
        a = torch.zeros(1, 1, 4, 4)
        a[:, :, :2, :2] = 4
        b = a.flip(-1)
        self.assertTrue(torch.equal(a.mean((2, 3)), b.mean((2, 3))))
        self.assertFalse(torch.equal(spatial_pool(a), spatial_pool(b)))
        self.assertEqual(spatial_pool(a).tolist(), [[4, 0, 0, 0]])

    def test_dimensions_and_global_mean_preserved(self):
        maps = torch.arange(2*256*4*4, dtype=torch.float32).reshape(2, 256, 4, 4)
        before = maps.clone()
        result = spatial_pool(maps)
        self.assertEqual(tuple(result.shape), (2, 1024))
        torch.testing.assert_close(result.reshape(2, 256, 4).mean(-1), maps.mean((2, 3)))
        self.assertTrue(torch.equal(before, maps))
        with self.assertRaises(ValueError):
            spatial_pool(torch.zeros(1, 256, 1, 1))

    def test_native_bounds_clip_round_and_reject_empty(self):
        self.assertEqual(crop_bounds(dict(x1=-2.1, y1=1.8, x2=12.3, y2=25), (20, 10, 3)), [0, 1, 10, 20])
        with self.assertRaises(ValueError):
            crop_bounds(dict(x1=30, y1=0, x2=40, y2=10), (20, 10, 3))


if __name__ == '__main__':
    unittest.main()
