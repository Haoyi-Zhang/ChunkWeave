# Analysis plan and prior-work boundary

The pilot executed eventsource-parser 4.1.1 and httpx-sse 0.4.3 source-level adapters.
A native Node 22.16.0 EventSource localhost pilot also executed. Chromium navigation
was blocked by the environment's administrator policy; no browser observations
are available. The native Node observation does not replace a browser observation.

## Advance and prior-work boundary

The WHATWG HTML SSE and Encoding specifications define a composed byte-to-event
problem, not a requirement to make a string-only parser decode bytes. Existing
upstream tests already exercise fragmented strings AND empty decoder output at a
split leading BOM: eventsource-parser 4.1.1 test/parse.test.ts lines 153--286.
Therefore neither random fragmentation nor BOM/empty-string testing is claimed
as a new technique. WPT eventsource/event-data.any.js checks multiline data,
unknown/case-sensitive fields, and an empty-data event using resources/message2.py.
The artifact ports one bounded iteration, not the infinite endpoint or full WPT
harness. The standard's final-incomplete-block semantics remain separate.

Kuhn et al., ICST 2012, DOI 10.1109/ICST.2012.147, cover t-way orders of events,
including interleaving. Here bytes retain their original order; only feed cuts
change. Consecutive cut intervals matter because an intervening output-producing
chunk can invalidate an empty-output/carry witness. Fu et al., arXiv:2412.20692v1,
measure association of input tests with k metamorphic relations. Here one primary
segmentation relation is checked against independent normative outputs and a
specific decoder/line/block boundary abstraction. No general new MT adequacy
framework is claimed. Zeller and Hildebrandt's ddmin (10.1109/32.988498) motivates
cut deletion; keeping bytes unchanged preserves semantics by construction.

Concrete advance to evaluate: state-labelled *consecutive* cut witnesses; an
explicit two-cut counterexample to the sufficiency of all single cuts; contract-
aware observations; and measured cost/detection tradeoffs against strong dynamic
baselines. The outcome may be a negative result for the scheduler. An improvement,
a maintained-library defect, and a universal representative-set theorem are NOT
requirements. No author or maintainer endorsement is claimed.

## Fixed design

240 authored cases: 12 named payload families x 20 semantic variants. The first
8 families are development, the last 4 are payload-family holdouts. Additional
normative/upstream fixtures, tiny exhaustive partition cases and a long-stream
cohort are separate. No production traffic or external service is used.

Eight explicitly authored faulty integration controls, fixed before evaluation:
stateless_utf8, reset_parser, empty_reset, leading_trim, newline_each_feed,
crlf_chunk_normalize, id_per_chunk, decoder_per_event. They are not upstream
regressions or a sample of real-world fault prevalence. Whole-buffer failing
units are excluded from the segmentation-detection denominator and reported.

Each budgeted nontrivial strategy uses at most 16 DISTINCT schedules per stream.
Whole-buffer is an extra common precheck. Full single-cut enumeration is reported
separately; the budgeted single-cut baseline uses evenly spaced cuts. Fixed sizes
are 1,2,3,4,5,7,8,11,16,23,32,47,64,97,128,257. Uniform partitions independently
cut each interior gap with probability 1/2. Sparse random chooses 1--3 cuts.
The proposed scheduler uses a prefix model to label single seams and adjacent
seam pairs; selects a small candidate set greedily by new obligations; and fills
unused slots with noncritical single-cut controls. Ablations remove decoder
awareness, parser context, or pair schedules. A cut-deletion reducer has a final
single-removal audit (1-minimal, not globally minimum).

Measurements include event agreement separately from retry/ID control state,
whole-buffer versus segmentation discrepancy, observed semantic coverage,
feed calls, scheduler and execution time, first discovery, reduced cut count,
and process resources. Exact adapters and localhost requested writes are never
pooled as exact partitions. Holdout results remain visible, with cluster-based
uncertainty across authored families rather than across repeated schedules.
