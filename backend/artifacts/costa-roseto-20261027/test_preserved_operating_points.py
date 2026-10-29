import copy
import unittest
from check_preserved_operating_points import choose_thresholds,map_score


def candidate(x,confidence):
    return dict(x1=x,y1=10,x2=x+10,y2=20,confidence=confidence,accepted=True)


def report(candidates):
    return dict(frames=[dict(frame=1,width=100,height=100,candidates=candidates)])


TRUTH=dict(frames=[dict(frame=1,boxes=[[.1,.1,.2,.2]])])


class OperatingPointTests(unittest.TestCase):
    def test_can_remove_lower_ranked_false_box_without_losing_baseline(self):
        reports=dict(a=dict(baseline=report([candidate(10,.6),candidate(50,.4)]),pilot=report([candidate(10,.6),candidate(50,.4)])))
        original=copy.deepcopy(reports)
        choices=choose_thresholds(reports,dict(a=TRUTH),.02)
        self.assertTrue(choices['feasible'])
        self.assertTrue(all(r['fp']==0 and r['tp']==1 for r in choices['feasible']))
        self.assertEqual(reports,original)

    def test_cannot_hide_a_false_box_ranked_above_the_true_ball(self):
        reports=dict(a=dict(baseline=report([candidate(10,.3),candidate(50,.9)]),pilot=report([candidate(10,.3),candidate(50,.9)])))
        choices=choose_thresholds(reports,dict(a=TRUTH),.02)
        self.assertEqual(choices['feasible'],[])
        self.assertEqual(choices['bestRetainingBaseline']['fp'],1)

    def test_global_improvement_cannot_hide_source_regression(self):
        reports=dict(a=dict(baseline=report([candidate(10,.8),candidate(50,.4),candidate(70,.4)]),pilot=report([candidate(10,.8)])),
            b=dict(baseline=report([candidate(10,.8)]),pilot=report([candidate(10,.8),candidate(50,.9)])))
        self.assertEqual(choose_thresholds(reports,dict(a=TRUTH,b=TRUTH),.02)['feasible'],[])

    def test_mapping_is_monotone_and_preserves_selected_knots(self):
        weak,strong=.0928,.4635
        values=[map_score(i/1000,weak,strong) for i in range(1001)]
        self.assertEqual(values,sorted(values))
        for value,expected in [(0,0),(weak,.02),(strong,.12),(1,1)]:
            self.assertAlmostEqual(map_score(value,weak,strong),expected)
        with self.assertRaises(ValueError):map_score(.5,.2,.1)


if __name__=='__main__':unittest.main()
