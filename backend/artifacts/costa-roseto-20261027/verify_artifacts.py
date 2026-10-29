"""Check crop integrity, split boundary and the frozen classifier identity."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
dataset = HERE / 'adapted-examples'
rows = json.loads((dataset / 'manifest.json').read_text())['examples']
assert len(rows) == 409
assert sum(row['episode'] == 'costa-first60' for row in rows) == 80
for row in rows:
    assert hashlib.sha256((dataset / row['file']).read_bytes()).hexdigest() == row['sha256']
    left, top, right, bottom = row['cropBounds']
    assert 0 <= left < right <= 854 and 0 <= top < bottom <= 480
    if row['episode'] == 'costa-first60':
        assert row['timestamp'] < 60
classifier = HERE / 'adapted-training-corrected/classifier.json'
assert hashlib.sha256(classifier.read_bytes()).hexdigest() == '4c0fdcb8d8fbb7190942ef2b5d2e3cdaf83046b8d29e80ec75e97d57178364ff'
assert len(json.loads(classifier.read_text())['trainingSources']) == 2
print('409 crop hashes/bounds and frozen classifier verified.')
