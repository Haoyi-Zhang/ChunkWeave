# Silent-scalar cut interaction law

Let `b = ASCII("data:") || UTF8(c) || LF || LF`, where `c` is one Unicode scalar
of width w in {2,3,4}, excluding U+FEFF and U+FFFD as in the theorem. The local
control retains a streaming UTF-8 decoder but resets the SSE string parser after
a nonempty byte chunk yields no characters.
The expected event contains exactly c. Let C be a subset of interior byte offsets.

**Claim.** This control changes the event sequence iff C contains at least two
offsets from W={5,...,5+w-1}. Consequently every single-cut partition passes,
minimum failing cut count is two, and exactly (2^w-w-1)*2^6 of the 2^(w+6)
partitions fail. Under independent equiprobable cuts the failure probability is
1-(w+1)/2^w. These are counts for this family/control, not independent faults.

**Proof.** Every chunk containing an ASCII byte produces nonempty decoded text.
Every chunk containing the final byte of c completes c and also produces
nonempty text. Therefore the only possible empty-output nonempty chunk lies
strictly within the not-yet-completed scalar, and its two endpoints belong to W.
Such a chunk exists exactly when at least two cuts lie in W: two consecutive
selected W positions have no selected cut between them outside W. At that point
the ASCII `data:` prefix has been delivered in earlier chunks and is buffered by
the parser. A reset removes it; when the scalar completes, the resulting line
has no recognized data field. No later field can restore it. Thus no event is
emitted. Conversely, in the absence of such a chunk no reset takes place and the
retained decoder/parser deliver c. There are 2^w subsets of W, of which exactly
1+w have fewer than two cuts. The other six positions can be chosen freely.
The witness {5,6} exists for every permitted width, establishing minimality.

`scripts/interaction_law.py` exhaustively compares the closed form, the separately
implemented Python functional model (`chunkweave.quotient.execute`) and the
actual vendored-source integration (`empty_reset` in `node_worker.mjs`).
Neither implementation generates its observation from the cut predicate.
The oracle is checked against the literal expected event. Every partition also
checks the clean model and single-BOM-owner source integration.

| Representative | UTF-8 width | Partitions | Failing partitions |
|---|---:|---:|---:|
| U+00E9 | 2 | 256 | 64 |
| U+4E2D | 3 | 512 | 256 |
| U+1F30D | 4 | 1,024 | 704 |

The 1,792 partitions yield 3,584 source executions and 3,584 model executions
when the clean and controlled modes are counted separately. The audit compares
failure histograms by cut count, checks whole-input conformance and all single
cuts, and verifies bytewise failure and minimum failing cut count two.
Disagreements produce a failed result with a mismatch count and bounded
observation examples, not a passing label.

From `artifact/`, run `PYTHONPATH=. python -B scripts/interaction_law.py` for JSON
on stdout, or add `--out results/my-silent-law.json` for a new file. Existing
output files are refused. The reproduction driver writes `interaction-law.json`
in its new run directory; its separate callback-shadow step still writes
`shadow-law.json` using `scripts/shadow_audit.py`. The two actions and laws are
not interchangeable.

The choice of scalar within a width does not affect the proof; the executable
audit samples one scalar per width and exhausts its partitions, rather than
claiming to execute all Unicode or rerun the full detection/timing campaign.
This is a specialized interaction characterization. It is not a universal
completeness theorem for SSE libraries or arbitrary callbacks.
