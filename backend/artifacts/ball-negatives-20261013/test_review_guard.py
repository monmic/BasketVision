import copy
import unittest
import hashlib
from review_guard import select_reviewed,validate_window,validate_review_binding


class ReviewGuardTests(unittest.TestCase):
    def test_review_binding_rejects_changed_or_missing_provenance(self):
        content=b'original proposals'
        review={'proposalsSha256':hashlib.sha256(content).hexdigest()}
        validate_review_binding(content,review)
        for data,decision in [(b'changed proposals',review),(content,{})]:
            with self.assertRaises(ValueError):
                validate_review_binding(data,decision)

    def setUp(self):
        self.proposals=[dict(id='a',image='train.png'),dict(id='b',image='train2.png')]
        self.review=dict(items=[dict(id='a',candidate='non_ball',crop='verified_negative',reason='Floor'),
                                dict(id='b',candidate='unannotated_ball',crop='excluded',reason='Spare ball')])
        self.images={'train.png','train2.png'}

    def test_only_explicit_negative_review_is_exported(self):
        self.assertEqual(select_reviewed(self.proposals,self.review,self.images),[self.proposals[0]])

    def test_real_ball_cannot_receive_empty_label(self):
        self.review['items'][1]['crop']='verified_negative'
        with self.assertRaises(ValueError):
            select_reviewed(self.proposals,self.review,self.images)

    def test_missing_duplicate_or_pending_review_rejected(self):
        for items in [self.review['items'][:1],self.review['items']*2,
                      [dict(id='a',candidate='non_ball',crop='pending',reason='Not checked'),self.review['items'][1]]]:
            with self.assertRaises(ValueError):
                select_reviewed(self.proposals,dict(items=items),self.images)

    def test_validation_or_test_image_cannot_enter_training_export(self):
        proposals=copy.deepcopy(self.proposals)
        proposals[0]['image']='val.png'
        with self.assertRaises(ValueError):
            select_reviewed(proposals,self.review,self.images)

    def test_known_ball_and_margin_rejected(self):
        for window in [(40,40,60,60),(10,40,30,60)]:
            with self.assertRaises(ValueError):
                validate_window(window,100,100,[[.4,.4,.6,.6]])
        validate_window((0,0,20,20),100,100,[[.4,.4,.6,.6]])

    def test_invalid_windows_rejected(self):
        for window in [(-1,0,20,20),(0,0,120,20),(20,0,10,20),(0.,0,20,20)]:
            with self.assertRaises(ValueError):
                validate_window(window,100,100,[])


if __name__=='__main__':
    unittest.main()
