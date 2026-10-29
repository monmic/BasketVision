"""Tracker contracts for optional semantic evidence, without ML or database."""
import copy
import sys
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/'scripts'))
from replay_ball_tracker import load_tracker,WORKER

prototype=HERE/'worker-semantic-prototype.py'


def detection(x=100,semantic=None):
    row=dict(centerX=x,centerY=100,width=10,height=10,qualityScore=.9,confidence=.9)
    if semantic is not None:row['semanticBall']=semantic
    return row


class SemanticGateTests(unittest.TestCase):
    def tracker(self,path=prototype):return load_tracker(worker=path)['BallTracker']()

    def test_negative_semantics_cannot_start_a_track(self):
        tracker=self.tracker()
        for i in range(10):
            result=tracker.update([detection(100+i,False)],i/30)[0]
            self.assertFalse(result['accepted']);self.assertNotIn('trackId',result)

    def test_negative_semantics_may_update_confirmed_track(self):
        tracker=self.tracker()
        for i in range(3):result=tracker.update([detection(100+i,True)],i/30)[0]
        self.assertTrue(result['accepted']);tid=result['trackId']
        result=tracker.update([detection(103,False)],.1)[0]
        self.assertTrue(result['accepted']);self.assertEqual(result['trackId'],tid)
        self.assertEqual(result['associationType'],'weak-track-update')

    def test_negative_semantics_cannot_supply_confirmation(self):
        tracker=self.tracker();tracker.update([detection(100,True)],0)
        for i in range(1,5):
            result=tracker.update([detection(100+i,False)],i/30)[0]
            self.assertFalse(result['accepted'])
        self.assertEqual(tracker.confirmed_count(),0)

    def test_absent_semantics_preserves_existing_behavior(self):
        old,new=self.tracker(WORKER),self.tracker()
        for i in range(40):
            values=[] if i in (8,9,10) else [detection(100+i)]
            self.assertEqual(old.update(copy.deepcopy(values),i/30),new.update(copy.deepcopy(values),i/30))

    def test_checkpoint_preserves_semantic_weak_hit_state(self):
        tracker=self.tracker()
        for i in range(3):tracker.update([detection(100+i,True)],i/30)
        tracker.update([detection(103,False)],.1)
        restored=self.tracker();restored.restore(tracker.snapshot())
        expected=tracker.update([detection(104,False)],4/30)[0]
        actual=restored.update([detection(104,False)],4/30)[0]
        self.assertEqual(expected,actual)


if __name__=='__main__':unittest.main()
