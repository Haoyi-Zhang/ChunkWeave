import unittest

from chunkweave.quotient import execute
from scripts.interaction_law import SCALARS, SourceWorker, audit, closed_form, fixture, predicts_failure

SPECTRA = (
    [0, 0, 1, 6, 15, 20, 15, 6, 1],
    [0, 0, 3, 19, 51, 75, 65, 33, 9, 1],
    [0, 0, 6, 40, 115, 186, 185, 116, 45, 10, 1],
)


class InteractionLawTests(unittest.TestCase):
    def test_literal_counts_and_spectra(self):
        for width, partitions, failures, spectrum in zip(
                (2, 3, 4), (256, 512, 1024), (64, 256, 704), SPECTRA):
            with self.subTest(width=width):
                formula = closed_form(width)
                self.assertEqual(formula['partitions'], partitions)
                self.assertEqual(formula['failing_partitions'], failures)
                self.assertEqual(formula['failure_spectrum'], spectrum)
                self.assertEqual(sum(spectrum), failures)
                self.assertEqual(sum(formula['total_spectrum']), partitions)

    def test_profile_restrictions(self):
        for scalar in ('', 'a', '\ufeff', '\ufffd', '\ud800', 'é中', 'data:é\n\n', None):
            with self.subTest(scalar=scalar), self.assertRaises(ValueError):
                fixture(scalar)
        for width in (True, 1, 5, 2.0):
            with self.subTest(width=width), self.assertRaises(ValueError):
                closed_form(width)

    def test_cut_validation(self):
        for cuts in ([0], [9], [6, 5], [5, 5], [True], [5.0]):
            with self.subTest(cuts=cuts), self.assertRaises(ValueError):
                predicts_failure('é', cuts)

    def test_single_cuts_pair_and_bytewise(self):
        for scalar in SCALARS:
            raw = fixture(scalar)
            self.assertFalse(predicts_failure(scalar, []))
            for cut in range(1, len(raw)):
                self.assertFalse(predicts_failure(scalar, [cut]))
            self.assertTrue(predicts_failure(scalar, [5, 6]))
            self.assertFalse(predicts_failure(scalar, [4, 5]))
            self.assertFalse(predicts_failure(scalar, [5, 5 + len(raw) - 7]))
            self.assertTrue(predicts_failure(scalar, list(range(1, len(raw)))))

    def test_source_model_formula_exhaustive_owned_family(self):
        result = audit(SourceWorker())
        self.assertEqual(result['status'], 'passed')
        self.assertFalse(result['campaign_rerun'])
        self.assertEqual(result['partitions'], 1792)
        self.assertEqual(result['source_executions'], 3584)
        self.assertEqual(result['model_executions'], 3584)
        for row, spectrum in zip(result['rows'], SPECTRA):
            self.assertEqual(row['source_failure_spectrum'], spectrum)
            self.assertEqual(row['model_failure_spectrum'], spectrum)
            self.assertEqual(row['mismatch_checks'], 0)
            self.assertTrue(row['whole_input_ok'])
            self.assertEqual(row['single_cut_passes'], row['bytes'] - 1)
            self.assertTrue(row['bytewise_fails'])
            self.assertEqual(row['minimum_failing_cuts'], 2)

    def test_mismatch_and_whole_precheck_are_not_hidden(self):
        class WrongWholeInput:
            def run(self, raw, schedules, modes):
                rows = []
                for cuts in schedules:
                    row = {mode: execute(raw, cuts, 'correct' if mode == 'bom_owned' else mode)
                           for mode in modes}
                    if not cuts:
                        row['empty_reset']['events'] = []
                    rows.append(row)
                return rows

        result = audit(WrongWholeInput())
        self.assertEqual(result['status'], 'failed')
        for row in result['rows']:
            self.assertFalse(row['whole_input_ok'])
            self.assertEqual(row['mismatch_checks'], 1)
            self.assertEqual(row['first_mismatches'][0]['cuts'], [])


if __name__ == '__main__':
    unittest.main()
