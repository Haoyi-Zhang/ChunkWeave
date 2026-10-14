import gzip
import json
from pathlib import Path
import tempfile
import unittest

from chunkweave.plot_inputs import read_json, read_timing_records


class PlotInputs(unittest.TestCase):
    def test_json_keeps_non_ascii_scalar(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'law.json'
            path.write_text('{"text":"data: 中\\n\\n","bytes":11}',encoding='utf-8')
            self.assertEqual(read_json(path),dict(text='data: 中\n\n',bytes=11))

    def test_compressed_records_keep_non_ascii_text_and_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'records.jsonl.gz'
            expected=[dict(text='é中',detected_ms=None),dict(text='λ',detected_ms=3.5)]
            with gzip.open(path,'wt',encoding='utf-8') as stream:
                stream.write('\n'.join(json.dumps(r,ensure_ascii=False) for r in expected)+'\n')
            self.assertEqual(read_timing_records(path),expected)

    def test_invalid_utf8_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.json';path.write_bytes(b'{"text":"\xff"}')
            with self.assertRaises(UnicodeDecodeError):read_json(path)

    def test_invalid_json_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.json';path.write_text('{',encoding='utf-8')
            with self.assertRaises(json.JSONDecodeError):read_json(path)


if __name__=='__main__':unittest.main()
