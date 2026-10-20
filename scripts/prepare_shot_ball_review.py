"""Build five independent offline annotation pages from an explicit sample plan."""
import argparse
import base64
import html
import json
import math
from pathlib import Path
import re


def sample_plan(plan, fps):
    step = plan['sampleStepSeconds']
    if not math.isfinite(step) or step <= 0 or not math.isfinite(fps) or fps <= 0:
        raise ValueError('Require positive finite sampling step and FPS')
    groups = {}
    for episode in plan['episodes']:
        name, start, end = episode['id'], episode['start'], episode['end']
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', name) or name in groups:
            raise ValueError('Episode IDs must be unique safe filenames')
        if not all(math.isfinite(t) for t in (start, end)) or not 0 <= start < end:
            raise ValueError('Invalid episode interval')
        times = [start+i*step for i in range(math.floor((end-start)/step)+1)]
        groups[name] = sorted({round(t*fps) for t in times} | {round(end*fps)})
    if not groups:
        raise ValueError('No episodes')
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('plan', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new output directory to preserve existing review pages')
    plan = json.loads(args.plan.read_text(encoding='utf-8-sig'))
    if args.video.name != plan['source']:
        raise ValueError('Video does not match sample plan')
    import cv2
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise ValueError('Cannot open video')
    fps = cap.get(cv2.CAP_PROP_FPS)
    groups = sample_plan(plan, fps)
    wanted = set().union(*map(set, groups.values()))
    samples = {}
    try:
        # One sequential pass preserves exact source frame indices across episodes.
        for index in range(max(wanted)+1):
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f'Cannot decode frame {index}')
            if index not in wanted:
                continue
            ok, encoded = cv2.imencode('.png', frame)
            if not ok:
                raise ValueError(f'Cannot encode frame {index}')
            samples[index] = dict(frame=index, timestamp=index/fps,
                image='data:image/png;base64,'+base64.b64encode(encoded).decode())
    finally:
        cap.release()
    template = Path(__file__).with_name('ball_review.html').read_text(encoding='utf-8')
    args.output.mkdir(parents=True)
    links = []
    for episode in plan['episodes']:
        name = episode['id']
        data = dict(source=plan['source'], fps=fps, exportName=f'home-vs-away-{name}.json',
                    samples=[samples[i] for i in groups[name]])
        page = template.replace('/*REVIEW_DATA*/', json.dumps(data).replace('<', '\\u003c'))
        (args.output/f'{name}.html').write_text(page, encoding='utf-8')
        links.append(f'<li><a href="{name}.html">{html.escape(episode["label"])}</a> '
                     f'— {len(groups[name])} fotogrammi ({episode["start"]}–{episode["end"]} s)</li>')
    index = ('<!doctype html><html lang="it"><meta charset="utf-8">'
             '<title>Home vs Away — annotazione palla</title>'
             '<style>body{font:18px system-ui;max-width:850px;margin:40px auto;padding:16px}li{margin:18px 0}</style>'
             '<h1>'+html.escape(plan.get('title','Revisione palla'))+'</h1><p>Apri un episodio e disegna rettangoli '
             'stretti attorno a tutte le palle visibili. Conferma ogni frame. Se la palla '
             'è coperta o la posizione è ambigua, usa Escludi frame; Nessuna palla è '
             'riservato ai frame di cui hai verificato l’assenza.</p><ul>'+''.join(links)+
             '</ul><p>Scarica il JSON prima di chiudere ciascuna pagina: otterrai cinque '
             'file con nomi distinti. I frame non confermati non entrano nella valutazione. '
             'Queste pagine funzionano senza server e non modificano l’analisi partita.</p></html>')
    (args.output/'index.html').write_text(index, encoding='utf-8')
    (args.output/'sample-plan.json').write_text(json.dumps(dict(plan=plan, fps=fps, frames=groups), indent=2), encoding='utf-8')
    print(f'Created {len(groups)} pages, {len(samples)} frames: {args.output}/index.html', flush=True)


if __name__ == '__main__':
    main()
