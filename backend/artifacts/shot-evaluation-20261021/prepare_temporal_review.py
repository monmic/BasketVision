"""Extract dense original frames for visual rim review, without assigning calibration."""
import argparse
import json
import math
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--episodes', type=Path, default=Path(__file__).with_name('episodes.json'))
    parser.add_argument('--output', type=Path, required=True, help='New directory; existing outputs are never overwritten.')
    parser.add_argument('--step', type=float, default=0.1)
    args = parser.parse_args()
    if not math.isfinite(args.step) or args.step <= 0:
        parser.error('--step must be finite and positive')
    if not args.video.is_file():
        parser.error('Video does not exist')
    episodes = json.loads(args.episodes.read_text(encoding='utf-8'))
    import cv2

    cap = cv2.VideoCapture(str(args.video))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not cap.isOpened() or not math.isfinite(fps) or fps <= 0 or count <= 0:
            raise RuntimeError('Cannot read video metadata')
        plans = []
        for episode in episodes:
            start, end = episode['startSeconds'], episode['endSeconds']
            if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end < count / fps):
                raise ValueError(f'Invalid video range for episode {episode["episode"]}')
            times = [start + n * args.step for n in range(math.ceil((end-start)/args.step))]
            times += [end, episode['manualTimestamp']]
            indices = sorted({round(t * fps) for t in times if start <= t <= end})
            plans.append((episode, indices))
        args.output.mkdir(parents=True, exist_ok=False)
        manifest = []
        for episode, indices in plans:
            frames = []
            for index in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError(f'Cannot decode frame {index}; output is incomplete')
                name = f'episode-{episode["episode"]:02d}-frame-{index:06d}.jpg'
                if not cv2.imwrite(str(args.output / name), frame):
                    raise RuntimeError(f'Cannot write {name}; output is incomplete')
                frames.append({'frame': index, 'timestamp': index / fps, 'file': name})
            manifest.append(dict(episode=episode['episode'], manualTimestamp=episode['manualTimestamp'],
                                 fps=fps, frames=frames, calibration=None,
                                 status='awaiting_temporal_rim_review'))
        # A manifest is written only after every requested frame has been decoded.
        with (args.output / 'manifest.json').open('x', encoding='utf-8') as stream:
            json.dump(manifest, stream, indent=2)
        print(f'Extracted {sum(len(e["frames"]) for e in manifest)} frames across {len(manifest)} episodes')
    finally:
        cap.release()


if __name__ == '__main__':
    main()
