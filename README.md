# ChunkWeave executable artifact

This directory contains the semantic oracle, bounded models, source adapters, schedule policies, CommitGate, tests, corpus, raw results, and regeneration scripts.

## Environment

The retained primary execution used Python 3.13.5 and Node 22.16.0. Use the pinned Node version when comparing fault-injection outcomes: decoder behavior can change between runtime versions. Dependency files are separated by purpose:

- `requirements-core.txt`: core adapters and CLI;
- `requirements-analysis.txt`: analysis and vector plot generation;
- `requirements-upstream.txt`: unchanged upstream Python tests;
- `requirements-browser.txt`: optional browser pilot dependencies.

The experiments themselves make no remote requests.

## Fast checks

```sh
PYTHONPATH=. python -m pytest tests -q
PYTHONPATH=. python -m chunkweave.audit   --file examples/progress.sse --out results/my-smoke.json
node --check chunkweave/node_worker.mjs
node --check chunkweave/commit_gate.mjs
```

## Complete bounded reproduction

Choose a new output directory; the driver refuses to overwrite an existing run.

```sh
PYTHONPATH=. python scripts/reproduce.py   --out results/my-run --paper ../paper
```

The driver runs local tests, bounded-state projection, the main campaign, exact boundary-law checks, rank-balanced timing, available unchanged upstream tests, witness reduction, analysis, CommitGate evaluation, and a CLI smoke test. With the optional companion `paper/` directory it also builds the anonymous manuscript. Published code alone can run without a manuscript or a TeX installation.

Compare the new run with the retained primary run:

```sh
PYTHONPATH=. python scripts/compare_reproduction.py   --primary results/study   --replay results/my-run   --out results/my-run-audit.json
```

## Regenerate manuscript data

```sh
PYTHONPATH=. python scripts/generate_paper.py   --out results/study --paper ../paper
```

This regenerates numeric macros, table snippets, CSV files, and vector plots. Plot labels use pdfLaTeX and the manuscript's Libertine font; pdfLaTeX must be on PATH for this optional step. The conceptual callback diagram remains editable TikZ in `../paper/figures/shadow.tex`. A change of host can change timing results; review the accompanying statistical prose when replacing primary measurements.

## Results layout

- `results/study/`: primary executed evidence.
- `results/study/analysis/RESULTS.md`: concise human-readable result table and exact denominators.
- `results/study/campaigns.jsonl.gz`: policy/control records.
- `results/study/sources.jsonl.gz`: exact source-configuration records.
- `results/study/timing.jsonl.gz`: rank-balanced warm timing records.
- `results/study/commit-gate/`: gate observations, exhaustive audit, and timing.
- A reproduction creates the separate output directory chosen with `--out`; its observations and timings are not pooled with the primary run.

## Safety and bounds

All inputs are valid UTF-8, local, and no larger than 65,536 bytes. The graph check has byte, node, edge, and elapsed-time caps and returns `UNKNOWN` when a cap is reached. The browser pilot is not part of the passing evidence because local navigation was administratively blocked before any request.
