"""Human full-frame ball annotations for the preselected detector pilot."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Pixel xyxy boxes, reviewed independently of detector predictions.
BOXES = {
    4: [334,196,347,209],
    5: [341,329,360,345], 6: [558,168,573,183],
    8: [270,182,286,199], 9: [570,187,584,201],
    11: [518,174,533,188],
    13: [190,323,205,338], 14: [588,287,604,304],
    15: [559,297,574,312], 16: [643,102,658,117],
    17: [724,242,738,256], 18: [288,84,301,99],
    19: [157,392,176,405],
    21: [376,301,396,320], 22: [380,168,397,184],
    24: [676,218,692,234], 26: [158,279,175,294],
}
NEGATIVE = {0,1,2,23,25}
UNCERTAIN = {3,7,10,12,20}

if __name__ == '__main__':
    data = json.loads((HERE/'detector-pilot/frames.json').read_text())
    for i, row in enumerate(data['frames']):
        row.update(status='visible' if i in BOXES else 'uncertain' if i in UNCERTAIN else 'absent',
                   pixelBoxes=[BOXES[i]] if i in BOXES else [])
        assert i in BOXES or i in NEGATIVE or i in UNCERTAIN
        if i in UNCERTAIN:
            row['reason']='Ball occluded or not distinguishable from hands/head in native frame; excluded, not negative.'
        row['review']='Full pristine frame then enlarged native context; single active court ball, rack/stored balls excluded.'
    (HERE/'detector-pilot/annotations-draft.json').write_text(json.dumps(data,indent=2))
