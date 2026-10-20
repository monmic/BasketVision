"""Do not convert unmatched detections or unreviewed crops into negative labels."""
import math
import hashlib


def validate_review_binding(proposal_bytes,review):
    if review.get('proposalsSha256')!=hashlib.sha256(proposal_bytes).hexdigest():
        raise ValueError('Proposals changed after visual review')


def select_reviewed(proposals, review, training_images):
    by_id={row['id']:row for row in proposals}
    decisions={row['id']:row for row in review['items']}
    if len(by_id)!=len(proposals) or len(decisions)!=len(review['items']):
        raise ValueError('Duplicate review or proposal ID')
    if set(by_id)!=set(decisions):
        raise ValueError('Review must cover exactly the proposed IDs')
    selected=[]
    for key,row in by_id.items():
        decision=decisions[key]
        if row['image'] not in training_images:
            raise ValueError('Proposal is not a training image')
        if decision['crop'] not in ['verified_negative','excluded']:
            raise ValueError('Unreviewed crop')
        if decision['candidate'] not in ['non_ball','unannotated_ball','ambiguous']:
            raise ValueError('Unknown candidate classification')
        if not decision.get('reason'):
            raise ValueError('Review reason required')
        if decision['crop']=='verified_negative':
            if decision['candidate']!='non_ball':
                raise ValueError('Cannot label a ball or ambiguous candidate as background')
            selected.append(row)
    return selected


def validate_window(window,width,height,truth,margin=16):
    if len(window)!=4 or not all(type(v) is int for v in window):
        raise ValueError('Integer crop coordinates required')
    x,y,r,b=window
    if not (0<=x<r<=width and 0<=y<b<=height):
        raise ValueError('Window outside image')
    for box in truth:
        if len(box)!=4 or not all(math.isfinite(v) for v in box):
            raise ValueError('Invalid reference box')
        x1,y1,x2,y2=box
        if not (0<=x1<x2<=1 and 0<=y1<y2<=1):
            raise ValueError('Invalid reference box')
        if min(r,x2*width+margin)>max(x,x1*width-margin) and min(b,y2*height+margin)>max(y,y1*height-margin):
            raise ValueError('Negative crop touches annotated ball or safety margin')
