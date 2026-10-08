"""Run the bounded local study from source without remote requests."""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('results/reproduction'))
    parser.add_argument('--paper', type=Path, default=None,
                        help='optional paper directory for data generation and PDF builds')
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('Refusing to overwrite an existing result directory')
    args.out.mkdir(parents=True)
    started = time.perf_counter()
    env = dict(os.environ, PYTHONPATH='.')
    steps: list[dict] = []
    commands = [
        ('tests', [sys.executable, '-m', 'pytest', 'tests', '-q'], 90),
        ('projection', [sys.executable, 'scripts/projection_audit.py', '--out', str(args.out / 'projection-audit.json')], 90),
        ('study', [sys.executable, 'scripts/study.py', '--out', str(args.out)], 960),
        ('boundary-laws', [sys.executable, 'scripts/shadow_audit.py', '--out', str(args.out / 'shadow-law.json')], 120),
        ('timing', [sys.executable, 'scripts/measure_timing.py', '--out', str(args.out / 'timing.jsonl.gz')], 420),
        ('upstream', [sys.executable, 'scripts/upstream_check.py', '--out', str(args.out)], 90),
        ('reduction', [sys.executable, 'scripts/reduce_witnesses.py', '--out', str(args.out)], 180),
        ('analysis', [sys.executable, 'scripts/analyze_study.py', '--out', str(args.out)], 90),
        ('commit-gate', [sys.executable, 'scripts/commit_gate_audit.py', '--out', str(args.out / 'commit-gate'), '--repeats', '5'], 240),
        ('report', [sys.executable, 'scripts/write_results.py', '--out', str(args.out)], 60),
        ('cli', [sys.executable, '-m', 'chunkweave.audit', '--file', 'examples/progress.sse', '--out', str(args.out / 'cli-smoke.json')], 60),
    ]
    if args.paper is not None:
        commands.extend([
            ('paper-figure', ['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error', 'shadow.tex'], 180),
            ('paper', ['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error', 'main.tex'], 180),
        ])
    for name, command, timeout in commands:
        step_started = time.perf_counter()
        cwd = (args.paper/'figures' if name=='paper-figure' else args.paper) if name.startswith('paper') else Path('.')
        log_path = args.out / f'{name}.log'
        with log_path.open('w', encoding='utf-8') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    env=env, cwd=cwd, timeout=timeout)
        steps.append({
            'step': name,
            'returncode': result.returncode,
            'seconds': time.perf_counter() - step_started,
            'command': command,
        })
        state = {'status': 'running' if result.returncode == 0 else 'failed', 'steps': steps}
        (args.out / 'reproduction.json').write_text(json.dumps(state, indent=2) + '\n')
        print(name, result.returncode, round(steps[-1]['seconds'], 2), flush=True)
        if result.returncode:
            raise SystemExit(f'Failed step: {name}')
    report = {
        'status': 'completed',
        'steps': steps,
        'wall_seconds': time.perf_counter() - started,
        'python': platform.python_version(),
        'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'scope': 'bounded local execution; unavailable optional browser evidence is not counted',
    }
    (args.out / 'reproduction.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['wall_seconds'])


if __name__ == '__main__':
    main()
