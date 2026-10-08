"""Exhaust the owned single-scalar silent-fragment family, not a study campaign.

Observations come from the functional Python model and the unchanged vendored
JS parser, not from the theorem predicate. No sockets, URLs, or arbitrary input.
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
from math import comb
from pathlib import Path

from chunkweave.oracle import evaluate, slices
from chunkweave.quotient import execute

SCALARS = ('é', '中', '🌍')
KEYS = ('events', 'retries', 'last_event_id')


class SourceWorker:
    """One bounded pipe-only request per fixture; no HTTPX/Python adapter import."""

    def run(self, raw: bytes, schedules: list[list[int]], modes: list[str]) -> list[dict]:
        worker_path = Path(__file__).resolve().parents[1] / 'chunkweave' / 'node_worker.mjs'
        request = {'b64': base64.b64encode(raw).decode('ascii'),
                   'schedules': schedules, 'modes': modes}
        result = subprocess.run(
            ['node', '--no-warnings', '--experimental-transform-types', str(worker_path)],
            input=json.dumps(request) + '\n', capture_output=True, text=True,
            encoding='utf-8', check=True, timeout=30,
        )
        response = json.loads(result.stdout)
        if 'error' in response:
            raise RuntimeError(response['error'])
        return response['answers']


def fixture(scalar: str) -> bytes:
    if not isinstance(scalar, str) or len(scalar) != 1:
        raise ValueError('expected one Unicode scalar')
    try:
        width = len(scalar.encode('utf-8'))
    except UnicodeEncodeError as error:
        raise ValueError('surrogates are not Unicode scalars') from error
    if width not in (2, 3, 4) or scalar in ('\ufeff', '\ufffd'):
        raise ValueError('law requires width 2/3/4, excluding U+FEFF and U+FFFD')
    return ('data:' + scalar + '\n\n').encode('utf-8')


def predicts_failure(scalar: str, cuts: list[int]) -> bool:
    raw = fixture(scalar)
    slices(raw, cuts)  # Validate strictly increasing interior offsets.
    width = len(raw) - 7
    return sum(5 <= cut < 5 + width for cut in cuts) >= 2


def closed_form(width: int) -> dict:
    if type(width) is not int or width not in (2, 3, 4):
        raise ValueError('width must be 2, 3, or 4')
    # Choose j cuts in W and k-j in the six free positions.
    failures = [
        sum(comb(width, j) * comb(6, k - j)
            for j in range(2, width + 1) if 0 <= k - j <= 6)
        for k in range(width + 7)
    ]
    return {
        'partitions': 1 << (width + 6),
        'failing_partitions': ((1 << width) - width - 1) * 64,
        'failure_spectrum': failures,
        'total_spectrum': [comb(width + 6, k) for k in range(width + 7)],
    }


def audit(worker: SourceWorker) -> dict:
    rows = []
    for scalar in SCALARS:
        raw = fixture(scalar)
        width = len(raw) - 7
        literal = {'events': [{'type': 'message', 'data': scalar, 'id': ''}],
                   'retries': [], 'last_event_id': ''}
        oracle_ok = evaluate(raw) == literal
        schedules = [[i + 1 for i in range(len(raw) - 1) if mask >> i & 1]
                     for mask in range(1 << (len(raw) - 1))]
        source_rows = worker.run(raw, schedules, ['bom_owned', 'empty_reset'])
        source_histogram = [0] * len(raw)
        model_histogram = [0] * len(raw)
        total_histogram = [0] * len(raw)
        mismatches = []
        mismatch_checks = 0
        whole_ok = False
        single_cut_passes = 0
        bytewise_fails = False
        for cuts, source in zip(schedules, source_rows, strict=True):
            model = execute(raw, cuts, 'empty_reset')
            model_clean = execute(raw, cuts, 'correct')
            observed = {key: source['empty_reset'][key] for key in KEYS}
            clean = {key: source['bom_owned'][key] for key in KEYS}
            source_bad = observed != literal
            model_bad = model != literal
            predicted = predicts_failure(scalar, cuts)
            predicted_observation = ({'events': [], 'retries': [], 'last_event_id': ''}
                                     if predicted else literal)
            total_histogram[len(cuts)] += 1
            source_histogram[len(cuts)] += source_bad
            model_histogram[len(cuts)] += model_bad
            agrees = (oracle_ok and clean == literal and model_clean == literal
                      and observed == model == predicted_observation)
            if not agrees:
                mismatch_checks += 1
                if len(mismatches) < 20:
                    mismatches.append({'cuts': cuts, 'predicted_failure': predicted,
                                       'source': observed, 'model': model,
                                       'source_clean': clean, 'model_clean': model_clean})
            if not cuts:
                whole_ok = agrees and not source_bad and not model_bad
            if len(cuts) == 1 and agrees and not source_bad:
                single_cut_passes += 1
            if len(cuts) == len(raw) - 1:
                bytewise_fails = agrees and source_bad and model_bad
        formula = closed_form(width)
        minimum = next((k for k, value in enumerate(source_histogram) if value), None)
        passed = (mismatch_checks == 0 and whole_ok and bytewise_fails
                  and single_cut_passes == len(raw) - 1 and minimum == 2
                  and len(schedules) == formula['partitions']
                  and total_histogram == formula['total_spectrum']
                  and source_histogram == model_histogram == formula['failure_spectrum']
                  and sum(source_histogram) == formula['failing_partitions'])
        rows.append({
            'status': 'passed' if passed else 'failed',
            'scalar': scalar, 'codepoint': f'U+{ord(scalar):04X}',
            'width': width, 'bytes': len(raw), 'partitions': len(schedules),
            'source_failures': sum(source_histogram), 'model_failures': sum(model_histogram),
            'source_failure_spectrum': source_histogram,
            'model_failure_spectrum': model_histogram, 'closed_form': formula,
            'whole_input_ok': whole_ok, 'single_cut_passes': single_cut_passes,
            'bytewise_fails': bytewise_fails, 'minimum_failing_cuts': minimum,
            'mismatch_checks': mismatch_checks, 'first_mismatches': mismatches,
        })
    partitions = sum(row['partitions'] for row in rows)
    return {
        'status': 'passed' if all(row['status'] == 'passed' for row in rows) else 'failed',
        'law': 'silent-fragment / empty_reset',
        'scope': 'one scalar per width, all partitions of three owned 9/10/11-byte fixtures',
        'campaign_rerun': False,
        'partitions': partitions,
        'source_executions': 2 * partitions, 'model_executions': 2 * partitions,
        'source_modes': ['bom_owned', 'empty_reset'], 'rows': rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='optional new JSON file; never overwrite')
    args = parser.parse_args()
    if args.out is not None and args.out.exists():
        raise SystemExit('Refusing to overwrite an existing audit file')
    result = audit(SourceWorker())
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x', encoding='utf-8') as stream:
            stream.write(text)
    print(text, end='')
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
