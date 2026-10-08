/**
 * CommitGate: segmentation-stable SSE composition for valid UTF-8 streams.
 *
 * The gate owns the stream BOM, frames logical SSE lines outside the parser,
 * feeds one complete line at a time, applies parser replacement only after a
 * blank-line commit, and applies decoder replacement only at a UTF-8 scalar
 * boundary.  Transport chunks therefore cannot expose already-consumed future
 * bytes to a callback-induced component replacement.
 */
import {createParser} from '../vendor/eventsource-parser-4.1.1/parse.ts'

const ACTIONS = Object.freeze({
  gate: {},
  gate_decoder_per_event: {decoderEvent: true},
  gate_parser_per_event: {parserEvent: true},
  gate_decoder_per_retry: {decoderRetry: true},
  gate_parser_per_retry: {parserRetry: true},
  gate_all: {decoderEvent: true, parserEvent: true, decoderRetry: true, parserRetry: true},
})

export const COMMIT_GATE_MODES = Object.freeze(Object.keys(ACTIONS))

class Utf8BoundaryTracker {
  constructor () {
    this.need = 0
    this.low = 0x80
    this.high = 0xbf
  }

  feed (bytes) {
    for (const byte of bytes) {
      if (this.need > 0) {
        if (byte < this.low || byte > this.high) throw new TypeError('invalid UTF-8 continuation')
        this.need--
        this.low = 0x80
        this.high = 0xbf
        continue
      }
      if (byte <= 0x7f) continue
      if (byte >= 0xc2 && byte <= 0xdf) {
        this.need = 1
      } else if (byte >= 0xe0 && byte <= 0xef) {
        this.need = 2
        if (byte === 0xe0) this.low = 0xa0
        if (byte === 0xed) this.high = 0x9f
      } else if (byte >= 0xf0 && byte <= 0xf4) {
        this.need = 3
        if (byte === 0xf0) this.low = 0x90
        if (byte === 0xf4) this.high = 0x8f
      } else {
        throw new TypeError('invalid UTF-8 leading byte')
      }
    }
  }

  finish () {
    if (this.need !== 0) throw new TypeError('incomplete final UTF-8 scalar')
  }
}

class SseLineFramer {
  constructor () {
    this.fragments = []
    this.swallowLf = false
  }

  feed (text) {
    const lines = []
    let start = 0
    if (this.swallowLf) {
      this.swallowLf = false
      if (text.charCodeAt(0) === 10) start = 1
    }
    for (let index = start; index < text.length; index++) {
      const code = text.charCodeAt(index)
      if (code !== 10 && code !== 13) continue
      if (index > start) this.fragments.push(text.slice(start, index))
      lines.push(this.fragments.length === 0
        ? ''
        : this.fragments.length === 1 ? this.fragments[0] : this.fragments.join(''))
      this.fragments.length = 0
      if (code === 13) {
        if (index + 1 < text.length && text.charCodeAt(index + 1) === 10) {
          index++
        } else if (index + 1 === text.length) {
          this.swallowLf = true
        }
      }
      start = index + 1
    }
    if (start < text.length) this.fragments.push(text.slice(start))
    return lines
  }
}

function normalizeCuts (bytes, cuts) {
  let previous = 0
  for (const cut of cuts) {
    if (!Number.isInteger(cut) || cut <= previous || cut >= bytes.length) {
      throw new TypeError('invalid partition')
    }
    previous = cut
  }
  return [...cuts, bytes.length]
}

/** Execute one exact byte partition through CommitGate. */
export function executeCommitGate (bytes, cuts, mode = 'gate') {
  const action = ACTIONS[mode]
  if (!action) throw new TypeError('unknown CommitGate mode')
  if (!(bytes instanceof Uint8Array)) throw new TypeError('bytes must be Uint8Array')
  if (bytes.length > 65536) throw new RangeError('input exceeds 64 KiB')

  const events = []
  const retries = []
  const diagnostics = []
  const tracker = new Utf8BoundaryTracker()
  const framer = new SseLineFramer()
  let decoder = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true})
  let atStart = true
  let last = ''
  let pendingDecoder = false
  let pendingParser = false
  let decoderResets = 0
  let parserResets = 0
  let lineFeeds = 0

  const requestDecoder = () => { pendingDecoder = true }
  const requestParser = () => { pendingParser = true }
  const makeParser = () => {
    const next = createParser({
      onId (id) { last = id },
      onEvent (event) {
        events.push({type: event.event || 'message', data: event.data, id: last})
        if (action.decoderEvent) requestDecoder()
        if (action.parserEvent) requestParser()
      },
      onRetry (value) {
        retries.push(value)
        if (action.decoderRetry) requestDecoder()
        if (action.parserRetry) requestParser()
      },
      onError (error) { diagnostics.push(error.type) },
    })
    // CommitGate, not each replacement parser, owns the one stream-level BOM.
    // A harmless comment completes the parser's private leading-BOM check.
    next.feed(':\n')
    return next
  }
  let parser = makeParser()

  const stripOwnedBom = (text) => {
    if (!atStart || text.length === 0) return text
    atStart = false
    return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text
  }

  const consumeText = (text) => {
    for (const line of framer.feed(stripOwnedBom(text))) {
      // Canonical LF is semantics-preserving after logical line framing.
      parser.feed(`${line}\n`)
      lineFeeds++
      // Parser replacement is committed only after a logical SSE block.
      if (line === '' && pendingParser) {
        parser = makeParser()
        pendingParser = false
        parserResets++
      }
    }
  }

  let start = 0
  let feedCount = 0
  for (const end of normalizeCuts(bytes, cuts)) {
    const chunk = bytes.subarray(start, end)
    tracker.feed(chunk)
    consumeText(decoder.decode(chunk, {stream: true}))
    // A decoder replacement is safe only when no scalar prefix is retained.
    if (pendingDecoder && tracker.need === 0) {
      decoder = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true})
      pendingDecoder = false
      decoderResets++
    }
    start = end
    feedCount++
  }

  tracker.finish()
  consumeText(decoder.decode())
  if (pendingDecoder) {
    // Valid input and final decoder flush imply a scalar boundary here.
    decoder = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true})
    pendingDecoder = false
    decoderResets++
  }

  return {
    events,
    retries,
    last_event_id: last,
    feed_count: feedCount,
    empty_decodes: 0,
    line_feeds: lineFeeds,
    decoder_resets: decoderResets,
    parser_resets: parserResets,
    deferred_decoder_reset: pendingDecoder,
    deferred_parser_reset: pendingParser,
    diagnostics,
  }
}
