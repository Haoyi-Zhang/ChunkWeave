"""Versioned authored, bounded SSE fixtures. No proprietary or live traffic."""
from __future__ import annotations
import json
from pathlib import Path
from .oracle import evaluate

FAMILIES = [
 ('task-en','Preparing the next batch', 'plain'),
 ('task-zh','正在整理本地任务，请稍候', 'json'),
 ('task-ja','処理を続けています。完了までお待ちください', 'kv'),
 ('task-ar','اكتملت الخطوة التالية بنجاح', 'plain'),
 ('task-fr','Mise à jour terminée : café et été', 'csv'),
 ('sensor-de','Messung übermittelt, Größe bestätigt', 'xml'),
 ('sensor-es','Actualización del panel: estación próxima', 'json'),
 ('sensor-emoji','Status 🟢 ready 🌍 queue 📦', 'kv'),
 ('holdout-ko','대시보드 상태를 업데이트했습니다', 'csv'),
 ('holdout-hi','कार्य की प्रगति अब उपलब्ध है', 'xml'),
 ('holdout-ru','Обновление панели завершено', 'json'),
 ('holdout-mixed','Local résumé e\u0301 / 完了 / 🍀', 'plain'),
]

def encode_payload(fmt:str, text:str, index:int, variant:int) -> str:
    if fmt=='json': return json.dumps({'step':index,'variant':variant,'status':text,'value':index*3+variant},ensure_ascii=False)
    if fmt=='csv': return f'{index},{variant},"{text}",{index*3+variant}'
    if fmt=='xml': return f'<update step="{index}" variant="{variant}"><status>{text}</status><value>{index*3+variant}</value></update>'
    if fmt=='kv': return f'step={index}; variant={variant}; status={text}; value={index*3+variant}'
    return f'Step {index}, variant {variant}: {text}; measured value {index*3+variant}.'

def author_stream(text:str, fmt:str, v:int, target:int=1152) -> bytes:
    endings=['\n','\r\n','\r']; e=endings[v%3]
    pieces=['\ufeff' if v%4==0 else '', ': ordinary dashboard updates'+e]
    # Metadata-only blocks must not become browser-style MessageEvents.
    if v%5==0: pieces+=['id: initial-'+str(v)+e, 'retry: 1200'+e, e]
    count=0
    while len(''.join(pieces).encode())<target:
        count+=1
        if count%3==1: pieces+=['id: '+str(v*100+count)+e]
        if count%5==0: pieces+=['id:'+e] # reset sticky ID
        if count%4==0: pieces+=[': keepalive '+text+e]
        if count%3==0: pieces+=['event: progress'+e]
        if count%4==1: pieces+=['retry: '+str(500+v*10)+e]
        payload=encode_payload(fmt,text,count,v)
        pieces+=['data: '+payload+e]
        if (count+v)%3==0: pieces+=['data: '+text+e]
        if (count+v)%4==0: pieces+=['x-note: ignored'+e]
        if (count+v)%7==0: pieces+=['Data: case-sensitive ignored'+e]
        pieces+=[e]
        if v%6==0 and count==2: pieces+=['data'+e,e] # empty-data event
        if v%7==0 and count==3: pieces+=['event: unused'+e,e] # no-data
    # A final incomplete block is retained as a semantic edge, never dispatched.
    if v%5==1: pieces+=['data: '+text] # unterminated line
    elif v%5==2: pieces+=['data: '+text+e] # terminated field but no blank line
    elif v%5==3: pieces+=[': final comment'+e]
    raw=''.join(pieces).encode()
    if len(raw)>65536: raise ValueError('bounded stream exceeded')
    return raw

def records():
    cases=[]
    for fi,(name,text,fmt) in enumerate(FAMILIES):
        for v in range(20):
            raw=author_stream(text,fmt,v)
            cases.append(dict(id=f'{name}-{v:02}',family=name,variant=v,
                              split='development' if fi<8 else 'holdout',cohort='main',
                              format=fmt,text=raw.decode(),source='authored',license='MIT'))
    # Larger cases are held out of scheduler development and control tuning.
    for fi in (1,7,8,11):
        name,text,fmt=FAMILIES[fi]
        for ki,target in enumerate((4096,16384,60000)):
            raw=author_stream(text,fmt,ki+8,target)
            cases.append(dict(id=f'long-{name}-{target}',family=name,variant=ki+8,
                              split='long',cohort='long',format=fmt,text=raw.decode(),
                              source='authored',license='MIT'))
    samples=[
      ('empty-data','data\n\n',['']),
      ('two-empty-data-fields','data\ndata\n\n',['\n']),
      ('incomplete-field','data:',[]),
      ('incomplete-block','data: not yet\n',[]),
      ('comment-block',': ordinary comment\n\n',[]),
      ('no-data-type','event: progress\n\n',[]),
      ('spaces','data:  one leading space retained\n\n',[' one leading space retained']),
      ('cr','data: value\r\r',['value']),
      ('crlf','data: value\r\n\r\n',['value']),
      ('lf','data: value\n\n',['value']),
      ('multiline','data: YHOO\ndata: +2\ndata: 10\n\n',['YHOO\n+2\n10']),
      ('sticky-id','id: 7\n\ndata: one\n\ndata: two\n\n',['one','two']),
      ('id-reset','id: 7\ndata: one\n\nid:\ndata: two\n\n',['one','two']),
      ('nul-id-ignore','id: 7\nid: a\0b\ndata: one\n\n',['one']),
      ('unknown','unknown: x\nData: not data\ndata: ok\n\n',['ok']),
      ('payload-feff','data: a\ufeffb\n\n',['a\ufeffb']),
      ('unicode-lines','data: a\u2028b\u0085c\v\f\n\n',['a\u2028b\u0085c\v\f']),
      ('application-sentinel','data: [DONE]\n\ndata: continues\n\n',['[DONE]','continues']),
    ]
    for name,text,want in samples:
        cases.append(dict(id='semantic-'+name,family='semantic',variant=0,split='conformance',cohort='conformance',format='plain',text=text,
                          source='authored-from-WHATWG-semantics',license='MIT',expected_data=want))
    wpt='data:msg\ndata: msg\n\n:\nfalsefield:msg\n\nfalsefield:msg\nData:data\n\ndata\n\ndata:end\n\n'
    cases.append(dict(id='wpt-event-data',family='wpt',variant=0,split='conformance',cohort='conformance',format='plain',text=wpt,
                      source='WPT event-data.any.js / resources/message2.py, one bounded iteration',license='BSD-3-Clause',expected_data=['msg\nmsg','','end']))
    for name,text,want in [('bom-hello','\ufeffdata: hello\n\n',['hello']),
                           ('bom-multiline','\ufeffdata: first\ndata: second\n\n',['first\nsecond']),
                           ('bom-two-events','\ufeffdata: first\n\ndata: second\n\n',['first','second'])]:
        cases.append(dict(id='upstream-'+name,family='eventsource-parser-tests',variant=0,split='conformance',cohort='conformance',format='plain',text=text,
                          source='eventsource-parser v4.1.1 test/parse.test.ts lines 153--198; byte-adapted',license='MIT-upstream',expected_data=want))
    for c in cases:
        raw=c['text'].encode();c['bytes']=len(raw);c['expected']=evaluate(raw)
        if 'expected_data' in c: assert [e['data'] for e in c['expected']['events']]==c['expected_data'],c['id']
    assert len({c['text'] for c in cases})==len(cases),'unexpected duplicate fixture'
    return cases

def main():
    cases=records(); p=Path('corpus');p.mkdir(exist_ok=True)
    (p/'corpus.json').write_text(json.dumps({'schema':1,'cases':cases},ensure_ascii=False,indent=2)+'\n')
    print(f'{len(cases)} fixtures, {sum(c["bytes"] for c in cases)} bytes')
if __name__=='__main__': main()
