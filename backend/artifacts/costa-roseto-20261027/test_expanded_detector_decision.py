import unittest
from decide_expanded_detector import COHORTS,decide


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.summary={s:dict(thresholds={c:dict(models=dict(baseline=dict(tp=1,fp=2,fn=1),expanded=dict(tp=2,fp=1,fn=0)),baselineObjectsLost=[])
            for c in ['0.02','0.12']}) for s in COHORTS}

    def test_sample_pass_does_not_release_model(self):
        result=decide(self.summary)
        self.assertTrue(result['eligibleForContinuousReplay'])
        self.assertFalse(result['productionRelease'])

    def test_source_regression_cannot_hide_in_global_improvement(self):
        self.summary['costa-test']['thresholds']['0.02']['models']['expanded']['fp']=3
        self.assertFalse(decide(self.summary)['eligibleForContinuousReplay'])

    def test_equal_totals_cannot_hide_lost_object_identity(self):
        self.summary['online-control']['thresholds']['0.12']['baselineObjectsLost']=[dict(frame=45,truthBox=0)]
        self.assertFalse(decide(self.summary)['eligibleForContinuousReplay'])

    def test_incomplete_control_is_not_a_pass(self):
        del self.summary['costa-fresh']
        with self.assertRaises(KeyError):decide(self.summary)


if __name__=='__main__':unittest.main()
