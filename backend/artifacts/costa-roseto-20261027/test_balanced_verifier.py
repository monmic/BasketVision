import unittest
import numpy as np
from semantic_verifier import fit, probabilities
from balanced_verifier import VIDEOS, balanced_weights, fit_weighted, reduce_rows, partition, gate


class BalancedVerifierTests(unittest.TestCase):
    def test_source_class_mass_is_equal_despite_imbalance(self):
        rows = [dict(sourceVideo=s,label=y) for s,y,n in [('a',0,20),('a',1,2),('b',0,3),('b',1,1)] for _ in range(n)]
        weights = balanced_weights(rows)
        for s in ['a','b']:
            for y in [0,1]:
                self.assertAlmostEqual(sum(w for r,w in zip(rows,weights) if (r['sourceVideo'],r['label']) == (s,y)),.25)
        with self.assertRaises(ValueError):
            balanced_weights(rows[:-1])

    def test_uniform_weights_reproduce_reference_fit(self):
        x = np.asarray([[-2,1],[-1,1],[1,1],[2,1]],dtype=np.float64)
        y = np.asarray([0,0,1,1])
        np.testing.assert_allclose(probabilities(x,fit(x,y)), probabilities(x,fit_weighted(x,y,np.ones(4))),atol=1e-9)

    def test_repetitions_keep_annotated_and_preserve_different_objects(self):
        original = dict(index=0,sourceVideo='a',label=1,timestamp=20.1,bounds=[10,10,20,20],provenance='verified-proposal')
        annotated = dict(original,index=1,timestamp=20.2,provenance='new-ground-truth')
        other = dict(original,index=2,bounds=[100,10,110,20])
        self.assertEqual([r['index'] for r in reduce_rows([original,annotated,other])],[1,2])

    def test_sequence_boundaries_and_guard(self):
        for second,expected in [(41.9,'train'),(42,'guard'),(43.9,'guard'),(44,'validation'),(59.9,'validation')]:
            self.assertEqual(partition(dict(sourceVideo=VIDEOS['costa'],timestamp=second)),expected)
        for second,expected in [(499.9,'train'),(500,'validation'),(559.9,'validation'),(560,'train')]:
            self.assertEqual(partition(dict(sourceVideo=VIDEOS['home'],timestamp=second)),expected)
        with self.assertRaises(ValueError):
            partition(dict(sourceVideo=VIDEOS['costa'],timestamp=60))

    def test_gate_rejects_control_loss_and_validation_regression(self):
        good = dict(ballRejected=0,falseKept=1,falseRejected=5)
        p = dict(reference=good.copy(),balanced=good.copy())
        self.assertTrue(gate([p]))
        self.assertFalse(gate([]))
        self.assertFalse(gate([dict(p,balanced=dict(good,ballRejected=1))]))
        self.assertFalse(gate([p,dict(p,kind='validation',balanced=dict(good,falseKept=2))]))


if __name__ == '__main__':
    unittest.main()
