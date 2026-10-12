/** Pipe/file-only comparison; no transport, compilation, or upstream mutation. */
import fs from 'node:fs'
import zlib from 'node:zlib'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {execFileSync} from 'node:child_process'
import {performance} from 'node:perf_hooks'
import assert from 'node:assert/strict'
import {createParser} from '../vendor/eventsource-parser-4.1.1/parse.ts'
import {executeCommitGate} from '../chunkweave/commit_gate.mjs'
import {executeCommitGateReference} from '../chunkweave/commit_gate_reference.mjs'

const root = fileURLToPath(new URL('../', import.meta.url))
const variants = ['direct-fatal', 'original', 'suffix-line', 'optimized', 'original-all', 'optimized-all']
const project = value => ({events:value.events, retries:value.retries, last_event_id:value.last_event_id})
function direct (bytes, cuts) {
  const events = [], retries = [], diagnostics = []
  let last = '', feeds = 0, start = 0
  const parser = createParser({onId:id => { last = id },
    onEvent:e => events.push({type:e.event || 'message', data:e.data, id:last}),
    onRetry:r => retries.push(r), onError:e => diagnostics.push(e.type)})
  const decoder = new TextDecoder('utf-8', {fatal:true, ignoreBOM:true})
  for (const end of [...cuts, bytes.length]) {
    parser.feed(decoder.decode(bytes.subarray(start, end), {stream:true}))
    start = end
    feeds++
  }
  parser.feed(decoder.decode())
  return {events, retries, last_event_id:last, diagnostics, feed_count:feeds,
    decoded_bytes:bytes.length, decode_calls:feeds + 1,
    parser_feed_calls:feeds + 1, boundary_byte_inspections:0,
    decoder_resets:0, parser_resets:0}
}
function execute (variant, bytes, cuts) {
  if (variant === 'direct-fatal') return direct(bytes, cuts)
  const mode = variant.endsWith('-all') ? 'gate_all' : 'gate'
  if (variant.startsWith('original')) {
    return executeCommitGateReference(bytes, cuts, mode)
  }
  return executeCommitGate(bytes, cuts, mode, {batchLines:variant !== 'suffix-line'})
}

if (process.argv[2] === '--cold') {
  const start = performance.now()
  const result = execute(process.argv[3], new TextEncoder().encode('id:7\nretry:21\ndata:é中🌍\n\n'), [14])
  console.log(JSON.stringify({elapsed_ms:performance.now() - start, observation:project(result)}))
} else {
  const out = path.resolve(process.argv[2] || path.join(root, 'results/commit-gate-optimized'))
  const allowed = path.join(root, 'results') + path.sep
  if (!out.startsWith(allowed)) throw new Error('benchmark output must stay inside candidate artifact/results')
  if (fs.existsSync(out)) throw new Error('refusing to overwrite a benchmark run')
  fs.mkdirSync(out, {recursive:true})
  const corpus = JSON.parse(fs.readFileSync(path.join(root, 'corpus/corpus.json'))).cases
  const retained = new Map(zlib.gunzipSync(fs.readFileSync(path.join(root, 'results/study/commit-gate/observations.jsonl.gz')))
    .toString().trim().split('\n').map(line => { const row = JSON.parse(line); return [row.case, row.schedules] }))
  // Reuse the original input-only first/middle/last family sample, not timing outcomes.
  const families = new Map()
  for (const fixture of corpus) {
    if (!families.has(fixture.family)) families.set(fixture.family, [])
    families.get(fixture.family).push(fixture)
  }
  const selected = new Map()
  for (const group of families.values()) {
    group.sort((a,b) => a.id.localeCompare(b.id, 'en'))
    for (const fixture of [group[0], group[Math.floor(group.length / 2)], group.at(-1)]) selected.set(fixture.id, fixture)
  }
  const workloads = []
  for (const fixture of selected.values()) {
    const bytes = new TextEncoder().encode(fixture.text)
    const cuts64 = Array.from({length:Math.floor((bytes.length - 1) / 64)}, (_,i) => (i + 1) * 64)
    const single = retained.get(fixture.id).find(cuts => cuts.length === 1)
    const plans = [[], ...(cuts64.length ? [cuts64] : []), ...(single ? [single] : [])]
    const unique = [...new Map(plans.map(cuts => [JSON.stringify(cuts), cuts])).values()]
    for (let index = 0; index < unique.length; index++) workloads.push({fixture, bytes, cuts:unique[index], index})
  }
  const rows = [], work = []
  let checksum = 0
  for (const [wi, workload] of workloads.entries()) {
    const {fixture, bytes, cuts, index} = workload
    for (const variant of variants) {
      const value = execute(variant, bytes, cuts)
      assert.deepEqual(project(value), fixture.expected, `${fixture.id}/${variant}`)
      // Derive reference loop/call counts OUTSIDE the timed region, without
      // instrumenting or allocating an extra result object in that baseline.
      const reference = variant.startsWith('original')
      work.push({case:fixture.id, schedule:index, variant, bytes:bytes.length,
        feeds:value.feed_count, decode_calls:reference ? value.feed_count + 1 : value.decode_calls,
        decoded_bytes:bytes.length, boundary_byte_inspections:reference ? bytes.length : value.boundary_byte_inspections,
        parser_feed_calls:reference ? value.line_feeds + 1 + value.parser_resets : value.parser_feed_calls,
        logical_lines:value.line_feeds ?? null,
        decoder_resets:value.decoder_resets, parser_resets:value.parser_resets})
    }
    // Same repetitions for every variant of this workload; timing contains
    // decoder/parser construction and output allocation on every execution.
    const t = performance.now()
    for (let i = 0; i < 8; i++) execute('original', bytes, cuts)
    const iterations = Math.max(8, Math.min(256, Math.ceil(16 / Math.max(0.01, performance.now() - t))))
    for (let repeat = 0; repeat < 6; repeat++) {
      const shift = (wi + repeat) % variants.length
      for (let rank = 0; rank < variants.length; rank++) {
        const variant = variants[(shift + rank) % variants.length]
        let value
        const start = performance.now()
        for (let i = 0; i < iterations; i++) {
          value = execute(variant, bytes, cuts)
          checksum += value.events.length + value.retries.length
        }
        const elapsed = performance.now() - start
        assert.deepEqual(project(value), fixture.expected)
        rows.push({case:fixture.id, family:fixture.family, bytes:bytes.length,
          schedule:index, feeds:cuts.length + 1, repeat, rank, variant, iterations,
          elapsed_ms:elapsed / iterations})
      }
    }
    if ((wi + 1) % 50 === 0) console.log(`workloads ${wi + 1}/${workloads.length}`)
  }
  const median = values => {
    const sorted = values.toSorted((a,b) => a - b), n = sorted.length
    return n % 2 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2
  }
  const pairs = new Map()
  for (const row of rows) {
    const key = JSON.stringify([row.case, row.schedule, row.repeat])
    if (!pairs.has(key)) pairs.set(key, {})
    pairs.get(key)[row.variant] = row.elapsed_ms
  }
  const summary = {}
  for (const variant of variants) {
    const values = rows.filter(r => r.variant === variant).map(r => r.elapsed_ms)
    summary[variant] = {runs:values.length, median_ms:median(values), mean_ms:values.reduce((a,b) => a + b, 0) / values.length,
      paired_vs_direct_percent:median([...pairs.values()].map(p => 100 * (p[variant] / p['direct-fatal'] - 1))),
      paired_vs_original_percent:median([...pairs.values()].map(p => 100 * (p[variant] / p[variant.endsWith('-all') ? 'original-all' : 'original'] - 1)))}
  }
  const cold = []
  // Each first execution runs in a fresh Node process. Parent elapsed includes
  // process startup + imports + stdout; child elapsed excludes those common costs.
  for (let repeat = 0; repeat < 6; repeat++) {
    for (let rank = 0; rank < variants.length; rank++) {
      const variant = variants[(repeat + rank) % variants.length]
      const start = performance.now()
      const value = JSON.parse(execFileSync(process.execPath,
        ['--no-warnings', '--experimental-transform-types', fileURLToPath(import.meta.url), '--cold', variant],
        {encoding:'utf8', timeout:30000}))
      cold.push({repeat, rank, variant, first_execution_ms:value.elapsed_ms, process_ms:performance.now() - start})
    }
  }
  const coldSummary = Object.fromEntries(variants.map(variant => [variant, {
    runs:6,
    median_first_execution_ms:median(cold.filter(r => r.variant === variant).map(r => r.first_execution_ms)),
    median_process_ms:median(cold.filter(r => r.variant === variant).map(r => r.process_ms)),
  }]))
  const result = {status:'PASS', node:process.version, platform:process.platform, arch:process.arch,
    scope:'local valid-input timing, no network, no invented faults; direct is a no-replacement cost floor, original gate is contract-matched',
    selected_streams:selected.size, workloads:workloads.length, repeats:6, rows:rows.length,
    timer:'warm in-process, includes construction/output allocation, excludes input plans and equality checks; cold separately includes startup/imports',
    checksum, summary, cold_summary:coldSummary}
  for (const [name, value] of [['timing.json', rows], ['work.json', work], ['cold.json', cold], ['summary.json', result]]) {
    fs.writeFileSync(path.join(out, name), JSON.stringify(value, null, 2) + '\n', {flag:'wx'})
  }
  console.log(JSON.stringify(result, null, 2))
}
