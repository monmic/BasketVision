"""Export changed detections as contextual crops for visual review (requires OpenCV).

Use the original video matching the diagnostic report dimensions. Green boxes
are newly accepted observations; red boxes are observations no longer accepted.
"""
import argparse
import html
import json
from pathlib import Path

import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    summary = json.loads((args.comparison / "summary.json").read_text())
    baseline = json.loads((args.comparison / "baseline.json").read_text())
    changes = json.loads((args.comparison / "differences.json").read_text())
    if summary["sourceVideo"] and args.video.name != summary["sourceVideo"]:
        raise ValueError("Video name does not match the diagnostic report")
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise ValueError("Cannot open video")
    expected = baseline["frames"][0]
    if (round(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))) != (expected["width"], expected["height"]):
        raise ValueError("Video dimensions must match candidate coordinates")
    args.output.mkdir(parents=True, exist_ok=False)
    sheets = []
    tiles = []
    try:
        for index, change in enumerate(changes):
            cap.set(cv2.CAP_PROP_POS_FRAMES, change["frame"])
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f"Cannot read frame {change['frame']}")
            c = change["after"]
            color = (0, 200, 0) if c["accepted"] else (0, 0, 255)
            x, y = round(c["centerX"]), round(c["centerY"])
            half = max(55, round(2 * max(c["width"], c["height"])))
            cv2.rectangle(frame, (round(c["x1"]), round(c["y1"])),
                          (round(c["x2"]), round(c["y2"])), color, 1)
            crop = frame[max(0, y-half):min(frame.shape[0], y+half), max(0, x-half):min(frame.shape[1], x+half)]
            tile = np.zeros((240, 256, 3), dtype=np.uint8)
            scale = min(256/crop.shape[1], 198/crop.shape[0])
            crop = cv2.resize(crop, (round(crop.shape[1]*scale), round(crop.shape[0]*scale)))
            tile[42:42+crop.shape[0], :crop.shape[1]] = crop
            label = f"#{index} {change['timestamp']:.3f}s {'ADD' if c['accepted'] else 'DROP'}"
            cv2.putText(tile, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, .43, (255, 255, 255), 1)
            cv2.putText(tile, f"frame {change['frame']} conf {c['confidence']:.3f}", (4, 34), cv2.FONT_HERSHEY_SIMPLEX, .43, (255, 255, 255), 1)
            tiles.append(tile)
            if len(tiles) == 12 or index == len(changes)-1:
                tiles.extend([np.zeros_like(tile)] * (12-len(tiles)))
                sheet = cv2.vconcat([cv2.hconcat(tiles[i:i+4]) for i in range(0, 12, 4)])
                name = f"changes-{len(sheets):02d}.jpg"
                if not cv2.imwrite(str(args.output / name), sheet):
                    raise OSError("Cannot write review image")
                sheets.append(name)
                tiles = []
    finally:
        cap.release()
    body = '\n'.join(f'<img src="{name}" alt="{name}" style="max-width:100%">' for name in sheets)
    (args.output / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Tracker review</title>'
        f'<h1>{html.escape(args.video.name)}</h1><p>{len(changes)} changed detections. '
        'ADD = newly accepted; DROP = no longer accepted. Numbers refer to differences.json. '
        'These are candidate crops, not confirmed shots.</p>' + body, encoding="utf-8")
    print(f"Exported {len(changes)} changed observations to {args.output}")


if __name__ == "__main__":
    main()
