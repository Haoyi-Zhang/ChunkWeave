/** Exhaustive short-profile check for CommitGate. */
import fs from 'node:fs'
import {executeCommitGate} from '../chunkweave/commit_gate.mjs'

const encoder = new TextEncoder()
const profiles = [
  {name: 'event-2', text: 'data:a\n\ndata:é\n\n', modes: ['gate', 'gate_decoder_per_event', 'gate_parser_per_event', 'gate_all']},
  {name: 'event-3', text: 'data:a\n\ndata:中\n\n', modes: ['gate', 'gate_decoder_per_event', 'gate_parser_per_event', 'gate_all']},
  {name: 'event-4', text: 'data:a\n\ndata:🌍\n\n', modes: ['gate', 'gate_decoder_per_event', 'gate_parser_per_event', 'gate_all']},
  {name: 'retry-2', text: 'retry:1\ndata:é\n\n', modes: ['gate', 'gate_decoder_per_retry', 'gate_parser_per_retry', 'gate_all']},
]

function observation (value) {
  return JSON.stringify({events: value.events, retries: value.retries, last_event_id: value.last_event_id})
}

let partitions = 0
let executions = 0
const rows = []
for (const profile of profiles) {
  const bytes = encoder.encode(profile.text)
  const expected = JSON.stringify({
    events: profile.name.startsWith('event-')
      ? [{type:'message',data:'a',id:''},{type:'message',data:profile.text.match(/data:([^\n]+)\n\n$/u)[1],id:''}]
      : [{type:'message',data:'é',id:''}],
    retries: profile.name === 'retry-2' ? [1] : [],
    last_event_id: '',
  })
  if (observation(executeCommitGate(bytes, [], 'gate')) !== expected) {
    throw new Error('Whole-input gate disagrees with specified SSE observation: '+profile.name)
  }
  const count = 2 ** (bytes.length - 1)
  let failures = 0
  for (let mask = 0; mask < count; mask++) {
    const cuts = []
    for (let offset = 1; offset < bytes.length; offset++) {
      if ((mask / 2 ** (offset - 1)) % 2 >= 1) cuts.push(offset)
    }
    for (const mode of profile.modes) {
      executions++
      if (observation(executeCommitGate(bytes, cuts, mode)) !== expected) failures++
    }
  }
  partitions += count
  rows.push({name: profile.name, bytes: bytes.length, partitions: count, modes: profile.modes, failures})
}
const result = {status: rows.every(row => row.failures === 0) ? 'PASS' : 'FAIL', oracle:'explicit SSE observations, checked before enumeration', partitions, executions, rows}
fs.writeFileSync(process.argv[2], `${JSON.stringify(result, null, 2)}\n`)
console.log(JSON.stringify(result))
if (result.status !== 'PASS') process.exitCode = 1
