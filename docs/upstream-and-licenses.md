# Sources, pins, ports and licenses

## Executed source modules

- eventsource-parser **v4.1.1**, rexxars/eventsource-parser: `src/parse.ts`, `src/errors.ts`. MIT; upstream LICENSE retained in `vendor/eventsource-parser-4.1.1/LICENSE`. Source retrieved through the connected GitHub file API; executable files were copied verbatim, not rewritten approximations. The included package.json is an authored ESM marker. The type-only import is erased at execution.
  - https://github.com/rexxars/eventsource-parser/tree/v4.1.1/src
  - https://github.com/rexxars/eventsource-parser/blob/v4.1.1/LICENSE
- httpx-sse **0.4.3**, florimondmanca/httpx-sse: `src/httpx_sse/_decoders.py`, `_models.py`. MIT; upstream LICENSE retained in `vendor/httpx_sse/LICENSE`. The artifact also includes the unchanged upstream `_api.py`, `_exceptions.py` and full `__init__.py`, replacing the old authored empty namespace marker. Exact file locators are in `upstream-source-files.json`; available upstream API tests execute through HTTPX MockTransport, without external traffic.
  - https://github.com/florimondmanca/httpx-sse/tree/0.4.3/src/httpx_sse
  - https://github.com/florimondmanca/httpx-sse/blob/0.4.3/LICENSE
- Node **22.16.0**, built-in Undici **6.21.2**. Runtime metadata is in results/native-e2e.json. No Node/Chromium executable is redistributed. Legal retrieval: official Node 22.16.0 release distributions and source.
  - https://nodejs.org/download/release/v22.16.0/
  - https://github.com/nodejs/undici/blob/v6.21.2/lib/web/eventsource/eventsource-stream.js
  - https://github.com/nodejs/undici/blob/v6.21.2/LICENSE

- fetch-event-source **2.0.1**, Microsoft/Azure: `src/parse.ts`, Git revision
  `1589ec1f49d96450f3bae9adb20ab4a5b3deb204` (2021). MIT; original license and source
  locator retained in `vendor/fetch-event-source-2.0.1/`. The source was read through
  the GitHub connector, copied verbatim and checked against its Git blob identity.
  - https://github.com/Azure/fetch-event-source/blob/1589ec1f49d96450f3bae9adb20ab4a5b3deb204/src/parse.ts
  - https://github.com/Azure/fetch-event-source/blob/1589ec1f49d96450f3bae9adb20ab4a5b3deb204/LICENSE

## Corpus provenance

The 252 primary/long streams and 18 semantic microcases are authored fixtures licensed under the repository MIT license. They are not customer traffic, a captured deployment workload, or manually translated/validated language corpora. Text was prepared in an AI-assisted workflow; the tested runtime does not call an LLM.

`wpt-event-data` is **one bounded iteration** of genuine upstream `eventsource/resources/message2.py`, with expected data from `eventsource/event-data.any.js`. The upstream resource loops; this artifact does not run that unbounded loop. The BSD-3-Clause license is retained at `licenses/WPT-BSD-3-Clause.txt`.

The upstream files were read at their default branch and identified by the file revisions below. These Git object IDs are solely exact upstream revision locators, not generated provenance certificates:

- event-data.any.js: blob `12867694f856f1e618cdc87515c1dba640de9f41`
- resources/message2.py: blob `8515e7b25eb9e60e74700f51d9d2cdfa062dcae1`
- LICENSE.md: blob `39c46d03ac2988226f949ee7ab3c7347d5481bd8`

Legal source retrieval uses GitHub's public repository contents/Git-blob read APIs for `web-platform-tests/wpt`, or the current source locations below with revision comparison:

- https://github.com/web-platform-tests/wpt/blob/master/eventsource/event-data.any.js
- https://github.com/web-platform-tests/wpt/blob/master/eventsource/resources/message2.py
- https://github.com/web-platform-tests/wpt/blob/master/LICENSE.md

Three `upstream-bom-*` cases are byte-adapted literal fixtures from eventsource-parser v4.1.1 `test/parse.test.ts`, approximately lines 153--198. The MIT upstream license applies. These are not the full package suite. The original tests explicitly exercise default TextDecoder, ignoreBOM, split BOM and empty decoder output; the artifact's adapters use their declared persistent decoder configuration. The original ignoreBOM/repeated-reset test harness is not claimed as executed.

- https://github.com/rexxars/eventsource-parser/blob/v4.1.1/test/parse.test.ts

Existing tests already cover fragmentation and decoder/parser interaction. This artifact makes no first-discovery claim about those ideas. Yaffle/EventSource was inspected as a candidate but was not executed. eventsource-parser v3.0.6 was read but not run, so there is no cross-version regression claim.

## Paper template and literature

The supplied acmart class, bibliography style and publisher source/README remain under their own notices. The original project starter prose and placeholder venue citation were replaced. Primary papers are cited, with legal retrieval URLs and verification notes in `paper/REFERENCE-AUDIT.md`; copyrighted third-party paper PDFs and font files are not redistributed.

## Complete authored corpus

The retained corpus contains 537 distinct valid UTF-8 SSE byte strings totaling 891,607 bytes; the largest is 60,145 bytes. It combines 393 pre-existing reference/structural fixtures with 144 prospectively specified fixtures in eight families: progress JSON, retry cycles, data whitespace, long callback tails, metadata-only blocks, incomplete suffixes, mixed endings, and Unicode planes. The corpus is retained at `corpus/corpus.json` and is reproducibly generated by the source modules. Authored fixtures are MIT-licensed local material, not production captures or mined faults.

`upstream-tests/httpx-sse-0.4.3/` retains all six upstream test modules plus their package marker. The recorded command executes 58 unchanged tests; one ASGI test requires the unavailable optional `sse_starlette` dependency. The file remains included and runs automatically when that dependency is available. Passing these tests is not represented as a full WPT or JavaScript-suite run. Exact Git blob locators are in `upstream-source-files.json`.
