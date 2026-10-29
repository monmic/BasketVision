import unittest
from prepare_detector_negatives import crop_bounds,excludes_balls


class NegativeMiningTests(unittest.TestCase):
    def test_context_cannot_include_ball_or_its_margin(self):
        balls=[[.5,.5,.6,.6]]
        self.assertFalse(excludes_balls([40,40,80,80],balls,100,100))
        self.assertFalse(excludes_balls([20,20,40,40],balls,100,100))
        self.assertTrue(excludes_balls([0,0,30,30],balls,100,100))

    def test_all_balls_checked_not_only_first(self):
        balls=[[.1,.1,.2,.2],[.8,.8,.9,.9]]
        self.assertFalse(excludes_balls([70,70,100,100],balls,100,100))

    def test_context_is_clipped_at_video_boundary(self):
        bounds=crop_bounds([0,0,10,10],100,80)
        self.assertEqual(bounds,[0,0,69,69])
        self.assertFalse(excludes_balls(bounds,[[0,0,.1,.1]],100,80))

    def test_negative_does_not_imply_parent_frame_has_no_ball(self):
        self.assertTrue(excludes_balls([0,0,100,100],[[.8,.8,.9,.9]],854,480))


if __name__=='__main__':unittest.main()
