"""Valid structural fixtures authored after the selector specification.

These are structural validation extensions, not mined bugs, production samples,
independent human holdouts, or a substitute for the complete upstream suites.
"""
from __future__ import annotations
import json
from pathlib import Path
from .corpus import records
from .oracle import evaluate

FAMILIES=('mixed-endings','metadata-transitions','empty-data-runs','scalar-widths',
          'decoder-lifetime','no-dispatch-suffix','nested-dashboard','long-single-field')


def extensions():
    out=[]
    widths=['a','é','中','🌍','aé中🌍','e\u0301']
    for family in FAMILIES:
        for v in range(12):
            e=('\n','\r\n','\r')[v%3]; payload=widths[v%len(widths)]
            if family=='mixed-endings':
                l=[': bounded mixed line endings','id: '+str(v),'event: progress',
                   'data: step '+str(v),'data: '+payload,'','data: next '+payload,'']
                text=''.join(x+(' \n' if False else ('\n','\r\n','\r')[(i+v)%3]) for i,x in enumerate(l))
            elif family=='metadata-transitions':
                l=['id: initial-'+str(v),'','data: '+payload,'','id:','',
                   'event: unused','','id: 7','id: keep\0ignored',
                   'data: '+str(v),'','retry: 0','retry: 1500','']
                text=e.join(l)+e
            elif family=='empty-data-runs':
                l=['data:','data: '+payload,'','data:','data:',
                   'data: '+str(v),'','data','data: tail','']
                text=e.join(l)+e
            elif family=='scalar-widths':
                cps=[0x7F,0x80,0x7FF,0x800,0xD7FF,0xE000,0xFFFF,0x10000,0x10FFFF]
                text='data: '+str(v)+' '+''.join(chr(c) for c in cps[v%3:])+e+e
            elif family=='decoder-lifetime':
                text=('id: '+str(v)+e+'data: first'+e+e+
                      'data: '+payload*3+e+e+'data: last '+payload+e+e)
            elif family=='no-dispatch-suffix':
                tail=('data: tail '+payload,'data: tail '+payload+e,'event: pending'+e)[v%3]
                text='data: delivered '+str(v)+e+e+tail
            elif family=='nested-dashboard':
                obj={'batch':v,'steps':[{'name':payload,'done':True},{'name':'next','done':False}],
                     'description':'ordinary local status updates'}
                # JSON is an application payload, not interpreted by SSE.
                text=('id: '+str(v)+e+'event: progress'+e+'data: '+
                      json.dumps(obj,ensure_ascii=False,separators=(',',':'))+e+e+
                      ': keepalive'+e+'data: '+payload+e+e)
            else:
                # Distinct long fields exercise trace complexity; still <=64 KiB.
                target=(1024,4096,16384,60000)[v//3]
                prefix='data: '+str(v)+' '
                text=prefix+'x'*(target-len(prefix.encode())-len((e+e).encode()))+e+e
            if v%4==0:text='\ufeff'+text
            out.append(dict(id=f'validation-{family}-{v:02}',family='validation-'+family,
                            variant=v,split='new-validation',cohort='validation',format='mixed',
                            source='authored structural validation extension',license='MIT',text=text))
    # Hand-written expected observations: no calls to either evaluator define them.
    truths=[
      ('double-leading-bom','\ufeff\ufeffdata: hidden\n\ndata: visible\n\n',[('message','visible','')],[],''),
      ('bom-in-value','data:\ufeffvalue\n\n',[('message','\ufeffvalue','')],[],''),
      ('midstream-bom-field','data:first\n\n\ufeffdata:hidden\n\ndata:last\n\n',
       [('message','first',''),('message','last','')],[],''),
      ('one-leading-space','data:  x\n\n',[('message',' x','')],[],''),
      ('tab-not-space','data:\tx\n\n',[('message','\tx','')],[],''),
      ('empty-before-nonempty','data:\ndata:x\n\n',[('message','\nx','')],[],''),
      ('two-empty','data:\ndata:\n\n',[('message','\n','')],[],''),
      ('bare-empty','data\n\n',[('message','','')],[],''),
      ('bare-before-nonempty','data\ndata:x\n\n',[('message','\nx','')],[],''),
      ('signed-retry','retry:+3\ndata:x\n\n',[('message','x','')],[],''),
      ('suffix-retry','retry:3ms\ndata:x\n\n',[('message','x','')],[],''),
      ('unicode-retry','retry:１２\ndata:x\n\n',[('message','x','')],[],''),
      ('space-retry','retry:  3\ndata:x\n\n',[('message','x','')],[],''),
      ('zero-retry','retry:0\ndata:x\n\n',[('message','x','')],[0],''),
      ('empty-id-reset','id:a\ndata:x\n\nid:\ndata:y\n\n',[('message','x','a'),('message','y','')],[],''),
      ('nul-id-ignore','id:a\nid:\0b\ndata:x\n\n',[('message','x','a')],[],'a'),
      ('id-not-committed','id:a\ndata:x\n\nid:b\n',[('message','x','a')],[],'a'),
      ('type-reset-no-data','event:custom\n\ndata:x\n\n',[('message','x','')],[],''),
      ('empty-type-reset','event:custom\nevent:\ndata:x\n\n',[('message','x','')],[],''),
      ('unterminated-no-event','data:x',[],[],''),
      ('terminated-no-blank','data:x\n',[],[],''),
      ('cr-at-eof','data:x\r\r',[('message','x','')],[],''),
      ('unicode-not-newline','data:a\u2028b\u0085c\v\f\n\n',[('message','a\u2028b\u0085c\v\f','')],[],''),
      ('case-sensitive-field','Data:hidden\ndata:visible\n\n',[('message','visible','')],[],''),
    ]
    for name,text,events,retries,last in truths:
        expected={'events':[dict(type=t,data=d,id=i) for t,d,i in events],
                  'retries':retries,'last_event_id':last}
        out.append(dict(id='truth-'+name,family='truth-table',variant=0,split='semantic-extension',
                        cohort='truth',format='plain',source='authored normative truth table',license='MIT',
                        text=text,manual_expected=expected))
    for c in out:
        c['bytes']=len(c['text'].encode());c['expected']=evaluate(c['text'].encode())
        if 'manual_expected' in c:assert c['manual_expected']==c['expected'],c['id']
    assert len({x['text'] for x in out})==len(out)
    return out


def all_cases():
    unique={}
    for c in records()+extensions():
        if c['text'] in unique:
            first=unique[c['text']]
            first.setdefault('validation_aliases',[]).append(c['id'])
            if 'manual_expected' in c:first['manual_expected']=c['manual_expected']
        else:unique[c['text']]=c
    return list(unique.values())

if __name__=='__main__':
    cases=all_cases();p=Path('corpus/base-corpus.json');p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps({'schema':1,'cases':cases},ensure_ascii=False,indent=2)+'\n')
    print(len(cases),'case records;',len({c['text'] for c in cases}),'unique streams;',sum(c['bytes'] for c in cases),'bytes')
