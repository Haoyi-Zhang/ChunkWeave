// Native Node EventSource end-to-end only: write schedules are NOT client chunks.
import {createServer} from 'node:http';
import {createInterface} from 'node:readline';
import {performance} from 'node:perf_hooks';
async function test(q) {
 const raw=Buffer.from(q.b64,'base64');
 if(raw.length>65536) throw Error('bounded input limit');
 const offsets=[0,...q.cuts,raw.length]; let writes=0, requests=0;
 const server=createServer(async(req,res)=>{
  requests++; res.writeHead(200,{'Content-Type':'text/event-stream','Cache-Control':'no-cache'});
  for(let i=1;i<offsets.length;i++) {
   res.write(raw.subarray(offsets[i-1],offsets[i]));writes++;
   await new Promise(resolve=>setImmediate(resolve));
  }
  res.end();
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const t=performance.now(); let s;
 try {
  const observation=await new Promise((resolve,reject)=>{
   s=new EventSource(`http://127.0.0.1:${server.address().port}/stream`);
   let events=[];let opened=false;
   const timer=setTimeout(()=>{s.close();reject(Error('local bounded timeout'));},2500);
   s.onopen=()=>{opened=true;};
   for(const kind of new Set(['message',...q.types])) s.addEventListener(kind,e=>{
    events.push({type:e.type,data:e.data,id:e.lastEventId});
   });
   // Stop at first EOF/error, before any retry. This is not a retry experiment.
   s.onerror=()=>{s.close();clearTimeout(timer);resolve({events,opened});};
  });
  return {...observation,requested_cuts:q.cuts,server_writes:writes,requests,
          observed_internal_partition:null,elapsed_ms:performance.now()-t};
 } finally {if(s)s.close();server.closeAllConnections();await new Promise(r=>server.close(r));}
}
for await(const line of createInterface({input:process.stdin})){
 try {console.log(JSON.stringify(await test(JSON.parse(line))));}
 catch(e){console.log(JSON.stringify({error:String(e)}));}
}
