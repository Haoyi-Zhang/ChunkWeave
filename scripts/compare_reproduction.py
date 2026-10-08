"""Compare deterministic outcomes of primary and reproduction runs without pooling timings."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any

VOLATILE = {
    'elapsed_ms', 'construction_ms', 'wall_seconds', 'seconds', 'clock_utc', 'utc',
    'peak_rss_kib', 'child_peak_rss_kib', 'command', 'median_ms', 'mean_ms', 'p95_ms',
    'median_overhead_percent', 'total_ms', 'detected_ms',
    'paired_median_overhead_percent', 'pooled_ratio_of_medians_percent',
    'peak_rss_source', 'platform', 'python', 'node',
}


def read_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items() if key not in VOLATILE}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def json_lines(path: Path) -> list[dict]:
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--primary', type=Path, default=Path('results/study'))
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('results/reproduction-audit.json'))
    args = parser.parse_args()
    checks: list[dict] = []

    scalar_files = (
        'resources.json', 'baselines.json.gz', 'source-differences.json.gz',
        'projection-audit.json', 'shadow-law.json', 'reduction.json',
        'upstream-summary.json', 'cli-smoke.json', 'analysis/summary.json',
        'commit-gate/exhaustive.json',
    )
    for filename in scalar_files:
        primary = normalize(read_json(args.primary / filename))
        replay = normalize(read_json(args.replay / filename))
        checks.append({'file': filename, 'equal': primary == replay})

    # Gate summary contains timing fields; normalization removes them while preserving all semantic counts.
    primary_gate = normalize(read_json(args.primary / 'commit-gate/summary.json'))
    replay_gate = normalize(read_json(args.replay / 'commit-gate/summary.json'))
    checks.append({'file': 'commit-gate/summary.json', 'equal': primary_gate == replay_gate})

    for filename, keys in (
        ('campaigns.jsonl.gz', ('case', 'strategy', 'seed')),
        ('sources.jsonl.gz', ('case', 'adapter')),
        ('commit-gate/observations.jsonl.gz', ('case',)),
    ):
        primary_rows = {
            tuple(row[key] for key in keys): normalize(row)
            for row in json_lines(args.primary / filename)
        }
        replay_rows = {
            tuple(row[key] for key in keys): normalize(row)
            for row in json_lines(args.replay / filename)
        }
        missing = sorted(set(primary_rows) ^ set(replay_rows))
        changed = [key for key in primary_rows.keys() & replay_rows.keys()
                   if primary_rows[key] != replay_rows[key]]
        checks.append({
            'file': filename,
            'primary_records': len(primary_rows),
            'replay_records': len(replay_rows),
            'missing_count': len(missing),
            'changed_count': len(changed),
            'equal': not missing and not changed,
            'first_differences': (missing + changed)[:5],
        })

    timing_keys = ('case', 'family', 'cohort', 'mode', 'repeat', 'seed',
                   'strategy', 'order_rank', 'block_index')
    primary_timing = sorted(tuple(row[key] for key in timing_keys)
                            for row in json_lines(args.primary / 'timing.jsonl.gz'))
    replay_timing = sorted(tuple(row[key] for key in timing_keys)
                           for row in json_lines(args.replay / 'timing.jsonl.gz'))
    checks.append({
        'file': 'timing.jsonl.gz',
        'scope': 'unit membership, seed, and assigned order only',
        'primary_records': len(primary_timing),
        'replay_records': len(replay_timing),
        'equal': primary_timing == replay_timing,
    })

    result = {
        'status': 'PASS' if all(check['equal'] for check in checks) else 'FAIL',
        'checks': checks,
        'excluded_fields': sorted(VOLATILE),
        'timing_note': 'Runtime-dependent durations and budget hits are retained separately and not pooled.',
        'primary': str(args.primary),
        'replay': str(args.replay),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if result['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
