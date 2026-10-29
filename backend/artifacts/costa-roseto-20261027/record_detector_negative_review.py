"""Record whole-crop visual review; model scores are not negative labels."""
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent/'detector-expanded/negative-review'
data=json.loads((BASE/'manifest.json').read_text())
assert len(data['crops'])==24
for row in data['crops']:
    row['status']='uncertain' if row['index']==20 else 'verified-negative'
    row['review']='Whole native crop inspected for active/stored balls; padded annotated-ball exclusion checked independently.'
    if row['index']==20:
        row['reason']='Small object around background staff hands not unambiguous; excluded conservatively.'
with (BASE/'reviewed.json').open('x') as stream:json.dump(data,stream,indent=2)
print('23 visually verified negative game crops; 1 uncertain excluded.')
