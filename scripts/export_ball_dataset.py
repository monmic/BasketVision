"""Export reviewed boxes to a YOLO dataset with whole-episode splits, no inference."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from benchmark_ball_model import validate_annotations
from prepare_shot_ball_review import sample_plan


def assign_frames(annotations, plan, split):
    reviewed = validate_annotations(annotations)
    if len({annotations['source'],plan['source'],split['source']}) != 1:
        raise ValueError('Sources differ')
    groups = sample_plan(plan,annotations['fps'])
    if set(split['splits']) != {'train','val','test'}:
        raise ValueError('Require train, val and test')
    assignments,used = {},set()
    for role,episodes in split['splits'].items():
        for episode in episodes:
            if episode not in groups or episode in used:
                raise ValueError('Unknown or shared episode')
            used.add(episode)
            for frame in groups[episode]:
                if frame in assignments:
                    raise ValueError('Overlapping episode frames')
                assignments[frame] = (role,episode)
    if used != set(groups) or not reviewed <= assignments.keys():
        raise ValueError('Split plan must cover episodes and reviewed frames')
    result = {frame:assignments[frame] for frame in reviewed}
    if {role for role,_ in result.values()} != {'train','val','test'}:
        raise ValueError('Every split needs reviewed frames')
    return result


def yolo_label(b):
    x1,y1,x2,y2 = b
    return f'0 {(x1+x2)/2:.8f} {(y1+y2)/2:.8f} {x2-x1:.8f} {y2-y1:.8f}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('video','annotations','plan','split','output'):
        parser.add_argument(name,type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output directory must be new')
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    a,plan,split = map(read,(args.annotations,args.plan,args.split))
    assignments = assign_frames(a,plan,split)
    if args.video.name != a['source']:
        raise ValueError('Wrong video')
    import cv2
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened() or not math.isclose(cap.get(cv2.CAP_PROP_FPS),a['fps'],rel_tol=1e-6):
        cap.release()
        raise ValueError('Cannot read video or FPS differs')
    truth = {r['frame']:r['boxes'] for r in a['frames']}
    args.output.mkdir(parents=True)
    for role in ('train','val','test'):
        for kind in ('images','labels'):
            (args.output/kind/role).mkdir(parents=True)
    manifest = dict(source=a['source'],fps=a['fps'],split=split,
        annotationsSha256=hashlib.sha256(args.annotations.read_bytes()).hexdigest(),frames=[])
    try:
        for index in range(max(assignments)+1):
            ok,frame = cap.read()
            if not ok:
                raise ValueError(f'Missing frame {index}; output incomplete')
            if index not in assignments:
                continue
            role,episode = assignments[index]
            stem = f'{Path(a["source"]).stem}-{index:06d}'
            image_path = Path('images')/role/(stem+'.png')
            label_path = Path('labels')/role/(stem+'.txt')
            if not cv2.imwrite(str(args.output/image_path),frame):
                raise OSError('Cannot save image')
            labels = [yolo_label(b) for b in truth[index]]
            (args.output/label_path).write_text('\n'.join(labels)+('\n' if labels else ''),encoding='utf-8')
            manifest['frames'].append(dict(frame=index,episode=episode,split=role,
                image=image_path.as_posix(),label=label_path.as_posix(),boxes=len(labels)))
    finally:
        cap.release()
    (args.output/'data.yaml').write_text('path: '+json.dumps(args.output.resolve().as_posix())+
        '\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: ball\n',encoding='utf-8')
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for role in ('train','val','test'):
        rows = [r for r in manifest['frames'] if r['split']==role]
        print(role,len(rows),'frames',sum(r['boxes'] for r in rows),'boxes',flush=True)


if __name__ == '__main__':
    main()
