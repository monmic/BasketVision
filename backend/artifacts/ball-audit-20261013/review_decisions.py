"""Manual decisions from all 12 scene boards and unmarked enlarged details.

Coordinates are approximate image-pixel boxes, not model predictions.
Conservative exclusions include uncertain partial visibility, not empty labels.
"""
TRAIN_CENTERS = {
    13002:(163,259),13008:(163,259),13014:(163,259),13020:(163,260),
    13026:(161,260),13242:(160,260),13248:(160,261),13254:(159,260),
    13272:(159,261),13284:(159,263),13290:(159,263),
}
OTHER_CENTERS = {
    13662:(186,267),13668:(236,266),13674:(267,264),13680:(288,264),
    13686:(300,262),13692:(306,262),13698:(310,261),13704:(312,261),
    13710:(313,260),13716:(314,259),13722:(315,256),13728:(315,256),
    13734:(316,255),13740:(316,256),14160:(264,262),14172:(289,260),
    14178:(294,260),14184:(298,259),14190:(301,259),14196:(303,259),
    14202:(305,257),14208:(307,256),14214:(309,256),14220:(310,256),
    14226:(311,256),14232:(312,256),14238:(313,256),14244:(314,256),
}

def decision(frame):
    if frame in TRAIN_CENTERS:
        x,y=TRAIN_CENTERS[frame]
        return [[x-6,y-7,x+7,y+7]], True, 'Visible additional stationary ball at left wall; approximate manual bounds.'
    if frame in OTHER_CENTERS:
        x,y=OTHER_CENTERS[frame]
        return [[x-5,y-6,x+5,y+5]], True, 'Visible additional stationary ball at left wall; approximate manual bounds.'
    if frame<13400 or frame in (13650,13656,14250):
        return [], False, 'Wall-ball region occluded, partially visible or too blurred for reliable additional bounds; exclude whole frame conservatively.'
    return [], True, 'Full scene reviewed; no additional ball confidently identified. Original action-ball annotation retained.'
