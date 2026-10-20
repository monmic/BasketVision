import unittest

from benchmark_ball_model import validate_annotations
from evaluate_ball_clip import evaluate


class BallBenchmarkTests(unittest.TestCase):
    def test_rejects_unreviewed_or_duplicate_frames(self):
        for frames in ([], [dict(frame=1, boxes=[])]*2,
                       [dict(frame=True, boxes=[])],
                       [dict(frame=1, boxes=[[0, 0, 0, 1]])]):
            with self.assertRaises(ValueError):
                validate_annotations(dict(frames=frames))

    def test_counts_duplicates_and_reviewed_absence_without_unreviewed_frames(self):
        prediction = dict(x1=10, y1=10, x2=20, y2=20, accepted=False)
        report = dict(sourceVideo="video.mp4", source=dict(fps=30), frames=[
            dict(frame=i, width=100, height=100, candidates=[prediction]*n)
            for i, n in ((0, 2), (1, 1), (2, 5))])
        annotations = dict(source="video.mp4", fps=30, frames=[
            dict(frame=0, boxes=[[.1, .1, .2, .2]]), dict(frame=1, boxes=[])])
        result = evaluate(report, annotations)["metrics"]["raw"]
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (1, 2, 0))
        annotations["frames"].append(dict(frame=3, boxes=[]))
        with self.assertRaises(ValueError):
            evaluate(report, annotations)


if __name__ == "__main__":
    unittest.main()
