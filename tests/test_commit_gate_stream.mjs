import assert from 'node:assert/strict'
import {test} from 'node:test'
import fs from 'node:fs'
import zlib from 'node:zlib'
import {createCommitGate, executeCommitGate, COMMIT_GATE_MODES} from '../chunkweave/commit_gate.mjs'
import {executeCommitGateReference} from '../chunkweave/commit_gate_reference.mjs'

const enc = new TextEncoder()
const project = value => ({events: value.events, retries: value.retries, last_event_id: value.last_event_id})
const corpus = JSON.parse(fs.readFileSync(new URL('../corpus/corpus.json', import.meta.url))).cases

test('all retained gate schedules and modes preserve specified observations and reset counts', () => {
  const cases = new Map(corpus.map(c => [c.id, c]))
  const records = zlib.gunzipSync(fs.readFileSync(new URL('../results/study/commit-gate/observations.jsonl.gz', import.meta.url)))
    .toString().trim().split('\n').map(JSON.parse)
  let checks = 0
  for (const record of records) {
    const fixture = cases.get(record.case)
    assert.ok(fixture)
    const bytes = enc.encode(fixture.text)
    for (const cuts of record.schedules) {
      for (const mode of COMMIT_GATE_MODES) {
        const reference = executeCommitGateReference(bytes, cuts, mode)
        const value = executeCommitGate(bytes, cuts, mode)
        assert.deepEqual(project(value), fixture.expected, `${fixture.id}/${mode}`)
        assert.deepEqual(project(value), project(reference))
        assert.equal(value.decoder_resets, reference.decoder_resets)
        assert.equal(value.parser_resets, reference.parser_resets)
        assert.equal(value.line_feeds, reference.line_feeds)
        assert.equal(value.decoded_bytes, bytes.length)
        assert.ok(value.boundary_byte_inspections <= Math.min(bytes.length, 4 * value.feed_count))
        checks++
      }
    }
  }
  assert.equal(records.length, 537)
  assert.equal(checks, 64938)
})

test('all byte cuts of Unicode/CRLF/BOM literal stream preserve sinks', () => {
  const text = '\ufeffid:7\r\nretry:21\r\ndata:é中🌍\r\n\r\ndata:\ufeff\r\n\r\n'
  const bytes = enc.encode(text)
  const expected = {events: [{type:'message', data:'é中🌍', id:'7'}, {type:'message', data:'\ufeff', id:'7'}], retries:[21], last_event_id:'7'}
  for (let cut = 1; cut < bytes.length; cut++) {
    const events = [], retries = []
    const gate = createCommitGate({mode:'gate_all', collect:false, onEvent:e => events.push(e), onRetry:r => retries.push(r)})
    gate.push(bytes.subarray(0, cut))
    gate.push(new Uint8Array())
    gate.push(bytes.subarray(cut))
    const result = gate.finish()
    assert.deepEqual({events, retries, last_event_id:result.last_event_id}, expected)
    assert.equal(result.events.length, 0)
  }
})

test('retry sink requests wait for scalar/block commits without delaying retry to next push', () => {
  let gate, retry = 0
  gate = createCommitGate({onRetry:() => {
    retry++
    gate.requestDecoderReplacement()
    gate.requestParserReplacement()
  }})
  const bytes = enc.encode('retry:1\ndata:中\n\n')
  gate.push(bytes.subarray(0, 14))
  assert.equal(retry, 1)
  assert.equal(gate.snapshot().deferred_decoder_reset, true)
  assert.equal(gate.snapshot().deferred_parser_reset, true)
  gate.push(bytes.subarray(14))
  const result = gate.finish()
  assert.equal(result.events[0].data, '中')
  assert.equal(result.decoder_resets, 1)
  assert.equal(result.parser_resets, 1)
})

test('sustained 2.5+ MiB stream retains no output history and one stream BOM owner', () => {
  const block = enc.encode('id:7\r\nretry:21\r\ndata:é中🌍\r\n\r\n')
  let events = 0, retries = 0
  const gate = createCommitGate({mode:'gate_all', collect:false,
    onEvent:e => { assert.equal(e.data, 'é中🌍'); assert.equal(e.id, '7'); events++ },
    onRetry:r => { assert.equal(r, 21); retries++ }})
  gate.push(enc.encode('\ufeff'))
  for (let i = 0; i < 100000; i++) {
    const cut = 1 + i % (block.length - 1)
    gate.push(block.subarray(0, cut))
    gate.push(new Uint8Array())
    gate.push(block.subarray(cut))
  }
  const result = gate.finish()
  assert.equal(events, 100000)
  assert.equal(retries, 100000)
  assert.equal(result.events.length + result.retries.length + result.diagnostics.length, 0)
  assert.equal(result.decoded_bytes, 3 + block.length * 100000)
  assert.ok(result.peak_line_chars < 32)
  assert.ok(result.peak_block_chars < 64)
})

test('bytewise residual observer covers every valid scalar, including boundary planes', () => {
  // One benign valid-scalar sweep; no parser history or network inputs.
  let count = 0, expectedData
  const gate = createCommitGate({mode:'gate_decoder_per_event', collect:false,
    onEvent:event => { assert.equal(event.data, expectedData); count++ }})
  for (let cp = 0x80; cp <= 0x10ffff; cp++) {
    if (cp >= 0xd800 && cp <= 0xdfff) continue
    expectedData = String.fromCodePoint(cp)
    const bytes = enc.encode('data:' + expectedData + '\n\n')
    for (let index = 0; index < bytes.length; index++) {
      // A pending request at every lead byte exercises deferral across every
      // continuation, rather than testing only resets at ASCII separators.
      if (index === 5) gate.requestDecoderReplacement()
      gate.push(Uint8Array.of(bytes[index]))
    }
  }
  const value = gate.finish()
  assert.equal(count, 0x110000 - 0x80 - 0x800)
  assert.equal(value.deferred_decoder_reset, false)
})

test('event sinks request both replacements before the following block of one push', () => {
  let gate
  gate = createCommitGate({onEvent:() => {
    gate.requestDecoderReplacement()
    gate.requestParserReplacement()
  }})
  gate.push(enc.encode('id:7\ndata:first\n\ndata:中\n\n'))
  const result = gate.finish()
  assert.deepEqual(result.events, [{type:'message', data:'first', id:'7'}, {type:'message', data:'中', id:'7'}])
  assert.equal(result.parser_resets, 2)
  assert.equal(result.decoder_resets, 1) // Requests coalesce to one feed boundary.
})

test('fatal validation and EOF checks remain active', () => {
  // Bounded decoder rejection checks, not a parser exploit or vulnerability test.
  for (const bytes of [Uint8Array.of(0xff), Uint8Array.of(0xc0, 0x80), Uint8Array.of(0xed, 0xa0, 0x80)]) {
    const gate = createCommitGate()
    assert.throws(() => gate.push(bytes), TypeError)
    assert.equal(gate.snapshot().failed, true)
    assert.throws(() => gate.push(enc.encode('data:x\n\n')))
  }
  const gate = createCommitGate()
  gate.push(Uint8Array.of(0xf0, 0x9f))
  assert.throws(() => gate.finish(), TypeError)
})

test('unfinished lines/blocks are not dispatched or committed at EOF', () => {
  const gate = createCommitGate({mode:'gate_all'})
  gate.push(enc.encode('id:7\ndata:ok\n\nid:uncommitted\nretry:2\ndata:pending'))
  const value = gate.finish()
  assert.deepEqual(value.events, [{type:'message', data:'ok', id:'7'}])
  assert.equal(value.last_event_id, '7')
  assert.deepEqual(value.retries, [2])
  assert.equal(value.deferred_parser_reset, true)
  assert.equal(value.buffered_line_chars, 0)
})

test('configured line/block limits fail terminally; per-call cap remains', () => {
  for (const text of ['data:' + 'x'.repeat(33), 'data:x\ndata:x\ndata:x\ndata:x\ndata:x\n']) {
    const gate = createCommitGate({maxBufferedChars:32})
    assert.throws(() => gate.push(enc.encode(text)), RangeError)
    assert.equal(gate.snapshot().failed, true)
  }
  assert.throws(() => createCommitGate().push(new Uint8Array(65537)), RangeError)
})

test('close, reentrancy, and sink errors do not silently resume', () => {
  const gate = createCommitGate()
  gate.finish()
  assert.throws(() => gate.push(new Uint8Array()))
  assert.throws(() => gate.finish())
  assert.throws(() => gate.requestParserReplacement())
  let reentrant
  reentrant = createCommitGate({onEvent:() => reentrant.push(enc.encode('data:x\n\n'))})
  assert.throws(() => reentrant.push(enc.encode('data:first\n\n')))
  assert.equal(reentrant.snapshot().failed, true)
  const broken = createCommitGate({onRetry:() => { throw new Error('sink stopped') }})
  assert.throws(() => broken.push(enc.encode('retry:1\n')), /sink stopped/)
  assert.equal(broken.snapshot().failed, true)
})

test('line-only ablation and block batching preserve observations, reduce actual calls', () => {
  const raw = enc.encode('id:7\nretry:1\ndata:a\ndata:b\n\ndata:c\n\n')
  const line = executeCommitGate(raw, [], 'gate_all', {batchLines:false})
  const batch = executeCommitGate(raw, [], 'gate_all')
  assert.deepEqual(project(line), project(batch))
  assert.ok(batch.parser_feed_calls < line.parser_feed_calls)
  assert.equal(batch.decoder_resets, line.decoder_resets)
  assert.equal(batch.parser_resets, line.parser_resets)
})
