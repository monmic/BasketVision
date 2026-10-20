import unittest
from crop_geometry import crop_window, transform_boxes


class CropGeometryTests(unittest.TestCase):
    def test_known_transform(self):
        self.assertEqual(transform_boxes([[.4,.4,.6,.6]],100,100,(25,25,75,75)),
                         [[.3,.3,.7,.7]])

    def test_corners_and_roundtrip(self):
        for box in [[0,0,.02,.04],[.98,.96,1,1],[.49,.48,.51,.52]]:
            for anchor in [(0.25,0.75),(0.75,0.25)]:
                window=crop_window(box,854,480,256,anchor)
                converted=transform_boxes([box],854,480,window)[0]
                x,y,r,b=window
                recovered=[(x+converted[0]*(r-x))/854,(y+converted[1]*(b-y))/480,
                           (x+converted[2]*(r-x))/854,(y+converted[3]*(b-y))/480]
                for expected,actual in zip(box,recovered):
                    self.assertAlmostEqual(expected,actual)

    def test_partial_other_object_is_not_silently_dropped(self):
        with self.assertRaises(ValueError):
            transform_boxes([[.4,.4,.6,.6],[.7,.4,.9,.6]],100,100,(25,25,75,75))

    def test_empty_and_too_small_crop_rejected(self):
        with self.assertRaises(ValueError):
            crop_window([.1,.1,.9,.9],100,100,20,(.5,.5))
        with self.assertRaises(ValueError):
            transform_boxes([[.8,.8,1,1]],100,100,(0,0,50,50))

    def test_anchor_changes_position_without_changing_box(self):
        box=[.49,.48,.51,.52]
        a=crop_window(box,854,480,256,(.25,.25))
        b=crop_window(box,854,480,256,(.75,.75))
        self.assertNotEqual(a,b)
        for window in [a,b]:
            transform_boxes([box],854,480,window)


if __name__ == '__main__':
    unittest.main()
