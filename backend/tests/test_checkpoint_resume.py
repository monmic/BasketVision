"""Actual worker helper compiled without importing YOLO or connecting to DB."""
import ast
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[2]/'vision/worker.py'
tree = ast.parse(source.read_text(encoding='utf-8-sig'))
nodes = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name == 'checkpoint_resume_frame']
assert len(nodes) == 1
namespace = {}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),namespace)
resume = namespace['checkpoint_resume_frame']


class CheckpointResumeTests(unittest.TestCase):
    def test_fresh_analysis_starts_at_first_requested_frame(self):
        self.assertEqual(resume({},15,15),15)

    def test_new_checkpoint_index_is_authoritative(self):
        self.assertEqual(resume(dict(nextFrameIndex=46,resumeTimestamp=3),15,15),46)

    def test_legacy_timestamp_excludes_already_processed_frame(self):
        self.assertEqual(resume(dict(resumeTimestamp=3),15,15),46)
        self.assertEqual(resume(dict(resumeTimestamp=0),0,15),1)

    def test_fractional_fps_and_range_clamp(self):
        fps = 29.970027463942692
        self.assertEqual(resume(dict(resumeTimestamp=2338/fps),1798,fps),2339)
        self.assertEqual(resume(dict(nextFrameIndex=1),1798,fps),1798)

    def test_no_frames_recounted_over_multiple_pause_resume_cycles(self):
        visited = []
        next_frame = resume({},15,15)
        for last in [30,52,104]:
            visited.extend(range(next_frame,last+1))
            next_frame = resume(dict(nextFrameIndex=last+1,resumeTimestamp=last/15),15,15)
        self.assertEqual(visited,list(range(15,105)))
        self.assertEqual(len(visited),90)


if __name__ == '__main__':
    unittest.main()
