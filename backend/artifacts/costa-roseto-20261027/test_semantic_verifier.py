import json
import unittest

import numpy as np
from semantic_verifier import crop_tensor,fit,probabilities


class SemanticVerifierTests(unittest.TestCase):
    def test_letterbox_preserves_rgb_and_rejects_empty_crops(self):
        image=np.full((10,20,3),[10,20,30],dtype=np.uint8)
        tensor=crop_tensor(image)
        self.assertEqual(tuple(tensor.shape),(3,128,128))
        np.testing.assert_allclose(tensor[:,64,64].numpy(),np.asarray([30,20,10])/255,rtol=1e-6)
        np.testing.assert_allclose(tensor[:,0,0].numpy(),np.full(3,114/255),rtol=1e-6)
        with self.assertRaises(ValueError):crop_tensor(np.empty((0,10,3),dtype=np.uint8))

    def test_frozen_json_predictions_match_and_do_not_mutate_features(self):
        features=np.asarray([[-2,1],[-1,1],[1,1],[2,1]],dtype=np.float64)
        labels=np.asarray([0,0,1,1]);original=features.copy()
        model=fit(features,labels)
        scores=probabilities(features,model)
        self.assertEqual((scores>=.5).tolist(),labels.astype(bool).tolist())
        restored=json.loads(json.dumps(model,allow_nan=False))
        np.testing.assert_allclose(probabilities(features,restored),scores)
        np.testing.assert_array_equal(features,original)
        self.assertTrue(np.isfinite(scores).all())

    def test_training_requires_both_reviewed_classes(self):
        with self.assertRaises(ValueError):fit(np.zeros((3,2)),np.zeros(3))
        with self.assertRaises(ValueError):fit(np.zeros((3,2)),np.asarray([0,1]))
        with self.assertRaises(ValueError):fit(np.asarray([[np.nan],[1.]]),np.asarray([0,1]))
        with self.assertRaises(ValueError):fit(np.zeros((2,2)),np.asarray([0,2]))

    def test_extreme_logits_stay_finite(self):
        model=dict(mean=[0],std=[1],weight=[1000],bias=0)
        scores=probabilities(np.asarray([[-1],[1]]),model)
        self.assertTrue(np.isfinite(scores).all())
        self.assertLess(scores[0],.5);self.assertGreater(scores[1],.5)


if __name__=='__main__':unittest.main()
