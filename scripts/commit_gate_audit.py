"""Evaluate CommitGate and its callback-triggered reconfiguration variants."""
from __future__ import annotations

import argparse
import gzip
import json
import random
import statistics
import subprocess
import time
from collections import defaultdict
from pathlib import Path

from chunkweave.adapters import NodeWorker
from chunkweave.oracle import evaluate
from chunkweave.corpus_extensions import cases
from chunkweave.schedules import distinct
from chunkweave.strategies import iterate

PAIRS = (
    ('decoder_per_event', 'gate_decoder_per_event'),
    ('parser_per_event', 'gate_parser_per_event'),
    ('decoder_per_retry', 'gate_decoder_per_retry'),
    ('parser_per_retry', 'gate_parser_per_retry'),
)
GATE_MODES = ('gate',) + tuple(guarded for _, guarded in PAIRS) + ('gate_all',)
ALL_MODES = tuple(unsafe for unsafe, _ in PAIRS) + GATE_MODES
KEYS = ('events', 'retries', 'last_event_id')


def observation(value: dict) -> dict:
    return {key: value[key] for key in KEYS}


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * q)))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('results/commit-gate'))
    parser.add_argument('--repeats', type=int, default=7)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 25:
        raise ValueError('repeats must be in [1, 25]')
    args.out.mkdir(parents=True, exist_ok=True)

    corpus = cases()
    started = time.perf_counter()
    raw_rows = []
    per_mode = defaultdict(lambda: {
        'streams': 0,
        'checks': 0,
        'whole_mismatches': 0,
        'changed_streams': 0,
        'changed_checks': 0,
        'semantic_mismatch_checks': 0,
    })

    with NodeWorker() as worker, gzip.open(args.out / 'observations.jsonl.gz', 'wt', encoding='utf-8') as output:
        for _ in range(40):
            worker.run('data:warmé\n\n'.encode(), [[6]], list(ALL_MODES))
        for case_index, case in enumerate(corpus):
            raw = case['text'].encode('utf-8')
            expected = case['expected']
            schedules = distinct(
                [[]] + list(iterate(raw, 'fixed')) + list(iterate(raw, 'callback-aware')),
                33,
            )
            schedules = [
                cuts for cuts in schedules
                if len(cuts) + 1 <= 4096 or len(raw) <= 4096
            ]
            whole = worker.run(raw, [[]], list(ALL_MODES))[0]
            baselines = {mode: whole[mode] for mode in ALL_MODES}
            trials = worker.run(
                raw,
                schedules,
                list(ALL_MODES),
                expected=expected,
                baselines=baselines,
            )
            compact = {}
            for mode in ALL_MODES:
                stats = per_mode[mode]
                stats['streams'] += 1
                stats['checks'] += len(trials)
                stats['whole_mismatches'] += observation(whole[mode]) != expected
                changes = [bool(row[mode]['changed']) for row in trials]
                mismatches = [
                    not (row[mode]['event_ok'] and row[mode]['control_ok'])
                    for row in trials
                ]
                stats['changed_streams'] += any(changes)
                stats['changed_checks'] += sum(changes)
                stats['semantic_mismatch_checks'] += sum(mismatches)
                compact[mode] = {
                    'whole_ok': observation(whole[mode]) == expected,
                    'changed': changes,
                    'semantic_mismatch': mismatches,
                }
            record = {
                'case': case['id'],
                'family': case['family'],
                'cohort': case['cohort'],
                'bytes': len(raw),
                'schedules': schedules,
                'modes': compact,
            }
            output.write(json.dumps(record, separators=(',', ':')) + '\n')
            raw_rows.append(record)
            if case_index % 100 == 0:
                print(f'{case_index + 1}/{len(corpus)}', flush=True)

        # Input-only benchmark sample: first, middle, last case in each family.
        families = defaultdict(list)
        for case in corpus:
            families[case['family']].append(case)
        selected = []
        for family_cases in families.values():
            family_cases.sort(key=lambda item: item['id'])
            selected.extend((family_cases[0], family_cases[len(family_cases) // 2], family_cases[-1]))
        selected = list({case['id']: case for case in selected}.values())
        timing_modes = ('bom_owned', 'gate', 'gate_all')
        timing_rows = []
        rng = random.Random(202610081)
        for repeat in range(args.repeats):
            for case_index, case in enumerate(selected):
                raw = case['text'].encode('utf-8')
                schedules = [[]]
                fixed = list(range(64, len(raw), 64))
                if len(fixed) + 1 <= 4096 and fixed:
                    schedules.append(fixed)
                callback = list(iterate(raw, 'two-obligation'))
                if callback:
                    schedules.append(callback[-1])
                schedules = distinct(schedules, 3)
                for schedule_index, cuts in enumerate(schedules):
                    order = list(timing_modes)
                    rng.shuffle(order)
                    row = worker.run(raw, [cuts], order)[0]
                    for rank, mode in enumerate(order):
                        timing_rows.append({
                            'case': case['id'],
                            'family': case['family'],
                            'bytes': len(raw),
                            'feeds': len(cuts) + 1,
                            'schedule_index': schedule_index,
                            'repeat': repeat,
                            'order_rank': rank,
                            'mode': mode,
                            'elapsed_ms': row[mode]['elapsed_ms'],
                        })

    timing_summary = {}
    for mode in ('bom_owned', 'gate', 'gate_all'):
        values = [row['elapsed_ms'] for row in timing_rows if row['mode'] == mode]
        timing_summary[mode] = {
            'runs': len(values),
            'median_ms': statistics.median(values),
            'mean_ms': statistics.mean(values),
            'p95_ms': percentile(values, 0.95),
        }
    baseline_median = timing_summary['bom_owned']['median_ms']
    for mode in ('gate', 'gate_all'):
        timing_summary[mode]['median_overhead_percent'] = (
            timing_summary[mode]['median_ms'] / baseline_median - 1
        ) * 100
        grouped = defaultdict(dict)
        for row in timing_rows:
            grouped[(row['case'],row['schedule_index'],row['repeat'])][row['mode']] = row['elapsed_ms']
        ratios = [(value[mode]/value['bom_owned']-1)*100 for value in grouped.values()
                  if mode in value and value.get('bom_owned',0)>0]
        timing_summary[mode]['paired_median_overhead_percent'] = statistics.median(ratios)
        timing_summary[mode]['paired_workloads'] = len(ratios)
        timing_summary[mode]['pooled_ratio_of_medians_percent'] = timing_summary[mode]['median_overhead_percent']

    exhaustive_path = args.out / 'exhaustive.json'
    subprocess.run([
        'node', '--no-warnings', '--experimental-transform-types',
        str(Path(__file__).with_name('commit_gate_exhaustive.mjs')),
        str(exhaustive_path),
    ], check=True)
    exhaustive = json.loads(exhaustive_path.read_text())

    result = {
        'status': 'PASS',
        'corpus_streams': len(corpus),
        'corpus_bytes': sum(case['bytes'] for case in corpus),
        'max_bytes': max(case['bytes'] for case in corpus),
        'mode_summary': dict(per_mode),
        'pairs': [
            {
                'unsafe': unsafe,
                'guarded': guarded,
                'unsafe_changed_streams': per_mode[unsafe]['changed_streams'],
                'guarded_changed_streams': per_mode[guarded]['changed_streams'],
                'unsafe_mismatch_checks': per_mode[unsafe]['semantic_mismatch_checks'],
                'guarded_mismatch_checks': per_mode[guarded]['semantic_mismatch_checks'],
            }
            for unsafe, guarded in PAIRS
        ],
        'timing': {
            'selected_streams': len({row['case'] for row in timing_rows}),
            'rows': len(timing_rows),
            'repeats': args.repeats,
            'summary': timing_summary,
        },
        'exhaustive': exhaustive,
        'wall_seconds': time.perf_counter() - started,
    }
    for mode in GATE_MODES:
        summary = per_mode[mode]
        if any(summary[key] for key in (
            'whole_mismatches', 'changed_streams', 'changed_checks', 'semantic_mismatch_checks'
        )):
            result['status'] = 'FAIL'
    if exhaustive['status'] != 'PASS':
        result['status'] = 'FAIL'

    (args.out / 'timing.json').write_text(json.dumps(timing_rows, indent=2) + '\n')
    (args.out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if result['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
