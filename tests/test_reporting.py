import unittest

from chunkweave.reporting import peak_rss_tex


class ResourceReportingTests(unittest.TestCase):
    def test_measured_rss_preserves_units_and_rounding(self):
        self.assertEqual(peak_rss_tex(171808), '167.78~MiB')
        self.assertEqual(peak_rss_tex(0), '0.00~MiB')
        self.assertEqual(peak_rss_tex(1024.0), '1.00~MiB')

    def test_unavailable_rss_is_not_a_numeric_measurement(self):
        self.assertEqual(peak_rss_tex(None), 'not measured')
        self.assertNotIn('MiB', peak_rss_tex(None))

    def test_invalid_resources_are_not_printed_as_measurements(self):
        for value in (True, False, -1, float('nan'), float('inf'), '171808', {}, 10**1000):
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                peak_rss_tex(value)
