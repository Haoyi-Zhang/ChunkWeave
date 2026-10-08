# Semantic profile v1

Normative basis read during preparation: WHATWG HTML, Server-sent events, sections 9.2.5 (parsing) and 9.2.6 (interpretation), and the WHATWG Encoding UTF-8 decoder / UTF-8 decode algorithm. Retrieval review date: 2026-10-03; the execution host recorded 2026-10-02 UTC. These are living specifications, not a claim that a complete archival standards snapshot is included.

- HTML: https://html.spec.whatwg.org/multipage/server-sent-events.html#parsing-an-event-stream
- HTML interpretation: https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation
- Encoding: https://encoding.spec.whatwg.org/#utf-8-decoder
- Encoding BOM handling: https://encoding.spec.whatwg.org/#utf-8-decode

## Profile and comparison object

Inputs are valid UTF-8, at most 65,536 bytes. Numeric retry values are at most 60,000 ms and at most six ASCII digits. A retry callback is metadata, not a request to sleep/reconnect. The recorded corpus includes at most one initial BOM; interior FEFF is ordinary payload. Malformed UTF-8, incomplete UTF-8 at EOF, repeated leading BOM composition, non-ASCII/signed retry metadata and configured parser-size-limit behavior are outside the evaluated profile. The corpus is finite, versioned and enumerated; accepting other inputs in a helper does not imply their validation.

The primary event observation is the ordered sequence `(type, data, lastEventId)`. Type defaults to `message`; data is exact Unicode text including interior newlines; IDs retain or reset according to input fields. Declared control observations are the retry-value sequence and last ID committed at a blank separator, where exposed. Origin is constant in each local native run and excluded from cross-adapter comparison. Timing, comments and optional diagnostics are not events.

Bytes, decoded Unicode chunks, lines and events are separate layers. A nonempty byte chunk may produce no Unicode. Three line endings are supported: LF, CR and CRLF. A CRLF straddling feeds remains one terminator. Comments and unknown fields do not dispatch. The first colon splits a field; exactly one immediately following ASCII space is removed. Repeated data fields insert LF; an empty data field still contributes a line. Blank blocks with no data do not dispatch, while a data field with empty value can dispatch an empty-data event. EOF does not supply a missing blank separator. A terminated field or an unterminated final line is not forcibly dispatched.

ID fields containing NUL are ignored; an empty ID field resets the buffer; the committed ID persists between events. Event type does not persist after a blank separator, including a no-data block. The application string `[DONE]` is normal data in this study and does not terminate SSE.

## Two different oracle implementations

`oracle.py` first uses whole-input strict UTF-8 decoding and then a regular expression to enumerate terminated lines. `model.py` uses a valid-only byte DFA, scalar-by-scalar CR/LF processing and a string data buffer. The model does not import codecs, regular expressions, or the reference evaluator. Upstream literal expected-data examples check both, and the short cases enumerate every partition. Both implementations were nevertheless prepared in the same AI-assisted workflow; algorithmic independence is not independent human validation. Agreement may preserve a shared misunderstanding.

The model does not implement invalid-byte replacement/error recovery. Profile membership is checked by the evaluation's reference entrypoint. This is not a general-purpose replacement for a browser decoder.
