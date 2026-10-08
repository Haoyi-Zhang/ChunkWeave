import copy
import unittest

from scripts.write_results import gate_overheads, gate_overhead_text


def synthetic_rows():
    # Three different keys even though the case is shared. Pooled and paired
    # statistics intentionally differ, so a regression cannot swap their labels.
    rows = []
    for (schedule, repeat), values in zip(
            ((0, 0), (1, 0), (0, 1)), ((1, 2, 3), (10, 100, 150), (100, 101, 202))):
        for mode, value in zip(('bom_owned', 'gate', 'gate_all'), values):
            rows.append({'case': 'synthetic', 'schedule_index': schedule,
                         'repeat': repeat, 'mode': mode, 'elapsed_ms': value})
    return rows


class ResultSummaryTests(unittest.TestCase):
    def test_paired_median_is_not_ratio_of_pooled_medians(self):
        result = gate_overheads(synthetic_rows())
        self.assertEqual(result['gate']['paired_workloads'], 3)
        self.assertAlmostEqual(result['gate']['paired_median_overhead_percent'], 100)
        self.assertAlmostEqual(result['gate']['pooled_ratio_of_medians_percent'], 900)
        self.assertAlmostEqual(result['gate_all']['paired_median_overhead_percent'], 200)
        self.assertAlmostEqual(result['gate_all']['pooled_ratio_of_medians_percent'], 1400)

    def test_pairs_use_case_schedule_repeat_not_row_order(self):
        rows = synthetic_rows()
        self.assertEqual(gate_overheads(rows), gate_overheads(list(reversed(rows))))
        self.assertEqual(gate_overheads(rows), gate_overheads(rows[::2] + rows[1::2]))

    def test_records_remain_unchanged(self):
        rows = synthetic_rows()
        original = copy.deepcopy(rows)
        gate_overheads(rows)
        self.assertEqual(rows, original)

    def test_human_readable_labels_and_formulas(self):
        text = gate_overhead_text(gate_overheads(synthetic_rows()))
        self.assertIn('Median paired per-workload overhead is 100.00%', text)
        self.assertIn('200.00%', text)
        self.assertIn('ratios of pooled medians are 900.00% and 1400.00%', text)
        self.assertIn('(case, schedule_index, repeat)', text)
        self.assertIn('100*(median(mode)/median(bom_owned) - 1)', text)

    def test_identical_mode_timings_have_zero_overhead(self):
        rows = synthetic_rows()
        for row in rows:
            row['elapsed_ms'] = 5
        for value in gate_overheads(rows).values():
            self.assertEqual(value['paired_median_overhead_percent'], 0)
            self.assertEqual(value['pooled_ratio_of_medians_percent'], 0)

    def test_duplicate_and_incomplete_pairs_are_rejected(self):
        rows = synthetic_rows()
        for data in ([], rows[:-1], rows + [rows[0]]):
            with self.subTest(records=len(data)), self.assertRaises(ValueError):
                gate_overheads(data)

    def test_invalid_timing_values_are_not_silently_dropped(self):
        for value in (0, -1, float('nan'), float('inf'), True, '1', 10 ** 1000):
            rows = synthetic_rows()
            rows[0]['elapsed_ms'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                gate_overheads(rows)

    def test_finite_inputs_cannot_emit_nonfinite_overheads(self):
        for baseline, mode_time in ((1e-300, 1e300), (1, 1e307)):
            rows = synthetic_rows()
            for row in rows:
                row['elapsed_ms'] = baseline if row['mode'] == 'bom_owned' else mode_time
            with self.subTest(baseline=baseline, mode_time=mode_time), self.assertRaises(ValueError):
                gate_overheads(rows)

    def test_finite_inputs_cannot_overflow_even_sample_medians(self):
        rows = synthetic_rows()[:6]
        for row in rows:
            row['elapsed_ms'] = 1e308
        with self.assertRaises(ValueError):
            gate_overheads(rows)

    def test_unknown_mode_is_rejected(self):
        rows = synthetic_rows()
        rows[0]['mode'] = 'unrecorded'
        with self.assertRaises(ValueError):
            gate_overheads(rows)


if __name__ == '__main__':
    unittest.main()
