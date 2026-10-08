# Executed integration and observation contracts

| Integration | Actual input boundary | Upstream code executed | Added observation/integration logic | Excluded claims |
|---|---|---|---|---|
| eventsource-parser 4.1.1 | Exact authored byte slices, then a persistent Node TextDecoder | Unmodified parse.ts and errors.ts from v4.1.1 | Sticky last-event ID via onId; type default; separate retry and diagnostics | No full npm/Vitest run, network, reconnection or browser guarantee |
| httpx-sse 0.4.3 source adapter | Exact authored byte slices, then Python utf-8-sig incremental decoding | Unmodified SSELineDecoder, SSEDecoder, ServerSentEvent | Observe a one-bit data-field flag to project metadata-only objects out of MessageEvent equality; retain raw objects; commit ID on blank; inspect retry state | This exact-slice adapter does not exercise automatic retries; separate upstream API tests use HTTPX MockTransport |
| fetch-event-source 2.0.1 | Exact controlled ReadableStream byte slices | Original getBytes/getLines/getMessages at pinned 2021 revision | Raw objects, accepted-data flag, actual ID/retry updates | No full fetch/reconnection wrapper, source payload repair or maintenance claim |
| Node 22.16.0 native EventSource (Undici 6.21.2) | Local HTTP request; requested server writes | Runtime's native EventSource | Collect default/declared event types and lastEventId; close on first EOF/error before retry | Server write boundaries are NOT known client chunk partitions; not a headless browser |

## Exact byte-parser and source-observer details

The added independent byte-parser family is not another
JavaScript configuration. `fetch-event-source` 2.0.1's original `getBytes`, `getLines`
and `getMessages` process controlled `ReadableStream` byte slices. The observer follows
actual accepted colon-delimited data fields, retains raw objects and persistent delivery
ID, and does not repair empty-data joining, BOM handling or retry values. The full
fetch/reconnection wrapper is not executed.

Two eventsource-parser configurations are retained: `correct` uses default TextDecoder
BOM stripping; `bom_owned` uses `ignoreBOM:true` and leaves exactly one leading BOM to
the parser. The former is retained as the originally authored composition, not described
as semantically correct on the newly added double-BOM literal. Python retry observations
now follow actual `_retry` assignments rather than treating every retained value as a
new update. Underlying source modules remain unchanged.

The JavaScript decoder is persistent and uses `decode(chunk, {stream:true})`, followed by a final decoder flush. No artificial parser blank line is supplied. The Python line decoder may defer a trailing CR; only a real held CR is flushed as a line terminator. An ordinary incomplete tail is not forced into an event. The JavaScript parser's onId is called at a blank separator, allowing ID-only blocks to update application state without fabricating data events.

The Python upstream decoder emits objects for some metadata-only blocks. Dropping such an object with an observed `has_data` bit is a declared **projection**, not evidence that the upstream object's existence is a defect. Raw objects are returned by the adapter. This observer sees actual line-decoder output, does not query the reference result, does not invent payloads, and does not repair Unicode. Access to private decoder members is version-specific and is a material adapter limitation.

Diagnostics are omitted from equality because unknown-field/comment callbacks are optional and not SSE MessageEvents. The full actual replay includes JavaScript diagnostics. No parser maxBufferSize setting was imposed; the harness independently bounds complete input sizes. EOF, reconnection, origins and transport retries are not normalized to pretend unlike APIs share an identical full contract.

## Controlled integration actions

`stateless_utf8` creates a decoder per byte chunk; `reset_parser` resets the parser at each subsequent feed; `empty_reset` resets the parser when nonempty bytes yield empty text; `leading_trim` trims the leading whitespace of subsequent decoded chunks; `newline_each_feed` adds a newline at feed ends; `crlf_chunk_normalize` normalizes CR/LF independently in each text fragment; `id_per_chunk` resets adapter ID state at each new chunk; `decoder_per_event` replaces the decoder inside the event callback. Controls change local integration logic, never upstream source. They were defined before the full run and were not selected from confirmed real library defects.

`decoder_per_event` can lose pending decoder state when a single decoded fragment both completes an event and leaves the bytes of a later scalar incomplete. Dense fragmentation can avoid this span and therefore is not monotonically stronger. The control is a mechanism probe, not a frequency model of production code.


## Callback actions and benign configuration

`skip_empty` uses the single-BOM-owner composition and skips calls to the string
parser when persistent decoding yields empty text. It is a fifth configuration,
not a fourth independent parser family. Original empty-text behavior remains.
Three additional authored actions replace the parser after event delivery,
replace the decoder at an accepted-retry callback, or replace the parser at that
retry callback (`parser_per_event`, `decoder_per_retry`, `parser_per_retry`).
They are controlled boundary-action variants, not asserted historical library defects.
Callbacks are synchronous in the examined source integration. The decoder processes
all bytes in the current chunk before text parsing invokes them. This order,
and the action's exact ownership/lifetime, is essential to the shadow theorem.
The reference projection identifies callback offsets without consulting any
control result or changing source-returned payloads.
