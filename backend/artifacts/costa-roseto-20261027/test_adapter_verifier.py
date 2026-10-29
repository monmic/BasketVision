import copy
import unittest
import numpy as np
import torch
from adapter_verifier import AdapterVerifier, BASE, read
from semantic_verifier import Extractor, probabilities
from spatial_verifier import spatial_pool


class AdapterVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.extractor = Extractor('/model.pt')
        cls.classifier = read(BASE/'balanced-verifier/balanced-classifier.json')

    def test_initialization_reproduces_normalized_logistic_scores(self):
        model = AdapterVerifier(self.extractor,self.classifier)
        torch.manual_seed(17)
        images = torch.rand(3,3,128,128)
        with torch.no_grad():
            x = spatial_pool(self.extractor.backbone(images)).numpy()
            actual = model(images).sigmoid().numpy()
        np.testing.assert_allclose(actual,probabilities(x,self.classifier),atol=1e-5,rtol=1e-5)

    def test_backward_step_changes_only_allowed_parameters_no_buffers(self):
        model = AdapterVerifier(self.extractor,self.classifier)
        before = copy.deepcopy(model.state_dict())
        buffers = set(dict(model.named_buffers()))
        optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=1e-5)
        logits = model(torch.rand(2,3,128,128))
        torch.nn.functional.binary_cross_entropy_with_logits(logits,torch.tensor([0.,1.])).backward()
        self.assertTrue(all(p.grad is None for p in model.prefix.parameters()))
        self.assertTrue(any(p.grad is not None for p in model.adapter.parameters()))
        self.assertTrue(all(not m.training for m in model.modules() if isinstance(m,torch.nn.BatchNorm2d)))
        optimizer.step()
        changed = {name for name,value in model.state_dict().items() if not torch.equal(value,before[name])}
        self.assertTrue(changed)
        self.assertFalse(changed & buffers)
        self.assertTrue(all(name.startswith(('adapter.','head.')) for name in changed))

    def test_cached_prefix_matches_full_forward_and_restore(self):
        model = AdapterVerifier(self.extractor,self.classifier)
        image = torch.rand(2,3,128,128)
        state = copy.deepcopy(model.state_dict())
        with torch.no_grad():
            torch.testing.assert_close(model(image),model.from_prefix(model.prefix(image)))
        restored = AdapterVerifier(self.extractor,self.classifier)
        restored.load_state_dict(state)
        with torch.no_grad():
            torch.testing.assert_close(model(image),restored(image))


if __name__ == '__main__':
    unittest.main()
