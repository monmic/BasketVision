import copy
import unittest
from export_detector_pilot import validate_row


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.row=dict(status='visible',pixelBoxes=[[10,20,30,40]],width=100,height=100,split='train')

    def test_normalizes_without_mutating(self):
        original=copy.deepcopy(self.row)
        self.assertEqual(validate_row(self.row),[[.1,.2,.3,.4]])
        self.assertEqual(self.row,original)

    def test_unknown_or_inconsistent_visibility_rejected(self):
        for status in ['unknown','absent','uncertain']:
            with self.subTest(status=status),self.assertRaises(ValueError):
                validate_row(dict(self.row,status=status))
        with self.assertRaises(ValueError):validate_row(dict(self.row,pixelBoxes=[]))

    def test_negative_and_uncertain_have_no_boxes(self):
        for status in ['absent','uncertain']:
            self.assertEqual(validate_row(dict(self.row,status=status,pixelBoxes=[])),[])

    def test_invalid_bounds_and_split_rejected(self):
        for box in [[-1,0,1,1],[0,0,101,1],[1,1,1,2],[0,0,float('nan'),2]]:
            with self.subTest(box=box),self.assertRaises(ValueError):
                validate_row(dict(self.row,pixelBoxes=[box]))
        with self.assertRaises(ValueError):validate_row(dict(self.row,split='other'))


if __name__=='__main__':unittest.main()
