"""Export every annotated frame with human boxes (green) and raw detections (red)."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('annotations', type=Path)
    parser.add_argument('report', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    import cv2
    import numpy as np
    from evaluate_ball_clip import evaluate, iou
    a = json.loads(args.annotations.read_text(encoding='utf-8-sig'))
    r = json.loads(args.report.read_text(encoding='utf-8-sig'))
    evaluate(r, a)  # Validate video identity, frame coverage and box geometry.
    if args.video.name != a['source'] or args.output.exists():
        raise ValueError('Require matching video and new output directory')
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise ValueError('Cannot open video')
    rows = {row['frame']:row for row in r['frames']}
    truth = {row['frame']:row['boxes'] for row in a['frames']}
    args.output.mkdir(parents=True)
    tiles, sheets, details = [], [], []
    try:
        for index in range(max(truth)+1):
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f'Missing frame {index}')
            if index not in truth:
                continue
            h,w = frame.shape[:2]
            row = rows[index]
            if (w,h)!=(row['width'],row['height']):
                raise ValueError('Report and video dimensions differ')
            predictions = [[c['x1']/w,c['y1']/h,c['x2']/w,c['y2']/h] for c in row['candidates']]
            details.append(dict(frame=index, boxes=[dict(box=b, bestRawIoU=max((iou(b,p) for p in predictions),default=0)) for b in truth[index]]))
            for boxes,color in ((predictions,(0,0,255)),(truth[index],(0,255,0))):
                for x1,y1,x2,y2 in boxes:
                    cv2.rectangle(frame,(round(x1*w),round(y1*h)),(round(x2*w),round(y2*h)),color,1)
            canvas = np.zeros((h+30,w,3),dtype=np.uint8)
            canvas[30:]=frame
            cv2.putText(canvas,f'frame {index} | {index/a["fps"]:.3f}s | green: annotation red: model',
                        (8,21),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
            tiles.append(canvas)
            if len(tiles)==4 or index==max(truth):
                tiles.extend([np.zeros_like(canvas)]*(4-len(tiles)))
                sheet=cv2.vconcat([cv2.hconcat(tiles[:2]),cv2.hconcat(tiles[2:])])
                name=f'audit-{len(sheets):02d}.jpg'
                if not cv2.imwrite(str(args.output/name),sheet,[cv2.IMWRITE_JPEG_QUALITY,95]):
                    raise OSError('Cannot write image')
                sheets.append(name);tiles=[]
    finally:
        cap.release()
    (args.output/'overlaps.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
    (args.output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Revisione annotazioni</title><h1>Verde: annotazioni; rosso: modello</h1>'+''.join(f'<img src="{s}" style="max-width:100%" alt="{s}">' for s in sheets),encoding='utf-8')
    print(f'Exported {len(details)} frames in {len(sheets)} sheets')


if __name__ == '__main__':
    main()
