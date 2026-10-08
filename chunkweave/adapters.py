"""Local integration adapters. Vendored code is upstream, adapters are authored."""
from __future__ import annotations
import base64, codecs, json, subprocess, sys
from pathlib import Path
from .oracle import slices

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor'))
from httpx_sse._decoders import SSEDecoder, SSELineDecoder

class NodeWorker:
    def __init__(self, worker: str = 'node_worker.mjs'):
        if worker not in ('node_worker.mjs', 'azure_worker.mjs'):
            raise ValueError('unsupported local worker')
        self.proc = subprocess.Popen(
            ['node','--no-warnings','--experimental-transform-types', str(ROOT/'chunkweave'/worker)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            bufsize=1)
    def run(self, raw: bytes, schedules: list, modes: list[str] | None = None,
            expected:dict|None=None, baselines:dict|None=None, retain_actual:bool=False) -> list:
        request = {'b64':base64.b64encode(raw).decode(), 'schedules':schedules,
                   'modes':modes or ['correct'], 'expected':expected,
                   'baselines':baselines,'retain_actual':retain_actual}
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(json.dumps(request) + '\n'); self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError('Node worker exited: ' + self.proc.stderr.read())
        result = json.loads(line)
        if 'error' in result:
            raise RuntimeError(result['error'])
        return result['answers']
    def close(self):
        if self.proc.stdin and not self.proc.stdin.closed:
            self.proc.stdin.close()
        self.proc.wait(timeout=10)
        if self.proc.stdout:self.proc.stdout.close()
        if self.proc.stderr:self.proc.stderr.close()
    def __enter__(self): return self
    def __exit__(self, *_): self.close()


def httpx_source_adapter(raw: bytes, cuts: list[int] | tuple[int,...]) -> dict:
    """Exact source-level integration, NOT a run of HTTPX network/reconnection.

    Python utf-8-sig incremental decoder strips one initial BOM. The upstream
    SSELineDecoder receives decoded fragments. Its unmodified SSEDecoder emits
    objects also for metadata-only blocks. A one-bit observation-side data-field
    flag projects these objects to browser-style data event equality; raw objects
    are retained. This does not synthesize payloads or repair parsing results.
    """
    decoder = codecs.getincrementaldecoder('utf-8-sig')('strict')
    lines = SSELineDecoder()
    events, raw_events, retries = [], [], []
    class ObservedSSEDecoder(SSEDecoder):
        # Observe actual upstream assignments, including equal-value repeats.
        # Invalid fields which retain an old value must not create a new retry.
        def __setattr__(self, name, value):
            if name == '_retry' and value is not None:
                retries.append(value)
            super().__setattr__(name, value)
    parser = ObservedSSEDecoder()
    has_data = False
    committed = ''
    def consume(line: str):
        nonlocal has_data, committed
        # Observation of the documented line-level input, not an oracle call.
        key = line.partition(':')[0]
        if key == 'data':
            has_data = True
        item = parser.decode(line)
        if line == '':
            committed = parser._last_event_id
            if item is not None:
                observation = {'type':item.event,'data':item.data,'id':item.id,'retry':item.retry}
                raw_events.append(observation)
                if has_data:
                    events.append({k:observation[k] for k in ('type','data','id')})
            has_data = False
    for chunk in slices(raw,cuts):
        for line in lines.decode(decoder.decode(chunk,final=False)):
            consume(line)
    for line in lines.decode(decoder.decode(b'',final=True)):
        consume(line)
    # Only a held CR actually terminates a line. An unterminated residual line is
    # excluded by this declared EOF adapter profile, and never forced to dispatch.
    if lines.trailing_cr:
        for line in lines.flush(): consume(line)
    return {'events':events,'retries':retries,'last_event_id':committed,'raw_objects':raw_events}
