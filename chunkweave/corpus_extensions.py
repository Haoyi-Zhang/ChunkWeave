"""144 policy-fixed, valid, bounded functional fixtures."""
from __future__ import annotations
import json
from .oracle import evaluate
from .validation_corpus import all_cases

FAMILIES=('progress-json','retry-cycles','data-whitespace','callback-tail',
          'metadata-only','incomplete-suffix','mixed-endings','unicode-planes')
WORDS=('完成','prêt','готово','جاهز','完了','준비','έτοιμο','तैयार','🌍','café','naïve','e\u0301')


def new_cases() -> list[dict]:
    result=[]
    previous={c['text'] for c in all_cases()}
    for family in FAMILIES:
        for v in range(18):
            word=WORDS[v % len(WORDS)]
            end=('\n','\r\n','\r')[v % 3]
            # A unique ordinary progress identifier is part of the actual data.
            identity=f'structural-{family}-{v:02d}'
            if family=='progress-json':
                obj={'task':identity,'step':v,'state':word,'ready':bool(v%2)}
                text=('id: '+str(100+v)+end+'event: progress'+end+
                      'data: '+json.dumps(obj,ensure_ascii=False,separators=(',',':'))+end+end+
                      'data: '+word+' / finished'+end+end)
            elif family=='retry-cycles':
                text=('retry: '+str(500+v)+end+'data: '+word+' '+identity+end+end+
                      'retry: '+str(1500+v)+end+'data: '+word+' next'+end+end+
                      'retry: ignored'+end+'data: complete'+end+end)
            elif family=='data-whitespace':
                text=('data: '+identity+end+end+'data:'+end+'data:  '+word+end+
                      'data:\t'+word+end+'data: '+str(v)+end+end)
            elif family=='callback-tail':
                gap=(0,3,11,31,127,509)[v%6]
                text=('data: '+identity+end+end+'data: '+('a'*gap)+word+end+end+
                      'data: done '+word+end+end)
            elif family=='metadata-only':
                text=('id: '+identity+end+end+'retry: '+str(v)+end+end+
                      'event: unused'+end+end+'data: '+word+end+end+
                      'id:'+end+'data: next '+word+end+end)
            elif family=='incomplete-suffix':
                tail=('data: pending '+word,'data: pending '+word+end,
                      'id: uncommitted'+end+'data: '+word)[v%3]
                text='data: '+identity+end+end+tail
            elif family=='mixed-endings':
                ls=[': '+identity,'id: '+str(v),'data: '+word,'','retry: 21',
                    'event: progress','data: next '+word,'','data: final','']
                text=''.join(line+('\n','\r\n','\r')[(i+v)%3] for i,line in enumerate(ls))
            else:
                # Distinct valid scalar boundaries, including legitimate payload
                # BOM and replacement characters outside the narrower theorem.
                codes=(0x80,0x7ff,0x800,0xd7ff,0xe000,0xfeff,0xfffd,0x10000,0x10ffff)
                payload=''.join(chr(codes[(v+i)%len(codes)]) for i in range(5))
                text=('data: '+identity+end+end+'data: '+payload+end+end+
                      'data: '+word+end+end)
            if v%6==0:
                text='\ufeff'+text
            assert text not in previous,(family,v)
            raw=text.encode('utf-8');assert len(raw)<=65536
            result.append(dict(id=identity,family=family,variant=v,cohort='structural',
                split='policy-fixed-structural',source='authored after the test policy was fixed',
                license='MIT',text=text,bytes=len(raw),expected=evaluate(raw)))
    assert len(result)==144 and len({c['text'] for c in result})==144
    return result


def cases() -> list[dict]:
    return all_cases()+new_cases()

if __name__=='__main__':
    from pathlib import Path
    c=cases();p=Path('corpus/corpus.json')
    p.write_text(json.dumps({'schema':1,'cases':c},ensure_ascii=False,indent=2)+'\n')
    print(len(c),'unique streams;',sum(x['bytes'] for x in c),'bytes;',max(x['bytes'] for x in c),'max')
