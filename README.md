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
PYTHONPATH=. python -B scripts/interaction_law.py
PYTHONPATH=. python -m chunkweave.audit   --file examples/progress.sse --out results/my-smoke.json
node --check chunkweave/node_worker.mjs
node --check chunkweave/commit_gate.mjs
node --no-warnings --experimental-transform-types --test tests/test_commit_gate_stream.mjs
```

The standalone silent-fragment checker uses Python's standard library and the
local Node worker, without importing the optional HTTPX adapter. Its regression
tests and the synthetic summary-statistic tests can also run without pytest:

```sh
PYTHONPATH=. python -B -m unittest discover -s tests -p test_interaction_law.py -v
PYTHONPATH=. python -B -m unittest discover -s tests -p test_result_summary.py -v
```

## Complete bounded reproduction

Choose a new output directory; the driver refuses to overwrite an existing run.

```sh
PYTHONPATH=. python scripts/reproduce.py   --out results/my-run --paper ../paper
```

The driver runs local tests, bounded-state projection, the main campaign, exact boundary-law checks, rank-balanced timing, available unchanged upstream tests, witness reduction, analysis, CommitGate evaluation, and a CLI smoke test. With the optional companion `paper/` directory it also builds the anonymous manuscript. Published code alone can run without a manuscript or a TeX installation.

The silent-fragment check writes `interaction-law.json` for 1,792 partitions of
three single-scalar inputs. The distinct callback-shadow check writes
`shadow-law.json`; it does not substitute for the silent-fragment law.

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

## Summary statistics from retained records

CommitGate headline overhead is the median of the paired per-workload values
`100*(mode/bom_owned - 1)`, paired by case, schedule index and repeat. On the
1,295 retained paired workloads this gives 21.92% for the gate and 42.46% for all
four replacement requests. The different ratios of pooled medians,
`100*(median(mode)/median(bom_owned) - 1)`, are 6.56% and 15.09%. The retained
`results/study/analysis/RESULTS.md` now labels both statistics separately. Its
campaign and test counts describe retained records, not a current campaign rerun.

Generate a new labelled summary without changing those retained files:

```sh
PYTHONPATH=. python -B scripts/write_results.py --out results/study --report results/my-summary.md
```

`--out` selects the existing records; `--report` selects a new Markdown output
and refuses an existing file. The generator recalculates both overhead statistics
from `commit-gate/timing.json` and rejects incomplete or duplicate pairs, invalid
timings, and nonfinite derived statistics rather than silently dropping them.
This is reanalysis, not new measurement. See
`docs/model-and-coverage.md` for the distinction between conditional test-count
coverage and measured detection-versus-work comparisons.

## Safety and bounds

The fixture campaign uses valid local UTF-8 inputs no larger than 65,536 bytes. The graph check has byte, node, edge, and elapsed-time caps and returns `UNKNOWN` when a cap is reached. The browser pilot is not part of the passing evidence because local navigation was administratively blocked before any request.

## Gate refinement and stream interface

`chunkweave/commit_gate.mjs` now exports `createCommitGate` as well as the original
bounded `executeCommitGate` wrapper. Use `push(Uint8Array)` followed by `finish()`
for a synchronous stream. `collect:false` and `onEvent`/`onRetry`/`onError` sinks
avoid retained output histories; the caller remains responsible for its own sink
memory and flow control. Requests through `requestDecoderReplacement()` and
`requestParserReplacement()` commit at scalar and blank-line boundaries. Sinks
must not reenter push/finish. A sink, decoding, or limit error ends the session;
delivered events are not rolled back. Each push is capped at 64 KiB; configured
unfinished-line and canonical-block limits default to 65,536 UTF-16 characters.
Total input need not be collected or capped. EOF adds no separator.

Fatal UTF-8 decoding remains active. After decoding validates a chunk, residual
tracking inspects at most four tail bytes. Complete-line batches stop at each
blank separator before applying a parser replacement. The preserved
`commit_gate_reference.mjs` is the original gate, with only its exported function
renamed, and is a contract-matched benchmark baseline. The direct fatal-decoder
baseline has no replacement contract. `batchLines:false` supplies a line-only
ablation without disabling decoding checks or commit rules.

The supplementary records at `results/gate-refinement/` contain
8,640 warm measurements on 94 streams/240 workloads, 36 fresh-process cold
measurements, single-pass work counts, and a fresh exhaustive result. They used
Node 24.19.0 on Windows x64 and must not be pooled with the original Node
22.16.0 results. Median paired warm time decreases by 10.03% (base) and 9.42%
(all requests) against the original gate. Cold first execution is not improved,
and overhead over the direct no-replacement cost floor remains. The original
21.92%/42.46% headline measurements above are retained historical measurements,
not timings of the refined implementation.

Run a new comparison and regenerate its supplementary table, without compiling:

```sh
node --no-warnings --experimental-transform-types scripts/benchmark_commit_gate.mjs results/my-gate-refinement
python -B scripts/summarize_gate_refinement.py --out results/my-gate-refinement --paper ../paper
```

The benchmark refuses an existing output directory and stays under artifact
`results/`. This experiment selects inputs and schedules without fault outcomes.
It does not rerun or replace the controlled detection campaign. That campaign's
strongest comparison is 4,010 versus 3,999 detected units: eleven additional
detections (0.216 percentage points), none on the structural cohort, with zero
observed partition-induced variation in any unmodified source configuration.
