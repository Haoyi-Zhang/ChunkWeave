// Source functions unchanged. ReadableStream chunks are directly controlled;
// there are no socket writes and no external requests in this adapter.
import readline from 'node:readline';
import {performance} from 'node:perf_hooks';
import {getBytes,getLines,getMessages} from '../vendor/fetch-event-source-2.0.1/parse.ts';

async function execute(raw,cuts) {
  const events=[],retries=[],raw_objects=[];
  let idBuffer='',committed='',hasData=false,feeds=0;
  const td=new TextDecoder();
  const onMessage=getMessages(id=>{idBuffer=id},v=>retries.push(v),m=>{
    raw_objects.push({...m});
    if(hasData)events.push({type:m.event||'message',data:m.data,id:committed});
  });
  const onChunk=getLines((line,fieldLength)=>{
    // Projection marks only data fields which the upstream field contract
    // actually accepts (a nonempty field followed by a colon). Bare `data`
    // must not be repaired by the observation layer.
    if(fieldLength>0 && td.decode(line.subarray(0,fieldLength))==='data')hasData=true;
    if(line.length===0)committed=idBuffer;
    onMessage(line,fieldLength);
    if(line.length===0)hasData=false;
  });
  let index=0,start=0;const ends=[...cuts,raw.length];
  const stream=new ReadableStream({pull(controller){
    if(index===ends.length){controller.close();return;}
    const end=ends[index++];controller.enqueue(raw.subarray(start,end));start=end;
  }});
  await getBytes(stream,chunk=>{feeds++;onChunk(chunk)});
  return {events,retries,last_event_id:committed,raw_objects,feed_count:feeds};
}
const rl=readline.createInterface({input:process.stdin,crlfDelay:Infinity});
for await (const line of rl) {
  try {
    const q=JSON.parse(line),raw=Buffer.from(q.b64,'base64'),answers=[];
    if(raw.length>65536)throw Error('bounded input limit');
    for(const cuts of q.schedules){
      if(cuts.some((v,i)=>!Number.isInteger(v)||v<=(i?cuts[i-1]:0)||v>=raw.length))throw Error('invalid partition');
      const t=performance.now();let r=await execute(raw,cuts);r.elapsed_ms=performance.now()-t;
      if(q.expected){
        const eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b),base=q.baselines?.correct;
        const z={event_ok:eq(r.events,q.expected.events),
          control_ok:eq(r.retries,q.expected.retries)&&r.last_event_id===q.expected.last_event_id,
          changed:base?!(eq(r.events,base.events)&&eq(r.retries,base.retries)&&r.last_event_id===base.last_event_id):null,
          event_count:r.events.length,feed_count:r.feed_count,elapsed_ms:r.elapsed_ms};
        if(q.retain_actual)z.actual=r;r=z;
      }
      answers.push({correct:r});
    }
    console.log(JSON.stringify({answers}));
  }catch(e){console.log(JSON.stringify({error:String(e),stack:e.stack}));}
}
