import copy
import unittest

from export_ball_dataset import assign_frames, yolo_label


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.plan = dict(source='v.mp4',sampleStepSeconds=1,episodes=[
            dict(id=str(i),start=i*10,end=i*10+1) for i in range(3)])
        self.a = dict(source='v.mp4',fps=30,frames=[
            dict(frame=i*300,boxes=[[.1,.2,.3,.4]]) for i in range(3)])
        self.split = dict(source='v.mp4',splits=dict(train=['0'],val=['1'],test=['2']))

    def test_whole_episodes_and_unreviewed_frames_omitted(self):
        result = assign_frames(self.a,self.plan,self.split)
        self.assertEqual(result,{0:('train','0'),300:('val','1'),600:('test','2')})
        self.assertNotIn(30,result)

    def test_shared_episode_rejected(self):
        self.split['splits']['val'].append('0')
        with self.assertRaises(ValueError):
            assign_frames(self.a,self.plan,self.split)

    def test_overlapping_frames_rejected(self):
        self.plan['episodes'][1].update(start=0,end=1)
        with self.assertRaises(ValueError):
            assign_frames(self.a,self.plan,self.split)

    def test_wrong_source_and_unassigned_frame_rejected(self):
        other = copy.deepcopy(self.a)
        other['source'] = 'wrong.mp4'
        with self.assertRaises(ValueError):
            assign_frames(other,self.plan,self.split)
        self.a['frames'].append(dict(frame=500,boxes=[]))
        with self.assertRaises(ValueError):
            assign_frames(self.a,self.plan,self.split)

    def test_yolo_box_conversion(self):
        self.assertEqual(yolo_label([.1,.2,.3,.4]),'0 0.20000000 0.30000000 0.20000000 0.20000000')


if __name__ == '__main__':
    unittest.main()
