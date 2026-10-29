import copy
import unittest
from benchmark_detector_pilot import score,regressions


class PilotEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.truth=dict(frames=[dict(frame=5,boxes=[[.1,.1,.2,.2]]),dict(frame=6,boxes=[])])
        c=dict(x1=10,y1=10,x2=20,y2=20,confidence=.05,accepted=True)
        self.report=dict(frames=[dict(frame=i,width=100,height=100,candidates=[copy.deepcopy(c)]) for i in [5,6]])

    def test_confidence_filter_preserves_inputs_and_counts_negative(self):
        original=copy.deepcopy(self.report)
        metrics=score(self.report,self.truth,.02)
        self.assertEqual((metrics['tp'],metrics['fp'],metrics['fn']),(1,1,0))
        metrics=score(self.report,self.truth,.12)
        self.assertEqual((metrics['tp'],metrics['fp'],metrics['fn']),(0,0,1))
        self.assertEqual(self.report,original)

    def test_duplicate_predictions_are_not_multiple_hits(self):
        self.report['frames'][0]['candidates']*=2
        metrics=score(self.report,self.truth,.02)
        self.assertEqual((metrics['tp'],metrics['fp'],metrics['fn']),(1,2,0))

    def test_lost_baseline_object_is_reported_at_same_frame(self):
        pilot=copy.deepcopy(self.report)
        pilot['frames'][0]['candidates']=[]
        self.assertEqual(regressions(dict(baseline=self.report,pilot=pilot),self.truth,.02),[dict(frame=5,truthBox=0)])
        self.assertEqual(regressions(dict(baseline=self.report,pilot=pilot),self.truth,.12),[])


if __name__=='__main__':unittest.main()
