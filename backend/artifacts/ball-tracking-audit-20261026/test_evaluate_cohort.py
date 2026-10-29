import unittest
from evaluate_cohort import evaluate


def candidate(x=1,accepted=True):
    return dict(x1=x,y1=1,x2=x+5,y2=6,accepted=accepted)


class CohortTests(unittest.TestCase):
    def test_fewer_detections_can_lose_a_real_ball(self):
        labels=dict(observations=[dict(frame=0,candidate=candidate(),review='visible_active_ball'),
                                  dict(frame=0,candidate=candidate(10),review='shoe')])
        report=dict(frames=[dict(frame=0,candidates=[candidate(accepted=False),candidate(10,False)])])
        result=evaluate(report,labels)
        self.assertEqual(result['reviewedCounts'],dict(visible_active_ball_rejected=1,shoe_rejected=1))

    def test_new_acceptance_is_not_an_automatic_true_positive(self):
        labels=dict(observations=[dict(frame=0,candidate=candidate(),review='visible_active_ball')])
        report=dict(frames=[dict(frame=0,candidates=[candidate(),candidate(20)])])
        result=evaluate(report,labels)
        self.assertEqual(len(result['newlyAcceptedUnreviewed']),1)
        self.assertEqual(result['reviewedCounts'],dict(visible_active_ball_accepted=1))

    def test_uncertain_observation_stays_separate_and_missing_coverage_fails(self):
        labels=dict(observations=[dict(frame=0,candidate=candidate(),review='uncertain_tiny_candidate')])
        result=evaluate(dict(frames=[dict(frame=0,candidates=[candidate(accepted=False)])]),labels)
        self.assertEqual(result['reviewedCounts'],dict(uncertain_tiny_candidate_rejected=1))
        with self.assertRaises(ValueError):
            evaluate(dict(frames=[]),labels)


if __name__=='__main__':
    unittest.main()
