"""Evaluate offline diagnostic reports against reviewed normalized ball boxes.

Only explicitly annotated frames are scored. Empty boxes mean reviewed absence;
unreviewed frames must be omitted. Uses source frame indices, never nearest time.
"""
import argparse
import json
import math
from pathlib import Path


def box(value):
    if len(value) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in value):
        raise ValueError('Boxes require four finite normalized coordinates')
    x1, y1, x2, y2 = value
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        raise ValueError(f'Invalid normalized box: {value}')
    return value


def iou(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    return intersection / ((a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection)


def matches(predictions, truth, threshold):
    # Maximum one-to-one matching: duplicate predictions count as false positives.
    assigned = {}
    def visit(p, seen):
        for t in sorted(range(len(truth)), key=lambda t: iou(predictions[p], truth[t]), reverse=True):
            if t in seen or iou(predictions[p], truth[t]) < threshold:
                continue
            seen.add(t)
            if t not in assigned or visit(assigned[t], seen):
                assigned[t] = p
                return True
        return False
    return sum(visit(p, set()) for p in range(len(predictions)))


def evaluate(report, annotations, threshold=0.5):
    if not 0 < threshold <= 1:
        raise ValueError('IoU must be in (0, 1]')
    if report.get('sourceVideo') and annotations.get('source') != report['sourceVideo']:
        raise ValueError('Annotations and report reference different videos')
    if 'fps' in annotations and not math.isclose(annotations['fps'], report['source']['fps'], rel_tol=1e-6):
        raise ValueError('Annotations and report have different FPS')
    truth = {}
    for row in annotations['frames']:
        index = row['frame']
        if not isinstance(index, int) or index < 0 or index in truth:
            raise ValueError('Annotation frame indices must be unique nonnegative integers')
        truth[index] = [box(b) for b in row['boxes']]
    if not truth:
        raise ValueError('No reviewed frames: annotate before evaluating')
    rows = {r['frame']: r for r in report['frames']}
    missing = sorted(set(truth)-set(rows))
    if missing:
        raise ValueError(f'Annotated frames were not processed: {missing}. Use a common sample or stride 1.')
    result = {'reviewedFrames': len(truth), 'iouThreshold': threshold,
              'elapsedSeconds': report.get('elapsedSeconds'), 'stagesSeconds': report.get('stagesSeconds'),
              'settings': report.get('settings'), 'metrics': {}}
    for mode in ('raw', 'accepted'):
        tp = fp = fn = 0
        errors = []
        for index, targets in sorted(truth.items()):
            row = rows[index]
            width, height = row['width'], row['height']
            if width <= 0 or height <= 0:
                raise ValueError('Invalid frame dimensions')
            predictions = [[c['x1']/width, c['y1']/height, c['x2']/width, c['y2']/height]
                           for c in row['candidates'] if mode == 'raw' or c['accepted']]
            if not all(math.isfinite(v) for p in predictions for v in p):
                raise ValueError('Non-finite prediction')
            hits = matches(predictions, targets, threshold)
            extra, missed = len(predictions)-hits, len(targets)-hits
            tp += hits
            fp += extra
            fn += missed
            if extra or missed:
                errors.append({'frame': index, 'falsePositives': extra, 'falseNegatives': missed})
        result['metrics'][mode] = dict(tp=tp, fp=fp, fn=fn,
            precision=tp/(tp+fp) if tp+fp else None,
            recall=tp/(tp+fn) if tp+fn else None, errors=errors)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('annotations', type=Path)
    parser.add_argument('reports', type=Path, nargs='+')
    parser.add_argument('--iou', type=float, default=0.5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    annotations = json.loads(args.annotations.read_text(encoding='utf-8'))
    results = []
    for path in args.reports:
        report = json.loads(path.read_text(encoding='utf-8'))
        results.append({'report': str(path), **evaluate(report, annotations, args.iou)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
