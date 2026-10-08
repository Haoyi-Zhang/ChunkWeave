"""Regenerate manuscript tables, macros, and vector figures from measured outputs."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import statistics
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import matplotlib
matplotlib.use('pgf')
import matplotlib.pyplot as plt
import numpy as np

from chunkweave.shadow_law import failure_probability
from chunkweave.strategies import STRATEGIES

LABEL = {
    'fixed': 'Fixed sizes',
    'bytewise': 'Bytewise',
    'uniform': 'Uniform random',
    'bytewise-sparse': 'Bytewise + sparse random',
    'state-feature': 'State-feature selector',
    'state-feature-no-parser': 'Reduced-tag state selector',
    'callback-aware': 'Callback-aware portfolio',
    'two-obligation': 'Two obligations',
    'no-shadow': 'No-shadow ablation',
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('results/study'))
    parser.add_argument('--paper', type=Path, default=Path('../paper'))
    args = parser.parse_args()
    out, paper = args.out, args.paper
    generated, figures = paper / 'generated', paper / 'figures'
    generated.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    summary = json.loads((out / 'analysis/summary.json').read_text())
    resources = json.loads((out / 'resources.json').read_text())
    law = json.loads((out / 'shadow-law.json').read_text())
    gate = json.loads((out / 'commit-gate/summary.json').read_text())

    timing_rows = [json.loads(line) for line in gzip.open(out / 'timing.jsonl.gz', 'rt')]
    by_strategy: dict[str, list[dict]] = defaultdict(list)
    for row in timing_rows:
        by_strategy[row['strategy']].append(row)
    timing = {}
    for strategy, rows in by_strategy.items():
        units = defaultdict(list)
        for row in rows:
            units[row['case'], row['mode']].append(row)
        timing[strategy] = {
            'units': len(units),
            'runs': len(rows),
            'rates': {
                str(threshold): 100 * sum(
                    row['detected_ms'] is not None and row['detected_ms'] <= threshold
                    for row in rows
                ) / len(rows)
                for threshold in (.1, .3, 1, 3, 10, 30, 50)
            },
            'mean_wall_ms': statistics.mean(row['total_ms'] for row in rows),
            'median_wall_ms': statistics.median(row['total_ms'] for row in rows),
            'mean_feeds': statistics.mean(row['feeds'] for row in rows),
            'mean_tests': statistics.mean(row['schedules'] for row in rows),
            'order_counts': dict(Counter(row['order_rank'] for row in rows)),
        }
    hits = {
        strategy: {
            (row['case'], row['mode'], row['repeat']): row
            for row in rows if row['detected_ms'] is not None
        }
        for strategy, rows in by_strategy.items()
    }
    common = hits['fixed'].keys() & hits['two-obligation'].keys()
    ratios = [hits['fixed'][key]['detected_ms'] / hits['two-obligation'][key]['detected_ms'] for key in common]
    timing['paired_fixed_two'] = {
        'common_detected_repeats': len(common),
        'median_time_ratio': statistics.median(ratios),
        'scope': 'conditional intersection; headline rates retain non-detections',
    }
    (out / 'analysis/timing-summary.json').write_text(json.dumps(timing, indent=2) + '\n')

    cohorts = ['old-input-old-action', 'new-input-old-action',
               'old-input-new-action', 'new-input-new-action']
    table = [
        r'\begin{tabular}{@{}lrrrrr@{}}', r'\toprule',
        r'&\multicolumn{2}{c}{Eight base actions}&\multicolumn{2}{c}{Three callback actions}&All\\',
        r'Policy&Reference&Structural&Reference&Structural&inputs\\', r'\midrule',
    ]
    for strategy in STRATEGIES:
        table.append(LABEL[strategy] + '&' + '&'.join(
            f"{summary['cohorts'][cohort]['rates'][strategy]:.2f}"
            for cohort in cohorts + ['all']
        ) + r'\\')
    table += [
        r'\midrule',
        'Eligible units&' + '&'.join(str(summary['cohorts'][cohort]['units'])
                                     for cohort in cohorts + ['all']) + r'\\',
        r'\bottomrule', r'\end{tabular}',
    ]
    (generated / 'detection.tex').write_text('\n'.join(table) + '\n')

    table = [r'\begin{tabular}{@{}lrrr@{}}', r'\toprule',
             r'Policy&3 ms&10 ms&50 ms\\', r'\midrule']
    for strategy in STRATEGIES:
        table.append(LABEL[strategy] + '&' + '&'.join(
            f"{timing[strategy]['rates'][str(threshold)]:.2f}"
            for threshold in (3, 10, 50)
        ) + r'\\')
    table += [r'\bottomrule', r'\end{tabular}']
    (generated / 'timing.tex').write_text('\n'.join(table) + '\n')

    table = [r'\begin{tabular}{@{}lrrr@{}}', r'\toprule',
             r'Source configuration&Checks&Whole diff.&Changed\\', r'\midrule']
    source_labels = {
        'js-default': 'JS: default decode',
        'js-single-bom-owner': 'JS: single BOM owner',
        'js-skip-empty': 'JS: omit empty text',
        'azure-source': 'Azure byte parser',
        'python-source': 'Python line parser',
    }
    for name, row in summary['source'].items():
        table.append(f"{source_labels[name]}&{row['checks']:,}&{row['whole_mismatch']}&{row['changed_streams']}" + r'\\')
    table += [r'\bottomrule', r'\end{tabular}']
    (generated / 'sources.tex').write_text('\n'.join(table) + '\n')

    gate_labels = {
        'decoder_per_event': 'Decoder / event',
        'parser_per_event': 'Parser / event',
        'decoder_per_retry': 'Decoder / retry',
        'parser_per_retry': 'Parser / retry',
    }
    table = [r'\begin{tabular}{@{}lrrrr@{}}', r'\toprule',
             r'&\multicolumn{2}{c}{Immediate replacement}&\multicolumn{2}{c}{CommitGate}\\',
             r'Trigger&Streams&Mismatch checks&Streams&Mismatch checks\\', r'\midrule']
    for pair in gate['pairs']:
        table.append(
            f"{gate_labels[pair['unsafe']]}&{pair['unsafe_changed_streams']}&"
            f"{pair['unsafe_mismatch_checks']:,}&{pair['guarded_changed_streams']}&"
            f"{pair['guarded_mismatch_checks']:,}" + r'\\'
        )
    table += [r'\bottomrule', r'\end{tabular}']
    (generated / 'commit-gate.tex').write_text('\n'.join(table) + '\n')

    plt.rcParams.update({'font.size': 9, 'font.family': 'serif',
                         'pgf.texsystem': 'pdflatex', 'pgf.rcfonts': False,
                         'pgf.preamble': r'\usepackage[T1]{fontenc}\usepackage{libertine}',
                         'pdf.fonttype': 42, 'ps.fonttype': 42})
    fig, axis = plt.subplots(figsize=(3.35, 2.25))
    density = np.linspace(0, 1, 201)
    density_rows = []
    for row, linestyle, marker in zip(law['rows'][:3], ('-', '--', ':'), ('o', 's', '^')):
        raw = row['text'].encode()
        width = row['bytes'] - 14
        values = [100 * float(failure_probability(raw, Fraction(float(p)).limit_denominator(100000))) for p in density]
        points = [.05, .1, .2, .4, .6, .8]
        weights = [100 * sum(value * p ** cuts * (1 - p) ** (len(raw) - 1 - cuts)
                             for cuts, value in enumerate(row['source_spectrum'])) for p in points]
        plotted = list(values)
        marks = []
        for p, observed in zip(points, weights):
            index = int(round(p * 200))
            assert abs(values[index] - observed) < 1e-10
            plotted[index] = observed
            marks.append(index)
        axis.plot(density, plotted, linestyle=linestyle, marker=marker,
                  markevery=marks, markersize=3, label=f'{width}-byte scalar')
        density_rows.extend([width, float(p), value] for p, value in zip(density, values))
    axis.set(xlabel='Independent cut probability', ylabel='Failing partition mass (%)',
             xlim=(0, 1), ylim=(0, 16))
    axis.legend(frameon=False, loc='upper right', fontsize=8)
    axis.spines[['top', 'right']].set_visible(False)
    fig.tight_layout(pad=.35)
    fig.savefig(figures / 'shadow-density.pdf')
    plt.close(fig)
    with (out / 'analysis/shadow-density.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['scalar_bytes', 'independent_cut_probability', 'failure_percent'])
        writer.writerows(density_rows)

    fig, axis = plt.subplots(figsize=(3.35, 2.25))
    for strategy, linestyle in [('fixed', '-'), ('state-feature-no-parser', '--'),
                                ('callback-aware', '-.'), ('two-obligation', ':')]:
        values = sorted(row['detected_ms'] for row in by_strategy[strategy]
                        if row['detected_ms'] is not None)
        x_values = np.geomspace(.04, 50, 220)
        y_values = [100 * np.searchsorted(values, threshold, side='right') /
                    len(by_strategy[strategy]) for threshold in x_values]
        axis.plot(x_values, y_values, label=LABEL[strategy], linestyle=linestyle)
    axis.set(xscale='log', xlabel='Warm discovery budget (ms)',
             ylabel='Detected eligible repeats (%)', ylim=(0, 100), xlim=(.04, 50))
    axis.set_xticks([.1, 1, 10, 50], [r'0.1', '1', '10', '50'])
    axis.legend(frameon=False, loc='lower right', fontsize=7.3)
    axis.spines[['top', 'right']].set_visible(False)
    fig.tight_layout(pad=.35)
    fig.savefig(figures / 'discovery.pdf')
    plt.close(fig)

    gate_timing = gate['timing']['summary']
    macros = {
        'PeakRSS': f"{resources['peak_rss_kib'] / 1024:.2f}",
        'AllUnits': summary['cohorts']['all']['units'],
        'StructuralUnits': summary['cohorts']['new-input-all-action']['units'],
        'AllPortfolio': f"{summary['cohorts']['all']['rates']['callback-aware']:.2f}",
        'AllFixed': f"{summary['cohorts']['all']['rates']['fixed']:.2f}",
        'StructuralPortfolio': f"{summary['cohorts']['new-input-all-action']['rates']['callback-aware']:.2f}",
        'StructuralFixed': f"{summary['cohorts']['new-input-all-action']['rates']['fixed']:.2f}",
        'TimePortfolio': f"{timing['callback-aware']['rates']['50']:.2f}",
        'TimeTwo': f"{timing['two-obligation']['rates']['50']:.2f}",
        'TimeFixed': f"{timing['fixed']['rates']['50']:.2f}",
        'TimeStateLean': f"{timing['state-feature-no-parser']['rates']['50']:.2f}",
        'ThreeTwo': f"{timing['two-obligation']['rates']['3']:.2f}",
        'ThreeFixed': f"{timing['fixed']['rates']['3']:.2f}",
        'StudyTime': f"{resources['wall_seconds']:.2f}",
        'CleanCampaign': f"{summary['clean_campaign_checks']:,}",
        'TwoWork': f"{timing['two-obligation']['mean_wall_ms']:.3f}",
        'FixedWork': f"{timing['fixed']['mean_wall_ms']:.3f}",
        'PortfolioWork': f"{timing['callback-aware']['mean_wall_ms']:.3f}",
        'StateLeanWork': f"{timing['state-feature-no-parser']['mean_wall_ms']:.3f}",
        'GateStreams': f"{gate['corpus_streams']:,}",
        'GateChecks': f"{gate['mode_summary']['gate']['checks']:,}",
        'GatePartitions': f"{gate['exhaustive']['partitions']:,}",
        'GateExecutions': f"{gate['exhaustive']['executions']:,}",
        'GateOverhead': f"{gate_timing['gate']['paired_median_overhead_percent']:.2f}",
        'GateAllOverhead': f"{gate_timing['gate_all']['paired_median_overhead_percent']:.2f}",
        'GateUnsafeMin': min(pair['unsafe_changed_streams'] for pair in gate['pairs']),
        'GateUnsafeMax': max(pair['unsafe_changed_streams'] for pair in gate['pairs']),
    }
    (generated / 'numbers.tex').write_text('\n'.join(
        '\\newcommand{\\' + key + '}{' + str(value) + '}' for key, value in macros.items()
    ) + '\n')
    print(json.dumps({'timing': timing, 'gate': gate['pairs'], 'macros': macros}, indent=2))


if __name__ == '__main__':
    main()
