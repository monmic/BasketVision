"""Pure coordinate transformations for training crops; normalized xyxy boxes."""
import math


def crop_window(box, width, height, crop_width, anchor):
    x1, y1, x2, y2 = box
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        raise ValueError('Invalid box')
    if width < 1 or height < 1 or not 0 < crop_width <= width:
        raise ValueError('Invalid dimensions')
    cw, ch = int(crop_width), max(1, round(crop_width * height / width))
    ax, ay = anchor
    if not (0 <= ax <= 1 and 0 <= ay <= 1):
        raise ValueError('Invalid anchor')
    # Feasible integer origins that keep the complete object within the crop.
    lo_x, hi_x = max(0, math.ceil(x2*width-cw)), min(width-cw, math.floor(x1*width))
    lo_y, hi_y = max(0, math.ceil(y2*height-ch)), min(height-ch, math.floor(y1*height))
    if lo_x > hi_x or lo_y > hi_y:
        raise ValueError('Object does not fit crop')
    left = min(hi_x, max(lo_x, round((x1+x2)*width/2-ax*cw)))
    top = min(hi_y, max(lo_y, round((y1+y2)*height/2-ay*ch)))
    return left, top, left+cw, top+ch


def transform_boxes(boxes, width, height, window):
    left, top, right, bottom = window
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError('Invalid crop window')
    result = []
    for x1,y1,x2,y2 in boxes:
        x1,y1,x2,y2 = x1*width,y1*height,x2*width,y2*height
        if x2 <= left or x1 >= right or y2 <= top or y1 >= bottom:
            continue
        if x1 < left-1e-8 or y1 < top-1e-8 or x2 > right+1e-8 or y2 > bottom+1e-8:
            raise ValueError('Crop partially cuts an annotated object')
        result.append([(x1-left)/(right-left),(y1-top)/(bottom-top),
                       (x2-left)/(right-left),(y2-top)/(bottom-top)])
    if not result:
        raise ValueError('No positive annotation in crop')
    return result
