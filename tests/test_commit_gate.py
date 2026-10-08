import unittest

from chunkweave.adapters import NodeWorker
from chunkweave.oracle import evaluate, slices
from chunkweave.corpus_extensions import cases


class CommitGateTests(unittest.TestCase):
    def _assert_repair(self, text: str, cut: int, unsafe: str, guarded: str) -> None:
        raw = text.encode('utf-8')
        expected = evaluate(raw)
        with NodeWorker() as worker:
            row = worker.run(
                raw,
                [[cut]],
                [unsafe, guarded],
                expected=expected,
                retain_actual=True,
            )[0]
        self.assertFalse(row[unsafe]['event_ok'])
        self.assertTrue(row[guarded]['event_ok'])
        self.assertTrue(row[guarded]['control_ok'])

    def test_decoder_replacement_after_event_is_quiescent(self):
        self._assert_repair(
            'data:a\n\ndata:中\n\n', 14,
            'decoder_per_event', 'gate_decoder_per_event',
        )

    def test_parser_replacement_after_event_is_committed(self):
        self._assert_repair(
            'data:a\n\ndata:b\n\n', 9,
            'parser_per_event', 'gate_parser_per_event',
        )

    def test_decoder_replacement_after_retry_is_quiescent(self):
        self._assert_repair(
            'retry:1\ndata:中\n\n', 14,
            'decoder_per_retry', 'gate_decoder_per_retry',
        )

    def test_parser_replacement_after_retry_is_committed(self):
        self._assert_repair(
            'retry:1\ndata:b\n\n', 9,
            'parser_per_retry', 'gate_parser_per_retry',
        )

    def test_gate_owns_bom_across_parser_replacements(self):
        raw = 'data:first\n\n\ufeffdata:hidden\n\ndata:last\n\n'.encode('utf-8')
        expected = evaluate(raw)
        with NodeWorker() as worker:
            rows = worker.run(
                raw,
                [[], list(range(1, len(raw)))],
                ['gate', 'gate_parser_per_event', 'gate_all'],
                expected=expected,
            )
        for row in rows:
            for mode in ('gate', 'gate_parser_per_event', 'gate_all'):
                self.assertTrue(row[mode]['event_ok'], mode)
                self.assertTrue(row[mode]['control_ok'], mode)

    def test_gate_preserves_corpus_on_representative_partitions(self):
        modes = (
            'gate', 'gate_decoder_per_event', 'gate_parser_per_event',
            'gate_decoder_per_retry', 'gate_parser_per_retry', 'gate_all',
        )
        selected = [
            c for i, c in enumerate(cases())
            if i % 37 == 0 or c['id'].startswith('truth-')
        ]
        with NodeWorker() as worker:
            for case in selected:
                raw = case['text'].encode('utf-8')
                schedules = [[]]
                if len(raw) > 1:
                    schedules.append(list(range(1, len(raw))))
                    schedules.append(list(range(7, len(raw), 7)))
                rows = worker.run(raw, schedules, list(modes), expected=case['expected'])
                for row in rows:
                    for mode in modes:
                        self.assertTrue(row[mode]['event_ok'], (case['id'], mode))
                        self.assertTrue(row[mode]['control_ok'], (case['id'], mode))

    def test_gate_partitions_preserve_bytes(self):
        raw = 'data:é中🌍\r\n\r\n'.encode('utf-8')
        for cuts in ([], [1], [5, 7, 9], list(range(1, len(raw)))):
            self.assertEqual(b''.join(slices(raw, cuts)), raw)


    def test_gate_handles_empty_input(self):
        raw = b''
        expected = evaluate(raw)
        with NodeWorker() as worker:
            row = worker.run(raw, [[]], ['gate', 'gate_all'], expected=expected)[0]
        for mode in ('gate', 'gate_all'):
            self.assertTrue(row[mode]['event_ok'])
            self.assertTrue(row[mode]['control_ok'])

    def test_gate_preserves_crlf_split_and_persistent_id(self):
        raw = b'id:7\r\ndata:a\r\n\r\ndata:b\r\n\r\n'
        expected = evaluate(raw)
        cuts = [5, 6, 14, 15, 16, 24, 25]
        with NodeWorker() as worker:
            row = worker.run(raw, [cuts], ['gate', 'gate_all'], expected=expected)[0]
        for mode in ('gate', 'gate_all'):
            self.assertTrue(row[mode]['event_ok'])
            self.assertTrue(row[mode]['control_ok'])

    def test_gate_does_not_dispatch_incomplete_eof_block(self):
        raw = 'data:delivered\n\ndata:pending 中'.encode('utf-8')
        expected = evaluate(raw)
        with NodeWorker() as worker:
            rows = worker.run(raw, [[], list(range(1, len(raw)))], ['gate_all'], expected=expected)
        self.assertTrue(all(row['gate_all']['event_ok'] and row['gate_all']['control_ok'] for row in rows))

    def test_gate_applies_retry_reconfiguration_after_block_commit(self):
        raw = 'retry:25\ndata:é\n\nid:9\ndata:next\n\n'.encode('utf-8')
        expected = evaluate(raw)
        with NodeWorker() as worker:
            rows = worker.run(raw, [[9], [10], list(range(1, len(raw)))], ['gate_all'], expected=expected)
        self.assertTrue(all(row['gate_all']['event_ok'] and row['gate_all']['control_ok'] for row in rows))

if __name__ == '__main__':
    unittest.main()
