import copy
import unittest

from revise_ball_annotations import revise


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.original = dict(source='video.mp4', fps=30, frames=[
            dict(frame=1, boxes=[[.1,.1,.4,.4]]), dict(frame=2, boxes=[])])
        self.revision = dict(source='video.mp4', width=100, height=100,
            replaceBoxesPixels=[dict(frame=1, boxes=[[12,12,30,30]])],
            excludeFrames=[dict(frame=2, reason='Occluded')])

    def test_preserves_original_and_normalizes_explicit_changes(self):
        before = copy.deepcopy(self.original)
        result = revise(self.original, self.revision)
        self.assertEqual(self.original, before)
        self.assertEqual(result['frames'], [dict(frame=1, boxes=[[.12,.12,.3,.3]])])

    def test_rejects_conflicting_and_unknown_changes(self):
        for index in (1,3):
            self.revision['excludeFrames'] = [dict(frame=index, reason='Ambiguous')]
            with self.assertRaises(ValueError):
                revise(self.original, self.revision)

    def test_rejects_wrong_video_and_out_of_bounds_boxes(self):
        self.revision['source'] = 'other.mp4'
        with self.assertRaises(ValueError):
            revise(self.original, self.revision)
        self.revision['source'] = 'video.mp4'
        self.revision['replaceBoxesPixels'][0]['boxes'] = [[-1,0,30,30]]
        with self.assertRaises(ValueError):
            revise(self.original, self.revision)


if __name__ == '__main__':
    unittest.main()
