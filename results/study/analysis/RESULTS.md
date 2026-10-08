# ChunkWeave measured results

This directory is the primary executed evidence. Inputs are valid, bounded local fixtures. An eligible unit is a stream/action pair that passes the whole-input semantic precheck; unsensitized actions remain in the denominator.

## Detection at a shared cap of sixteen distinct schedules

| Policy | All 5,104 units | Structural cohort, 1,572 units |
|---|---:|---:|
| Fixed sizes | 75.00% | 65.08% |
| Bytewise only | 56.90% | 48.66% |
| Uniform random | 65.62% | 58.42% |
| Bytewise + sparse random | 75.40% | 64.97% |
| State-feature selector | 65.85% | 61.70% |
| State selector without parser tags | 78.35% | 70.42% |
| Callback-aware portfolio | 78.57% | 70.42% |
| Two-obligation policy | 77.39% | 70.42% |
| No-shadow ablation | 71.55% | 65.08% |

The two-obligation policy uses at most two schedules. On the structural cohort it matches the full callback-aware portfolio and the state selector without parser tags at 70.42%. Across all units, the portfolio reaches 78.57%, fixed sizes 75.00%, and the strong state baseline 78.35%. Three random seeds are averaged inside each unit.

Reference/base-action units: 2,560; structural/base-action: 1,140; reference/callback-action: 972; structural/callback-action: 432. Forty-four whole-input-invalid units are excluded from 5,148 potential combinations.

## CommitGate

| Trigger | Immediate: changed streams | Immediate: mismatch checks | Guarded: changed streams | Guarded: mismatch checks |
|---|---:|---:|---:|---:|
| Decoder / Event | 375 | 1,434 | 0 | 0 |
| Parser / Event | 430 | 6,786 | 0 | 0 |
| Decoder / Retry | 286 | 1,587 | 0 | 0 |
| Parser / Retry | 319 | 6,635 | 0 | 0 |

Every guarded mode preserves the oracle over 537 streams and 10,823 schedules per mode. The exhaustive audit covers 524,288 partitions and 2,097,152 gated executions with zero failures. Median overhead is 6.56% for the gate and 15.09% when all four replacement requests are enabled.

## Repeated, rank-balanced warm discovery

| Policy | Detected by 3 ms | Detected by 50 ms | Mean consumed work (ms) |
|---|---:|---:|---:|
| Fixed sizes | 65.74% | 71.73% | 1.078 |
| Bytewise only | 51.28% | 55.52% | 0.556 |
| Uniform random | 59.66% | 63.78% | 1.418 |
| Bytewise + sparse random | 67.34% | 71.89% | 0.990 |
| State-feature selector | 55.29% | 61.55% | 2.798 |
| State selector without parser tags | 65.88% | 75.00% | 1.316 |
| Callback-aware portfolio | 70.56% | 75.00% | 1.011 |
| Two-obligation policy | 68.69% | 73.20% | 0.704 |
| No-shadow ablation | 61.37% | 68.36% | 1.193 |

The timing study contains 81 inputs, 888 eligible units, five repeats, nine policies, and 39,960 runs. Timers include lazy construction, warm IPC, and source execution. Common oracle/precheck work and startup are excluded; all non-detections remain in the denominator.

## Source configurations

| Configuration | Streams | Checks | Whole-input differences | Partition-changed streams |
|---|---:|---:|---:|---:|
| js-default | 537 | 10,823 | 1 | 0 |
| js-single-bom-owner | 537 | 10,823 | 0 | 0 |
| js-skip-empty | 537 | 10,823 | 0 | 0 |
| azure-source | 537 | 10,823 | 105 | 0 |
| python-source | 537 | 10,823 | 3 | 0 |

These rows represent three independently implemented parser families and five configurations. Whole-input contract differences are retained and are not counted as segmentation findings.

## Exact and regression checks

The callback-shadow law matches 229,376 exhaustively executed partitions; the full source audit contains 237,700 executions. All seven analytical spectra match the complete-state model counts.

The bounded-state projection matches 945,349 byte prefixes and 69,975 selected schedules on 2,734 inputs.

Cut-only reduction produces 64 byte-preserving witnesses, all replayed and freshly checked for deletion-1 minimality.

The local test suite has 57 passing tests plus 7 subtests. 58 unchanged upstream httpx-sse tests pass. The included ASGI test requires an unavailable optional dependency.

## Resources and limits

The campaign has 6,084 records, 997,104 scheduled mode executions, and 54,115 source checks. An additional 83,092 clean checks have zero semantic disagreements.

Campaign wall time: 154.78 s; Python 3.13.5; Node v22.16.0; Python peak RSS 167.78 MiB. Inputs are capped at 65,536 bytes; the largest stream is 60,145 bytes.

The browser pilot is recorded as blocked before a localhost request, so it contributes no browser observation. Theorems, exact-state results, and source experiments retain their stated and separate scopes.
