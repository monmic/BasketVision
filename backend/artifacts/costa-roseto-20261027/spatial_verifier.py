"""Isolated spatial pooling experiment; same frozen backbone and reviewed data."""
import hashlib
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from semantic_verifier import Extractor, crop_tensor, fit, probabilities, metrics

BASE = Path(__file__).resolve().parent


def spatial_pool(features):
    if features.ndim != 4 or min(features.shape[2:]) < 2:
        raise ValueError('Spatial feature maps of at least 2x2 required')
    return torch.nn.functional.adaptive_avg_pool2d(features, (2, 2)).flatten(1)


def features(extractor, images):
    spatial, mean = [], []
    with torch.inference_mode():
        for start in range(0, len(images), 32):
            batch = torch.stack([crop_tensor(im) for im in images[start:start+32]])
            maps = extractor.backbone(batch)
            spatial.append(spatial_pool(maps).numpy())
            mean.append(maps.mean(dim=(2, 3)).numpy())
    return np.concatenate(spatial), np.concatenate(mean)


def crop_bounds(candidate, shape):
    height, width = shape[:2]
    bounds = [max(0, math.floor(candidate['x1'])), max(0, math.floor(candidate['y1'])),
              min(width, math.ceil(candidate['x2'])), min(height, math.ceil(candidate['y2']))]
    if bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
        raise ValueError('Empty candidate crop')
    return bounds


def control_crops(rows, capture):
    images = []
    frames = {}
    for row in rows:
        index = row['frame']
        if index not in frames:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, image = capture.read()
            if not ok:
                raise ValueError(f'Unreadable frame {index}')
            frames[index] = image
        image = frames[index]
        left, top, right, bottom = crop_bounds(row['candidate'], image.shape)
        images.append(image[top:bottom, left:right])
    return images


def main():
    root = BASE / 'spatial-verifier'
    root.mkdir(exist_ok=False)
    read = lambda path: json.loads(path.read_text())
    source = BASE / 'adapted-examples/manifest.json'
    old = read(BASE / 'adapted-training-corrected/classifier.json')
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest(source) == old['trainingManifestSha256']
    rows = read(source)['examples']
    images = []
    for row in rows:
        path = source.parent / row['file']
        assert digest(path) == row['sha256']
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(path)
        images.append(image)
    extractor = Extractor('/model.pt')
    assert extractor.weights_sha256 == old['backboneSha256']
    started = time.perf_counter()
    x, means = features(extractor, images)
    labels = np.asarray([r['label'] == 'active_ball' for r in rows], dtype=np.int64)
    groups = np.asarray([r['episode'] for r in rows])
    folds = []
    for group in sorted(set(groups)):
        mask = groups == group
        model = fit(x[~mask], labels[~mask])
        fold = dict(group=group, examples=int(mask.sum()), metrics=metrics(labels[mask], probabilities(x[mask], model)))
        folds.append(fold)
        print(json.dumps(fold), flush=True)
    classifier = dict(fit(x, labels), threshold=.5, featureProtocol='same backbone, adaptive mean 2x2 flattened channels first',
                      trainingManifestSha256=digest(source), backboneSha256=extractor.weights_sha256, l2=.01)
    path = root / 'classifier.json'
    path.write_text(json.dumps(classifier, allow_nan=False))
    frozen_hash = digest(path)
    training_seconds = time.perf_counter()-started
    # No control observations loaded until the classifier has been serialized.
    controls = dict(proposals=read(BASE / 'adapted-review.json')['observations'],
                    trackIdentities=read(BASE / 'continuous-review/review.json')['observations'])
    capture = cv2.VideoCapture('/video.mp4')
    results = {}
    try:
        for name, observations in controls.items():
            crops = control_crops(observations, capture)
            started = time.perf_counter()
            spatial, pooled = features(extractor, crops)
            scores = probabilities(spatial, classifier)
            old_scores = probabilities(pooled, old)
            elapsed = time.perf_counter()-started
            valid = np.asarray([r.get('label', r.get('visualObject')) in ('ball', 'non_ball') for r in observations])
            truth = np.asarray([r.get('label', r.get('visualObject')) == 'ball' for r in observations], dtype=np.int64)
            result = dict(observations=len(observations), evaluated=int(valid.sum()),
                          original=metrics(truth[valid], old_scores[valid]),
                          spatial=metrics(truth[valid], scores[valid]),
                          sharedFeatureSeconds=elapsed,
                          nativeCropSizes=[list(c.shape[:2]) for c in crops],
                          scores=[dict(index=r['index'], score=float(s), oldScore=float(o)) for r,s,o in zip(observations, scores, old_scores)])
            results[name] = result
            print(json.dumps(dict(control=name, original=result['original'], spatial=result['spatial'])), flush=True)
    finally:
        capture.release()
    assert digest(path) == frozen_hash
    passed = all(r['spatial']['ballRejected'] == 0 and r['spatial']['falseRejected'] > 0 for r in results.values())
    summary = dict(trainingExamples=len(rows), features=x.shape[1], folds=folds,
                   classifierSha256=frozen_hash, trainingSeconds=training_seconds, controls=results,
                   eligibleForContinuousReplay=passed, productionRelease=False,
                   notice='Known overlapping development controls. No exhaustive recall. Timing excludes detector, decoding and whole job.')
    (root / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False))
    print(json.dumps(dict(eligibleForContinuousReplay=passed, trainingSeconds=training_seconds)), flush=True)


if __name__ == '__main__':
    main()
