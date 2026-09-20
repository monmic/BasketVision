"""Export exact decoded frames and a standalone, offline annotation page."""
import argparse
import base64
import json
from pathlib import Path

import cv2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--seconds', type=float, nargs='+',
                        default=list(range(20)) + [2.866667, 10.166667])
    args = parser.parse_args()
    cap = cv2.VideoCapture(str(args.video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or fps <= 0:
        raise ValueError('Cannot read video/FPS')
    if any(t < 0 for t in args.seconds):
        raise ValueError('Timestamps must be nonnegative')
    wanted = {round(t * fps) for t in args.seconds}
    samples = []
    # Sequential decoding keeps indices aligned with diagnostic reports.
    for index in range(max(wanted) + 1):
        ok, frame = cap.read()
        if not ok:
            break
        if index not in wanted:
            continue
        ok, encoded = cv2.imencode('.png', frame)
        if not ok:
            raise ValueError(f'Cannot encode frame {index}')
        samples.append(dict(frame=index, timestamp=index/fps,
                            image='data:image/png;base64,' + base64.b64encode(encoded).decode()))
    cap.release()
    if len(samples) != len(wanted):
        raise ValueError('Some requested timestamps are outside the video')
    data = dict(source=args.video.name, fps=fps, samples=samples)
    template = Path(__file__).with_name('ball_review.html').read_text(encoding='utf-8')
    html = template.replace('/*REVIEW_DATA*/', json.dumps(data).replace('<', '\\u003c'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding='utf-8')
    print(f'Created {args.output}: {len(samples)} frames. Open locally in a browser.')


if __name__ == '__main__':
    main()
