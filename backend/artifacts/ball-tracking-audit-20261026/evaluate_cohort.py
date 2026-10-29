"""Evaluate reviewed accepted-box cohorts without pretending to measure video recall."""
from collections import Counter


def key(frame,candidate):
    return (frame,)+(tuple(round(candidate[k],1) for k in ('x1','y1','x2','y2')))


def evaluate(report,reviewed):
    observations={}
    for row in report['frames']:
        for candidate in row['candidates']:
            identity=key(row['frame'],candidate)
            if identity in observations:
                raise ValueError('Ambiguous duplicate candidate geometry')
            observations[identity]=candidate
    counts=Counter()
    labeled=set()
    for row in reviewed['observations']:
        identity=key(row['frame'],row['candidate'])
        if identity not in observations or identity in labeled:
            raise ValueError('Missing or duplicate reviewed observation')
        labeled.add(identity)
        candidate=observations[identity]
        counts[row['review']+('_accepted' if candidate['accepted'] else '_rejected')]+=1
    newly=[dict(frame=identity[0],candidate=c) for identity,c in observations.items()
           if c['accepted'] and identity not in labeled]
    return dict(reviewedCounts=dict(counts),newlyAcceptedUnreviewed=newly,
                notice='Reviewed baseline cohort only. Newly accepted boxes are unreviewed, not automatically true balls. No whole-video recall or precision inferred.')
