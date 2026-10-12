"""Regenerate the supplementary TeX table from new measured records; no compiler."""
from __future__ import annotations
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

LABELS = {
    'direct-fatal': 'Direct fatal decoder (no replacements)',
    'original': 'Original gate',
    'suffix-line': 'Suffix observer, line-only feeds',
    'optimized': 'Optimized gate',
    'original-all': 'Original gate, all requests',
    'optimized-all': 'Optimized gate, all requests',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('results/commit-gate-optimized-final'))
    parser.add_argument('--paper', type=Path, default=Path('../paper'))
    args = parser.parse_args()
    rows = json.loads((args.out / 'timing.json').read_text())
    cold = json.loads((args.out / 'cold.json').read_text())
    work = json.loads((args.out / 'work.json').read_text())
    summary = json.loads((args.out / 'summary.json').read_text())
    pairs = defaultdict(dict)
    for row in rows:
        key = (row['case'], row['schedule'], row['repeat'])
        assert row['variant'] not in pairs[key]
        assert row['elapsed_ms'] > 0
        pairs[key][row['variant']] = row['elapsed_ms']
    assert len(pairs) == summary['workloads'] * summary['repeats'] == 1440
    assert all(set(pair) == set(LABELS) for pair in pairs.values())
    table = [r'\begin{tabular}{@{}lrrrr@{}}', r'\toprule',
             r'Composition&Warm ($\mu$s)&Paired (\%)&First (ms)&Process (ms)\\',
             r'\midrule']
    for variant, label in LABELS.items():
        values = [row['elapsed_ms'] for row in rows if row['variant'] == variant]
        baseline = 'original-all' if variant.endswith('-all') else 'original'
        change = statistics.median(100 * (pair[variant] / pair[baseline] - 1) for pair in pairs.values())
        assert abs(change - summary['summary'][variant]['paired_vs_original_percent']) < 1e-9
        first = statistics.median(row['first_execution_ms'] for row in cold if row['variant'] == variant)
        process = statistics.median(row['process_ms'] for row in cold if row['variant'] == variant)
        displayed = '--' if variant == 'direct-fatal' else f'{change:.2f}'
        table.append(f'{label}&{1000 * statistics.median(values):.2f}&{displayed}&{first:.3f}&{process:.2f}' + r'\\')
    table += [r'\bottomrule', r'\end{tabular}']
    # Every measured composition receives the same bytes and cuts. Work records
    # are a SINGLE untimed pass, not multiplied by adaptive timing repetitions.
    keys = ('bytes', 'feeds', 'decoded_bytes', 'decode_calls', 'boundary_byte_inspections',
            'parser_feed_calls', 'decoder_resets', 'parser_resets')
    totals = {variant: {key: sum(row[key] for row in work if row['variant'] == variant)
                        for key in keys} for variant in LABELS}
    for variant in LABELS:
        for key in ('bytes', 'feeds', 'decoded_bytes', 'decode_calls'):
            assert totals[variant][key] == totals['original'][key]
    for key in ('decoder_resets', 'parser_resets'):
        assert totals['optimized-all'][key] == totals['original-all'][key]
    target = args.paper / 'generated' / 'gate-refinement.tex'
    target.write_text('\n'.join(table) + '\n', encoding='utf-8')
    print(json.dumps({'table': str(target), 'paired_repeats': len(pairs), 'work_totals': totals}, indent=2))


if __name__ == '__main__':
    main()
