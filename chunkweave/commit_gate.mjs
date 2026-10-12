/** CommitGate: fatal UTF-8 decoding and quiescent SSE component replacement. */
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

// The fatal native decoder validates ALL bytes before this observer runs.
// A valid UTF-8 prefix can end in only one unfinished scalar. Inspect at most
// three continuation bytes and their lead; an all-continuation short chunk
// advances the prior residual. This is NOT a replacement UTF-8 validator.
class Utf8BoundaryObserver {
  constructor () { this.need = 0; this.inspections = 0 }
  feed (bytes) {
    if (!bytes.length) return
    let index = bytes.length - 1
    while (index >= 0) {
      const byte = bytes[index]
      this.inspections++
      if (byte < 0x80 || byte > 0xbf) {
        const width = byte < 0x80 ? 1 : byte < 0xe0 ? 2 : byte < 0xf0 ? 3 : 4
        this.need = Math.max(0, width - (bytes.length - index))
        return
      }
      index--
    }
    this.need -= bytes.length
  }
}

class SseLineFramer {
  constructor (limit) {
    this.limit = limit
    this.fragments = []
    this.length = 0
    this.swallowLf = false
    this.peak = 0
  }
  append (text) {
    if (!text.length) return
    this.length += text.length
    if (this.length > this.limit) throw new RangeError('unfinished line exceeds character limit')
    this.peak = Math.max(this.peak, this.length)
    this.fragments.push(text)
  }
  feed (text, consume, consumeRun) {
    // Empty decoded output must not clear the split-CRLF state.
    if (!text.length) return
    let start = 0
    if (this.swallowLf) {
      this.swallowLf = false
      if (text.charCodeAt(0) === 10) start = 1
    }
    const noCr = text.indexOf('\r', start) === -1
    let firstLf = noCr ? text.indexOf('\n', start) : -1
    if (noCr && firstLf === -1) {
      this.append(text.slice(start))
      return
    }
    // Already LF-framed text needs no per-line string assembly. Still stop at
    // EVERY blank line, return from its callbacks, then commit parser requests.
    if (noCr && this.fragments.length === 0 && consumeRun) {
      let runStart = start, lines = 0, end = firstLf
      while (end !== -1) {
        const length = end - start
        if (length > this.limit) throw new RangeError('unfinished line exceeds character limit')
        this.peak = Math.max(this.peak, length)
        lines++
        if (length === 0) {
          consumeRun(text.slice(runStart, end + 1), lines, true)
          runStart = end + 1
          lines = 0
        }
        start = end + 1
        end = text.indexOf('\n', start)
      }
      if (lines) consumeRun(text.slice(runStart, start), lines, false)
      this.append(text.slice(start))
      return
    }
    const emit = (end) => {
      this.append(text.slice(start, end))
      const line = this.fragments.length === 0 ? ''
        : this.fragments.length === 1 ? this.fragments[0] : this.fragments.join('')
      this.fragments.length = 0
      this.length = 0
      consume(line)
    }
    if (noCr) {
      let end = firstLf
      while (end !== -1) {
        emit(end)
        start = end + 1
        end = text.indexOf('\n', start)
      }
    } else {
      for (let index = start; index < text.length; index++) {
        const code = text.charCodeAt(index)
        if (code !== 10 && code !== 13) continue
        emit(index)
        if (code === 13) {
          if (text.charCodeAt(index + 1) === 10) index++
          else if (index + 1 === text.length) this.swallowLf = true
        }
        start = index + 1
      }
    }
    this.append(text.slice(start))
  }
}

/**
 * Stateful synchronous stream. push() accepts <=64 KiB per call; total input
 * is not retained or capped. collect:false delivers to sinks without retaining
 * output history. Limits bound unfinished lines and canonical block characters.
 * Callbacks may request replacements, but must not reenter push()/finish().
 * Sink/decoding/limit errors terminate the session; already delivered events
 * cannot be rolled back. This is not a network/reconnection/backpressure API.
 */
export function createCommitGate ({mode = 'gate', collect = true,
  batchLines = true, maxBufferedChars = 65536, onEvent, onRetry, onError} = {}) {
  const action = ACTIONS[mode]
  if (!action) throw new TypeError('unknown CommitGate mode')
  if (typeof collect !== 'boolean' || typeof batchLines !== 'boolean') throw new TypeError('boolean options required')
  if (!Number.isSafeInteger(maxBufferedChars) || maxBufferedChars < 1) throw new RangeError('positive character limit required')
  for (const sink of [onEvent, onRetry, onError]) {
    if (sink !== undefined && typeof sink !== 'function') throw new TypeError('sink must be a function')
  }
  const events = [], retries = [], diagnostics = []
  const observer = new Utf8BoundaryObserver()
  const framer = new SseLineFramer(maxBufferedChars)
  let decoder = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true})
  let atStart = true, last = '', pendingDecoder = false, pendingParser = false
  let decoderResets = 0, parserResets = 0, lineFeeds = 0, parserFeeds = 0
  let feedCount = 0, emptyDecodes = 0, decodedBytes = 0, decodeCalls = 0
  let eventCount = 0, retryCount = 0, blockChars = 0, peakBlockChars = 0
  let closed = false, failed = false, busy = false
  const requestDecoderReplacement = () => {
    if (closed || failed) throw new Error('session is not open')
    pendingDecoder = true
  }
  const requestParserReplacement = () => {
    if (closed || failed) throw new Error('session is not open')
    pendingParser = true
  }
  const makeParser = () => {
    const next = createParser({
      onId (id) { last = id },
      onEvent (event) {
        const value = {type: event.event || 'message', data: event.data, id: last}
        eventCount++
        if (collect) events.push(value)
        if (action.decoderEvent) pendingDecoder = true
        if (action.parserEvent) pendingParser = true
        onEvent?.(value)
      },
      onRetry (value) {
        retryCount++
        if (collect) retries.push(value)
        if (action.decoderRetry) pendingDecoder = true
        if (action.parserRetry) pendingParser = true
        onRetry?.(value)
      },
      onError (error) {
        if (collect) diagnostics.push(error.type)
        onError?.(error)
      },
    })
    next.feed(':\n') // Prime parser-local BOM state; the gate owns stream BOM.
    parserFeeds++
    return next
  }
  let parser = makeParser()
  const batch = []
  const flush = () => {
    if (!batch.length) return
    parser.feed(batch.length === 1 ? batch[0] : batch.join(''))
    parserFeeds++
    batch.length = 0
  }
  const countBlock = (characters, lines) => {
    blockChars += characters
    if (blockChars > maxBufferedChars) throw new RangeError('block exceeds character limit')
    peakBlockChars = Math.max(peakBlockChars, blockChars)
    lineFeeds += lines
  }
  const commitBlock = () => {
    // The parser has returned from all callbacks and its own block reset.
    if (pendingParser) {
      parser = makeParser()
      pendingParser = false
      parserResets++
    }
    blockChars = 0
  }
  const consumeLine = (line) => {
    countBlock(line.length + 1, 1)
    batch.push(`${line}\n`)
    if (!batchLines || line === '') flush()
    if (line === '') commitBlock()
  }
  const consumeRun = (text, lines, commit) => {
    countBlock(text.length, lines)
    parser.feed(text)
    parserFeeds++
    if (commit) commitBlock()
  }
  const consumeText = (text) => {
    if (!text.length) return
    if (atStart) {
      atStart = false
      if (text.charCodeAt(0) === 0xfeff) text = text.slice(1)
    }
    framer.feed(text, consumeLine, batchLines ? consumeRun : undefined)
    // Deliver complete nonblank lines now, including accepted retry callbacks.
    flush()
  }
  const commitDecoder = () => {
    if (pendingDecoder && observer.need === 0) {
      decoder = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true})
      pendingDecoder = false
      decoderResets++
    }
  }
  const guarded = (operation) => {
    if (closed || failed || busy) throw new Error('session is closed, failed, or reentered')
    busy = true
    try { return operation() } catch (error) { failed = true; throw error }
    finally { busy = false }
  }
  const push = (bytes) => guarded(() => {
    if (!(bytes instanceof Uint8Array)) throw new TypeError('bytes must be Uint8Array')
    if (bytes.length > 65536) throw new RangeError('chunk exceeds 64 KiB')
    const text = decoder.decode(bytes, {stream: true}) // Retain fatal validation.
    decodeCalls++
    decodedBytes += bytes.length
    if (!text.length) emptyDecodes++
    observer.feed(bytes)
    consumeText(text)
    commitDecoder()
    feedCount++
  })
  const snapshot = () => ({
    events, retries, last_event_id: last, diagnostics,
    feed_count: feedCount, empty_decodes: emptyDecodes, line_feeds: lineFeeds,
    parser_feed_calls: parserFeeds, decode_calls: decodeCalls,
    decoded_bytes: decodedBytes, boundary_byte_inspections: observer.inspections,
    decoder_resets: decoderResets, parser_resets: parserResets,
    event_count: eventCount, retry_count: retryCount,
    deferred_decoder_reset: pendingDecoder, deferred_parser_reset: pendingParser,
    buffered_line_chars: framer.length, peak_line_chars: framer.peak,
    peak_block_chars: peakBlockChars, closed, failed,
  })
  const finish = () => guarded(() => {
    consumeText(decoder.decode()) // Fatal flush rejects an incomplete scalar.
    decodeCalls++
    commitDecoder()
    // No synthetic line terminator or block separator. Release unfinished state.
    framer.fragments.length = 0
    framer.length = 0
    parser = null
    closed = true
    return snapshot()
  })
  return {push, finish, snapshot, requestDecoderReplacement, requestParserReplacement}
}

/** Existing <=64-KiB exact-partition interface, backed by the stream engine. */
export function executeCommitGate (bytes, cuts, mode = 'gate', options = {}) {
  if (!(bytes instanceof Uint8Array)) throw new TypeError('bytes must be Uint8Array')
  if (bytes.length > 65536) throw new RangeError('input exceeds 64 KiB')
  let previous = 0
  for (const cut of cuts) {
    if (!Number.isInteger(cut) || cut <= previous || cut >= bytes.length) throw new TypeError('invalid partition')
    previous = cut
  }
  const gate = createCommitGate({...options, mode})
  let start = 0
  for (const end of [...cuts, bytes.length]) {
    gate.push(bytes.subarray(start, end))
    start = end
  }
  return gate.finish()
}
