"""Paired detail/context classification on existing, verified training data."""
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np

from semantic_verifier import Extractor, fit, probabilities, metrics
from spatial_verifier import features, crop_bounds

BASE = Path(__file__).resolve().parent
VIDEOS = dict(costa='ad0b3783-9ef0-49b9-8645-a8fac9540389-020ad1c9868d47e48fe7193d831fc33f.mp4',
              home='35b68704-541f-4c6d-b8ab-45228266102a.mp4')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context_bounds(bounds, shape):
    left, top, right, bottom = bounds
    height, width = shape[:2]
    if not 0 <= left < right <= width or not 0 <= top < bottom <= height:
        raise ValueError('Invalid native crop bounds')
    dx, dy = right-left, bottom-top
    return [max(0, left-dx), max(0, top-dy), min(width, right+dx), min(height, bottom+dy)]


def views(image, bounds):
    left, top, right, bottom = bounds
    context = context_bounds(bounds, image.shape)
    x1, y1, x2, y2 = context
    return image[top:bottom, left:right], image[y1:y2, x1:x2], context


def eligible(controls, folds):
    def no_regression(pair):
        a, b = pair['detail'], pair['context']
        return b['ballRejected'] <= a['ballRejected'] and b['falseKept'] <= a['falseKept']
    return (bool(controls) and bool(folds)
            and all(c['context']['ballRejected'] == 0 and c['context']['falseRejected'] > 0
                and no_regression(c) for c in controls.values())
            and all(no_regression(f) for f in folds))


def extract_pair(extractor, detail, context):
    a = features(extractor, detail)[0]
    b = features(extractor, context)[0]
    return dict(detail=a, context=np.concatenate([a, b], axis=1))


def export_training(root):
    manifest_path = BASE / 'adapted-examples/manifest.json'
    original = read(manifest_path)['examples']
    assert sha(manifest_path) == read(BASE / 'adapted-training-corrected/classifier.json')['trainingManifestSha256']
    dataset_path = BASE / 'detector-expanded/dataset/manifest.json'
    full_rows = read(dataset_path)['frames']
    rows, detail, context, identities = [], [], [], set()
    out = root / 'crops'
    out.mkdir()
    captures = {name: cv2.VideoCapture('/videos/'+name) for name in VIDEOS.values()}
    cached = {}
    def append(image, bounds, source, frame, label, provenance):
        identity = (source, frame, *bounds)
        if identity in identities:
            existing = next(r for r in rows if (r['sourceVideo'], r['frame'], *r['bounds']) == identity)
            if existing['label'] != label:
                raise ValueError('Conflicting duplicate labels')
            return
        identities.add(identity)
        tight, broad, expanded = views(image, bounds)
        record = dict(index=len(rows), sourceVideo=source, frame=frame, bounds=bounds,
                      contextBounds=expanded, label=label, provenance=provenance)
        for name, im in [('detail', tight), ('context', broad)]:
            path = out / f'{len(rows):04d}-{name}.png'
            if not cv2.imwrite(str(path), im):
                raise ValueError(path)
            record[name+'File'] = path.relative_to(root).as_posix()
            record[name+'Sha256'] = sha(path)
        rows.append(record)
        detail.append(tight)
        context.append(broad)
    try:
        for row in original:
            assert row['label'] in {'active_ball', 'shoe', 'non_ball', 'background', 'player_head'}
            path = manifest_path.parent / row['file']
            assert sha(path) == row['sha256']
            source, index = row['sourceVideo'], row['frame']
            if source == VIDEOS['costa']:
                assert row['timestamp'] < 60
            key = source, index
            if key not in cached:
                cap = captures[source]
                cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                ok, image = cap.read()
                if not ok:
                    raise ValueError(key)
                cached[key] = image
            image = cached[key]
            tight = views(image, row['cropBounds'])[0]
            if not np.array_equal(tight, cv2.imread(str(path))):
                raise ValueError(f'Native pixel mismatch: {path}')
            append(image, row['cropBounds'], source, index, int(row['label'] == 'active_ball'), 'verified-proposal')
        added = 0
        for row in full_rows:
            if row['kind'] != 'full-frame' or row['split'] != 'train':
                continue
            path = dataset_path.parent / row['image']
            assert sha(path) == row['sha256']
            image = cv2.imread(str(path))
            source = VIDEOS['costa' if row['source'] == 'costa' else 'home']
            if source == VIDEOS['costa']:
                assert row['frame'] < 1798
            height, width = image.shape[:2]
            for box in row['boxes']:
                candidate = dict(zip(['x1', 'y1', 'x2', 'y2'], [box[0]*width, box[1]*height, box[2]*width, box[3]*height]))
                append(image, crop_bounds(candidate, image.shape), source, row['frame'], 1, 'train-ground-truth')
                added += 1
        assert added == 49
    finally:
        for cap in captures.values():
            cap.release()
    manifest = dict(examples=rows, originalManifestSha256=sha(manifest_path),
                    expandedManifestSha256=sha(dataset_path), extraPositiveBoxes=added,
                    videoSha256={name: sha(Path('/videos')/name) for name in VIDEOS.values()})
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    return rows, detail, context


def control_views(rows, capture):
    detail, context, cached = [], [], {}
    for row in rows:
        index = row['frame']
        if index not in cached:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, image = capture.read()
            if not ok:
                raise ValueError(index)
            cached[index] = image
        image = cached[index]
        tight, broad, _ = views(image, crop_bounds(row['candidate'], image.shape))
        detail.append(tight)
        context.append(broad)
    return detail, context


def main():
    root = BASE / 'context-verifier'
    root.mkdir(exist_ok=False)
    rows, detail, context = export_training(root)
    extractor = Extractor('/model.pt')
    assert extractor.weights_sha256 == read(BASE / 'adapted-training-corrected/classifier.json')['backboneSha256']
    started = time.perf_counter()
    x = extract_pair(extractor, detail, context)
    y = np.asarray([r['label'] for r in rows], dtype=np.int64)
    groups = np.asarray([r['sourceVideo'] for r in rows])
    folds = []
    for group in sorted(set(groups)):
        heldout = groups == group
        fold = dict(heldOutVideo=group, trainExamples=int((~heldout).sum()), testExamples=int(heldout.sum()))
        for name in x:
            model = fit(x[name][~heldout], y[~heldout])
            fold[name] = metrics(y[heldout], probabilities(x[name][heldout], model))
        folds.append(fold)
        print(json.dumps(fold), flush=True)
    models, hashes = {}, {}
    for name in x:
        model = dict(fit(x[name], y), threshold=.5, l2=.01, backboneSha256=extractor.weights_sha256,
                     manifestSha256=sha(root/'manifest.json'), featureDimensions=x[name].shape[1])
        path = root / (name+'-classifier.json')
        path.write_text(json.dumps(model, allow_nan=False))
        hashes[name] = sha(path)
        models[name] = model
    seconds = time.perf_counter()-started
    print(json.dumps(dict(trainingExamples=len(rows), trainingSeconds=seconds)), flush=True)
    # Both final models frozen before any control is read.
    paths = dict(proposals=BASE/'adapted-review.json', trackIdentities=BASE/'continuous-review/review.json')
    controls = {}
    capture = cv2.VideoCapture('/videos/'+VIDEOS['costa'])
    try:
        for name, path in paths.items():
            observations = read(path)['observations']
            a, b = control_views(observations, capture)
            started = time.perf_counter()
            inputs = extract_pair(extractor, a, b)
            labels = [r.get('label', r.get('visualObject')) for r in observations]
            valid = np.asarray([label in ('ball', 'non_ball') for label in labels])
            truth = np.asarray([label == 'ball' for label in labels], dtype=np.int64)
            pair = dict(labelSha256=sha(path), observations=len(observations), predictions={})
            for mode in models:
                scores = probabilities(inputs[mode], models[mode])
                pair[mode] = metrics(truth[valid], scores[valid])
                pair['predictions'][mode] = [dict(index=r['index'], score=float(s)) for r,s in zip(observations, scores)]
            pair['sharedFeatureSeconds'] = time.perf_counter()-started
            controls[name] = pair
            print(json.dumps(dict(control=name, detail=pair['detail'], context=pair['context'])), flush=True)
    finally:
        capture.release()
    assert all(sha(root/(name+'-classifier.json')) == hashes[name] for name in models)
    summary = dict(trainingExamples=len(rows), trainingSeconds=seconds, folds=folds, classifierSha256=hashes,
                   controls=controls, eligibleForContinuousReplay=eligible(controls, folds), productionRelease=False)
    (root/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False))
    print(json.dumps(dict(eligibleForContinuousReplay=summary['eligibleForContinuousReplay'])), flush=True)


if __name__ == '__main__':
    main()
