"""Verify exported labels, reviewed source images and immutable split provenance."""
import hashlib
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/'scripts'))
from export_ball_dataset import yolo_label
from export_detector_pilot import validate_row
from prepare_detector_frames import SPLITS


def audit():
    root=HERE/'detector-pilot';dataset=root/'dataset'
    annotations=root/'annotations-draft.json'
    all_rows=json.loads(annotations.read_text())['frames']
    manifest_path=dataset/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    assert manifest['annotationsSha256']==hashlib.sha256(annotations.read_bytes()).hexdigest()
    assert len(all_rows)==27 and len(manifest['frames'])==22 and len(manifest['excluded'])==5
    assert all(r['status']=='uncertain' for r in manifest['excluded'])
    assert {r['frame'] for r in manifest['frames']}.isdisjoint(r['frame'] for r in manifest['excluded'])
    for role,times in SPLITS.items():
        assert sorted(r['requestedSeconds'] for r in all_rows if r['split']==role)==times
    for row in manifest['frames']:
        boxes=validate_row(row)
        assert boxes==row['boxes']
        for image in [root/row['file'],dataset/row['image']]:
            assert hashlib.sha256(image.read_bytes()).hexdigest()==row['sha256']
        assert (dataset/row['label']).read_text()==''.join(yolo_label(b)+'\n' for b in boxes)
    for run in ['training','training-stable-warmup']:
        frozen=root/run/'frozen.json'
        if not frozen.exists():continue
        report=json.loads(frozen.read_text())
        assert report['datasetManifestSha256']==hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        assert report['selectedWeightsSha256']==hashlib.sha256((root/run/'weights/best.pt').read_bytes()).hexdigest()
    print('27 selected / 22 exported / 5 excluded; labels, hashes, splits and frozen checkpoints verified.')


if __name__=='__main__':audit()
