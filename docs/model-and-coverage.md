# Model, coverage and proof scope

A partition is a strictly increasing list of interior byte offsets. No bytes are changed, omitted or reordered. A stream of n bytes has 2^(n-1) partitions; all single cuts enumerate only n-1 of these. Positive-length input pieces may decode to an empty string.

For the formal model, one-byte transition folding preserves the same concrete state and output whether folds are grouped into chunks or not. The proof assumes deterministic byte/character transitions, persistent decoder/parser buffers, feed(empty) as a no-op, identical finalization, and no application mutation of state at feed or event boundaries. Induction on bytes gives grouping invariance. This is not a proof of those assumptions for any third-party implementation.

The finite coverage feature at a cut uses remaining UTF-8 continuation count, pending-CR state, field phase, nonempty data/type/ID buffers, whether an event has been emitted, and initial-BOM status. Concrete string values are omitted. Consecutive cuts at most 32 bytes apart and within the same/adjacent block add a pair class: silent decoded interval, within-line, line-crossing, or block-crossing, plus selected endpoint states. Inserting a cut can destroy a previously adjacent pair. Thus feed density is not monotonic for this criterion.

The universe enumerates every interior seam and eligible nearby pair in the concrete reference trace. This enumeration is coverage instrumentation, charged separately from generation. The 16-schedule method uses first/middle/last representatives by state, a cap of 192 seam representatives, nearby representative pairs and silent-interval witnesses, then greedily maximizes additional class coverage. The reference trace and greedy work are charged to its scheduling time. A candidate witness may cover up to two seam classes and one pair class; 16 schedules need not cover a universe of hundreds of classes.

No state-equivalence, bisimulation, transition-congruence or representative-set completeness result is established. The actual measured coverage is reported, including uncovered classes. Payload-sensitive logic and history beyond the abstract state can distinguish two representatives. The model argument proves grouping invariance only for the specified fold implementation; the empirical study concerns other, explicitly pinned integrations.

## Test count, coverage and consumed work

The at-most-two-partition guarantee is conditional on the single-scalar
empty-reset family and the data-only decoder-per-event profile. It is a bound on
test count, not on feed calls or execution time: bytewise input makes n feeds.
Outside those profiles, two obligations and the sixteen-schedule portfolio are
empirical selectors, not completeness guarantees. Feature-class coverage and
the rate of detected eligible stream/action units are also different quantities.

In the retained warm timing records, two obligations use 0.704461 ms mean
consumed work per unit/repeat, the lowest mean among the compared multi-schedule
policies. Bytewise-only is cheaper at 0.556413 ms, but detects 55.52% by 50 ms
versus 73.20% for two obligations. The full portfolio and reduced-tag state
selector each reach 75.00% at that threshold with more mean consumed work.
Thus the intended comparison is a detection-versus-work tradeoff, not an
unqualified least-work ranking over all nine policies. These rates include all
eligible repeats, including non-detections; consumed work includes lazy
construction, warm IPC and source execution, but excludes common prechecks and
startup. These values describe the retained records, not new timing runs.

## Minimal two-cut example

Use the valid 10-byte stream `data:` + UTF-8 U+4E2D + LF LF. The expected data is the single U+4E2D scalar. The authored empty-reset integration agrees for the whole buffer and all nine one-cut schedules. Splitting at offsets 6 and 7 yields chunks `[data: E4] [B8] [AD LF LF]`. The middle byte produces no decoded character while the parser still holds `data:`. Resetting the parser at that point loses the field prefix. Exactly two cuts are sufficient; exhaustive enumeration confirms no one-cut witness and 256 failing partitions among the 512 total partitions of this stream. This is a local functional control, not an upstream vulnerability or discovered package bug.

The reducer deletes only cuts, leaving stream bytes and standard semantics unchanged. It applies ddmin-style deletion and explicitly checks all one-cut deletions of the result. The result is 1-minimal, not necessarily globally minimum. Reduction is scoped to whole-buffer-conforming controls and a segmentation-induced discrepancy.
