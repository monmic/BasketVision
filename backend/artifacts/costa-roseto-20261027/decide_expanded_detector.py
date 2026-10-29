"""Apply the predeclared sample gate; passing never authorizes production release."""
import json
from pathlib import Path

COHORTS=['costa-test','home-away-control','online-control','costa-fresh']


def decide(summary,candidate_name='expanded'):
    reasons=[]
    for confidence in ['0.02','0.12']:
        old_fp=new_fp=0
        for source in COHORTS:
            result=summary[source]['thresholds'][confidence]
            baseline=result['models']['baseline'];candidate=result['models'][candidate_name]
            old_fp+=baseline['fp'];new_fp+=candidate['fp']
            if result['baselineObjectsLost']:
                reasons.append(dict(source=source,confidence=confidence,reason='Previously matched ball objects lost',objects=result['baselineObjectsLost']))
            if candidate['fn']>baseline['fn']:
                reasons.append(dict(source=source,confidence=confidence,reason='More missed ball objects',baseline=baseline['fn'],candidate=candidate['fn']))
            if candidate['fp']>baseline['fp']:
                reasons.append(dict(source=source,confidence=confidence,reason='More false positives',baseline=baseline['fp'],candidate=candidate['fp']))
        if new_fp>=old_fp:
            reasons.append(dict(confidence=confidence,reason='No total false-positive reduction',baseline=old_fp,candidate=new_fp))
    return dict(eligibleForContinuousReplay=not reasons,productionRelease=False,reasons=reasons,
        notice='Frozen sample gate at both preset confidences, without source averaging hiding regressions. Production still requires continuous and independent-source validation.')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preserve-geometry',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent/('detector-preserved/evaluation' if args.preserve_geometry else 'detector-expanded/evaluation')
    report=decide(json.loads((root/'summary.json').read_text()),'preserved' if args.preserve_geometry else 'expanded')
    with (root/'decision.json').open('x') as stream:json.dump(report,stream,indent=2)
    print(json.dumps(report,indent=2))
