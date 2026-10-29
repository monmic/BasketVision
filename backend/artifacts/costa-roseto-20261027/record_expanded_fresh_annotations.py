"""Independent native-frame annotation of the six frozen fresh samples."""
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent/'detector-expanded/fresh'
BOXES={0:[630,238,645,252],1:[508,326,524,343],2:[119,290,136,307],
       4:[237,193,253,208],5:[183,157,198,174]}
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',action='store_true')
    args=parser.parse_args()
    data=json.loads((BASE/'frames.json').read_text())
    for i,row in enumerate(data['frames']):
        row.update(status='visible' if i in BOXES else 'uncertain',pixelBoxes=[BOXES[i]] if i in BOXES else [],review='Pristine full-frame followed by enlarged native context; active ball only.')
        if i not in BOXES:row['reason']='Active ball not distinguishable behind players; excluded, not negative.'
    (BASE/'annotations-draft.json').write_text(json.dumps(data,indent=2))
    if args.freeze:
        data['notice']='Five visible ball frames reviewed before expanded checkpoint selection; one ambiguous frame excluded, not negative.'
        with (BASE/'reviewed.json').open('x') as stream:json.dump(data,stream,indent=2)
