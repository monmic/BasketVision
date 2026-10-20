"""Measure the last epoch on development splits only; never select on test."""
import json
from run_experiment import OUT, score, save
import torch

torch.set_num_threads(2)
report = json.loads((OUT / 'comparison.json').read_text())
report['lastDevelopment'] = score(OUT / 'train/weights/last.pt', OUT / 'dataset',
                                  ['train', 'val'], 'last-development')
save('comparison.json', report)
