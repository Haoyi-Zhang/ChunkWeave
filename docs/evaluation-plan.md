# Evaluation plan and method decisions

Recorded before constructing or scoring the 144-stream structural cohort on 4 October 2026. This is a local prospective design record.
This is a local prospective design record, not an independent preregistration.

Earlier pilot results informed the callback-aware portfolio. The structural cohort tests transfer to additional authored constructions; it is not an independently collected population.

## Scientific question
Characterize an opposite fragmentation effect to the silent-scalar law: a callback
can replace a decoder after it has consumed bytes that lie beyond the callback's
logical event. Derive a necessary-and-sufficient cut predicate and a cut-count
spectrum for LF-terminated data-only streams excluding payload U+FEFF and U+FFFD.
Check the formula against an exact full-state model, exhaustive short partitions,
and actual unchanged parser-source executions. The exclusions are part of the
law, not of the general empirical corpus.

## Frozen method
The obligation portfolio starts with bytewise input. In a single reference pass,
record complete event / accepted-retry callback offsets and scalar interior
positions. Keep the first representative for each (callback kind, UTF-8 width,
residual width, field context), round-robin across callback kinds. Test a single
cut after the callback inside an unfinished scalar, without an intervening cut.
Then test a bounded selection of two cuts enclosing a silent scalar fragment.
Use the original fixed-size sequence to fill the remaining 16-schedule cap.
No SUT response or control identifier is consulted by construction. The two-test
ablation is bytewise plus the first available shadow cut. A no-shadow ablation
retains silent-gap obligations but removes callback-spanning cuts.

## Evaluation
Keep the pre-existing reference cohort retrospective. Generate 144 new streams in
eight specified structural families, 18 variants each: progress JSON, retry
cycles, data whitespace, long callback tails, metadata-only blocks, incomplete
suffixes, mixed endings, and Unicode planes. Deduplicate against all prior bytes.
The new cases are authored in the same workflow, not independent production data.
Use all eight prior controls plus parser replacement on events, decoder replacement
on retry callbacks, and parser replacement on retry callbacks. These are controlled boundary-action variants, not mined defects or independent library bugs.
An empty-decoder-output-skipping composition is an additional benign control.

Compare fixed, bytewise, uniform random, bytewise plus sparse random, the state-feature selector, its no-parser-tag ablation, the callback-aware portfolio, the two-obligation policy, and the no-shadow ablation. Cap at 16 unique schedules, retain actual
counts, use three seeds for random policies, exclude whole-semantic failures.
Report results separately for old/new cases and old/new control actions; additionally
report per-control results rather than only a pooled rate. Source consistency
checks share exactly the same schedule set across the four existing configurations.
Use balanced repeated warm discovery timing, retaining all non-detections.
No run-time budget is permitted to count results completed after its threshold.

## Scope
All streams valid UTF-8, <=64 KiB; no remote experiments, malformed inputs, attacks,
load generation, production data, paid services, credentials or model APIs.
Browser unavailable is recorded as unavailable, not emulated or bypassed.
EOF is not a forced event dispatch. A graph UNKNOWN is not a passing result.
