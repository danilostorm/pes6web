import unittest
from tools.check_ppm import inspect_ppm


class FrameInspectionTests(unittest.TestCase):
    def test_black_image(self):
        self.assertEqual(inspect_ppm(b"P6\n2 1\n255\n" + bytes(6)), (2, 1, 0, 2))

    def test_colored_pixel(self):
        self.assertEqual(inspect_ppm(b"P6\n2 1\n255\n" + bytes([4, 0, 0, 0, 0, 0])), (2, 1, 1, 2))

    def test_bad_dimensions(self):
        with self.assertRaises(ValueError):
            inspect_ppm(b"P6\n2 2\n255\n" + bytes(6))


if __name__ == "__main__":
    unittest.main()
