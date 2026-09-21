"""Synthetic camera-transform checks; run with the worker's OpenCV dependencies."""
import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vision"))
from camera_motion import CameraMotion


class CameraMotionTests(unittest.TestCase):
    def texture(self, width=854, height=480):
        random = np.random.default_rng(27)
        return random.integers(0, 256, (height, width, 3), dtype=np.uint8)

    def test_known_translation_in_original_pixels(self):
        frame = self.texture()
        shifted = cv2.warpAffine(frame, np.float32([[1, 0, 6], [0, 1, -3]]), (854, 480))
        motion = CameraMotion()
        self.assertIsNone(motion.update(frame, 0))
        result = motion.update(shifted, .04)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["matrix"][0][2], 6, delta=.5)
        self.assertAlmostEqual(result["matrix"][1][2], -3, delta=.5)

    def test_blank_frame_has_no_camera_evidence(self):
        frame = np.zeros((480, 854, 3), dtype=np.uint8)
        motion = CameraMotion()
        motion.update(frame, 0)
        self.assertIsNone(motion.update(frame, .04))

    def test_local_texture_cannot_define_camera_motion(self):
        frame = np.zeros((480, 854, 3), dtype=np.uint8)
        frame[150:270, 300:450] = self.texture(150, 120)
        motion = CameraMotion()
        motion.update(frame, 0)
        self.assertIsNone(motion.update(frame, .04))

    def test_resume_gap_and_resolution_change_reset_evidence(self):
        motion = CameraMotion()
        frame = self.texture()
        motion.update(frame, 0)
        self.assertIsNone(motion.update(frame, 1))
        self.assertIsNone(motion.update(self.texture(320, 240), 1.04))


if __name__ == "__main__":
    unittest.main()
