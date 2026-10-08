// Exact controlled byte slices; no networking. Upstream parser source unchanged.
import readline from 'node:readline';
import {createParser} from '../vendor/eventsource-parser-4.1.1/parse.ts';
import {performance} from 'node:perf_hooks';
import {COMMIT_GATE_MODES, executeCommitGate} from './commit_gate.mjs';

const MODES = ['correct', 'stateless_utf8', 'reset_parser', 'empty_reset',
  'leading_trim', 'newline_each_feed', 'crlf_chunk_normalize',
  'id_per_chunk', 'decoder_per_event', 'bom_owned', 'skip_empty',
  'parser_per_event', 'decoder_per_retry', 'parser_per_retry',
  ...COMMIT_GATE_MODES];

function execute(bytes, cuts, mode='correct') {
  if (COMMIT_GATE_MODES.includes(mode)) return executeCommitGate(bytes, cuts, mode);
  const events = [], retries = [], diagnostics = [];
  let last = '', d = new TextDecoder('utf-8', {ignoreBOM: ['bom_owned','skip_empty'].includes(mode)}), feedCount = 0, emptyText = 0;
  const makeParser = () => createParser({
    onId(id) { last = id; },
    onEvent(e) {
      events.push({type: e.event || 'message', data: e.data, id: last});
      if (mode === 'decoder_per_event') d = new TextDecoder('utf-8');
      if (mode === 'parser_per_event') p = makeParser();
    },
    onRetry(value) {
      retries.push(value);
      if (mode === 'decoder_per_retry') d = new TextDecoder('utf-8');
      if (mode === 'parser_per_retry') p = makeParser();
    },
    onError(e) { diagnostics.push(e.type); },
  });
  let p = makeParser();
  let a = 0;
  for (const b of [...cuts, bytes.length]) {
    const c = bytes.subarray(a, b);
    if (mode === 'reset_parser' && feedCount) p.reset();
    if (mode === 'id_per_chunk' && feedCount) last = '';
    let t = mode === 'stateless_utf8'
      ? new TextDecoder('utf-8').decode(c)
      : d.decode(c, {stream:true});
    if (!t.length) emptyText++;
    if (mode === 'empty_reset' && !t.length && c.length) p.reset();
    if (mode === 'leading_trim' && feedCount) t = t.trimStart();
    if (mode === 'crlf_chunk_normalize') t = t.replace(/\r\n/g,'\n').replace(/\r/g,'\n');
    if (mode === 'newline_each_feed') t += '\n';
    if (mode !== 'skip_empty' || t.length) p.feed(t);
    feedCount++;
    a = b;
  }
  // Decoder finalization is not event finalization. reset({consume:true}) is NOT used.
  if (mode !== 'stateless_utf8') p.feed(d.decode());
  return {events, retries, last_event_id:last, feed_count:feedCount,
    empty_decodes:emptyText, diagnostics};
}

const rl = readline.createInterface({input:process.stdin, crlfDelay:Infinity});
for await (const line of rl) {
  try {
    const request = JSON.parse(line);
    if (request.action === 'info') {
      console.log(JSON.stringify({node:process.version, modes:MODES}));
      continue;
    }
    const raw = Buffer.from(request.b64, 'base64');
    if (raw.length > 65536) throw new Error('input exceeds 64 KiB');
    const modes = request.modes || ['correct'];
    const answers = [];
    for (const cuts of request.schedules) {
      if (cuts.some((v,i) => !Number.isInteger(v) || v <= (i?cuts[i-1]:0) || v >= raw.length)) {
        throw new Error('invalid partition');
      }
      const row = {};
      for (const mode of modes) {
        if (!MODES.includes(mode)) throw new Error('unknown integration mode');
        const start = performance.now();
        row[mode] = execute(raw,cuts,mode);
        row[mode].elapsed_ms = performance.now()-start;
      }
      if (request.expected) {
        for (const mode of modes) {
          const r=row[mode], expected=request.expected, base=request.baselines?.[mode];
          const eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
          const eventOK=eq(r.events,expected.events);
          const controlOK=eq(r.retries,expected.retries)&&r.last_event_id===expected.last_event_id;
          row[mode]={event_ok:eventOK,control_ok:controlOK,
            changed:base?!(eq(r.events,base.events)&&eq(r.retries,base.retries)&&r.last_event_id===base.last_event_id):null,
            event_count:r.events.length,feed_count:r.feed_count,empty_decodes:r.empty_decodes,
            diagnostic_count:r.diagnostics.length,elapsed_ms:r.elapsed_ms};
          if(request.retain_actual) row[mode].actual=r;
        }
      }
      answers.push(row);
    }
    console.log(JSON.stringify({answers}));
  } catch (e) {
    console.log(JSON.stringify({error:String(e), stack:e.stack}));
  }
}
