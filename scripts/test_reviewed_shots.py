import unittest

from diagnose_reviewed_shots import diagnose, rim_at, validate_keyframes


class ReviewedShotsTests(unittest.TestCase):
    def test_interpolation_without_extrapolation(self):
        keys = [[1, 400, 200, 40], [2, 500, 220, 60]]
        self.assertEqual(rim_at(keys, 1.5), (450, 210, 50))
        self.assertEqual(rim_at(keys, 2), (500, 220, 60))
        self.assertIsNone(rim_at(keys, .9))
        self.assertIsNone(rim_at(keys, 2.1))

    def test_camera_translation_and_zoom_preserve_candidate_and_evidence(self):
        for keys in ([[1, 400, 200, 40], [2, 400, 200, 40]],
                     [[1, 400, 200, 40], [2, 600, 300, 60]]):
            points = []
            for t, relative_y in ((1, -.75), (1.1, -.25), (1.2, .375)):
                x, y, w = rim_at(keys, t)
                points.append(dict(timestamp=t, centerX=x, centerY=y+relative_y*w,
                                   trackId=1, trackState="confirmed"))
            result = diagnose(points, keys, 1280, 720)
            self.assertEqual(len(result), 1)
            self.assertIsNone(result[0]["outcome"])
            for evidence, point in zip(result[0]["evidence"], points):
                self.assertAlmostEqual(evidence["x"], point["centerX"], places=5)
                self.assertAlmostEqual(evidence["y"], point["centerY"], places=5)
            excluded = dict(points[1], timestamp=1.15, shotMotionEligible=False)
            self.assertEqual(diagnose(points+[excluded], keys, 1280, 720), [])

    def test_invalid_calibration_rejected(self):
        for keys in ([[1, 400, 200, 40]],
                     [[1, 400, 200, 40], [1, 410, 200, 40]],
                     [[1, 400, 200, 40], [3, 410, 200, 40]],
                     [[1, 400, 200, 40], [2, 1290, 200, 40]]):
            with self.assertRaises(ValueError):
                validate_keyframes(keys, 1280, 720)


if __name__ == "__main__":
    unittest.main()
