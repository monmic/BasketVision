"""Apply explicit manual revisions to a NEW annotation file, preserving originals."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from benchmark_ball_model import validate_annotations
from evaluate_ball_clip import box


def revise(original, revision):
    frames = validate_annotations(original)
    if original['source'] != revision['source']:
        raise ValueError('Revision belongs to another video')
    w,h = revision['width'],revision['height']
    if not (isinstance(w,int) and isinstance(h,int) and w>0 and h>0):
        raise ValueError('Invalid source dimensions')
    replacements = {}
    excluded = set()
    for entry in revision['replaceBoxesPixels']:
        index = entry['frame']
        if index not in frames or index in replacements:
            raise ValueError('Unknown or duplicate replacement frame')
        replacements[index] = [box([b[0]/w,b[1]/h,b[2]/w,b[3]/h]) for b in entry['boxes']]
    for entry in revision['excludeFrames']:
        index = entry['frame']
        if index not in frames or index in excluded or index in replacements or not entry['reason']:
            raise ValueError('Unknown, duplicate or conflicting exclusion')
        excluded.add(index)
    result = copy.deepcopy(original)
    result['frames'] = [dict(row, boxes=replacements.get(row['frame'],row['boxes']))
                        for row in result['frames'] if row['frame'] not in excluded]
    validate_annotations(result)
    result['revision'] = revision
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original',type=Path)
    parser.add_argument('revision',type=Path)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    raw = args.original.read_bytes()
    result = revise(json.loads(raw.decode('utf-8-sig')),
                    json.loads(args.revision.read_text(encoding='utf-8-sig')))
    result['originalSha256'] = hashlib.sha256(raw).hexdigest()
    with args.output.open('x',encoding='utf-8') as output:
        json.dump(result,output,indent=2,allow_nan=False)
    print(f"Saved {len(result['frames'])} reviewed frames to {args.output}")


if __name__ == '__main__':
    main()
