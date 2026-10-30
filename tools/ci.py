"""Whole-module three-shard proposal; fail closed on collection or phase gaps."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def load_schedule(root=ROOT):
    raw=(root/'tools/test-schedule.json').read_bytes()
    expected=(root/'tools/test-schedule.sha256').read_text().split()[0]
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('Schedule final-byte digest mismatch')
    schedule=json.loads(raw)
    if set(schedule)!=set('ABC'):
        raise ValueError('Exactly three whole-module shards required')
    flat=[p for group in schedule.values() for p in group]
    if len(flat)!=len(set(flat)):
        raise ValueError('Overlapping module ownership')
    for name in flat:
        if Path(name).is_absolute() or '..' in Path(name).parts or not name.endswith('.py'):
            raise ValueError('Invalid module path')
    return schedule

def validate_discovery(nodeids,schedule):
    if not nodeids or len(nodeids)!=len(set(nodeids)):
        raise ValueError('Empty/duplicate native collection')
    modules={n.split('::',1)[0] for n in nodeids}
    planned=[n for group in schedule.values() for n in group]
    if len(planned)!=len(set(planned)) or set(planned)!=modules:
        raise ValueError('Module gap, overlap or stale schedule entry')
    return {s:[n for n in nodeids if n.split('::',1)[0] in files] for s,files in schedule.items()}

def certify(discovery, shards, schedule):
    expected=validate_discovery(discovery['nodeids'],schedule)
    if discovery['exitstatus'] or discovery['warnings']:
        raise ValueError('Discovery failure/warning')
    if set(shards)!=set('ABC'):
        raise ValueError('Missing shard evidence')
    for name,data in shards.items():
        if data.get('identity')!=discovery.get('identity'):
            raise ValueError('Head/run/attempt/schedule identity drift')
        if data['exitstatus'] or data['warnings'] or data['nodeids']!=expected[name]:
            raise ValueError('Shard collection/status mismatch: '+name)
        wanted={(n,p) for n in expected[name] for p in ('setup','call','teardown')}
        seen=[]
        for r in data['reports']:
            if r['outcome']!='passed' or r['xfail']:
                raise ValueError('Nonpassing phase/xfail')
            seen.append((r['nodeid'],r['phase']))
        if len(seen)!=len(set(seen)) or set(seen)!=wanted:
            raise ValueError('Missing/duplicate test phase')
    return {'status':'FOCUSED_THREE_SHARD_PASS','tests':len(discovery['nodeids']),
            'modules':{k:len(v) for k,v in schedule.items()},
            'whole_program_certification':False}

def execute(root,args,output):
    environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(root/'tmp'),
        XDG_CACHE_HOME=str(root/'cache'),XDG_CONFIG_HOME=str(root/'cache/config'),MPLCONFIGDIR=str(root/'cache/mpl'))
    command=[sys.executable,'-B','-m','pytest','-p','no:cacheprovider','--audit-file',str(output),*args]
    print(json.dumps({'command':command,'cwd':str(root)}),flush=True)
    return subprocess.run(command,cwd=root,env=environment).returncode

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['collect','run','certify'])
    parser.add_argument('--shard',choices=list('ABC'))
    parser.add_argument('--evidence',type=Path)
    args=parser.parse_args()
    schedule=load_schedule()
    evidence=args.evidence or ROOT/'evidence/native'
    evidence.mkdir(parents=True,exist_ok=True)
    if args.action=='collect':
        code=execute(ROOT,['--collect-only','-q'],evidence/'collection.json')
        if code:raise SystemExit(code)
        print(json.dumps(validate_discovery(json.loads((evidence/'collection.json').read_text())['nodeids'],schedule)))
    elif args.action=='run':
        if not args.shard:parser.error('--shard required')
        discovery=json.loads((evidence/'collection.json').read_text())
        selected=validate_discovery(discovery['nodeids'],schedule)[args.shard]
        modules=list(dict.fromkeys(n.split('::',1)[0] for n in selected))
        code=execute(ROOT,[*modules,'-q'],evidence/(args.shard+'.json'))
        raise SystemExit(code)
    else:
        if (evidence/'collection.json').exists():
            discovery=json.loads((evidence/'collection.json').read_text())
            shards={s:json.loads((evidence/(s+'.json')).read_text()) for s in 'ABC'}
        else:
            collections=[json.loads((evidence/('native-'+s)/'collection.json').read_text()) for s in 'ABC']
            if not all(d==collections[0] for d in collections):
                raise ValueError('Independent native discovery drift')
            discovery=collections[0]
            shards={s:json.loads((evidence/('native-'+s)/(s+'.json')).read_text()) for s in 'ABC'}
        result=certify(discovery,shards,schedule)
        (evidence/'certificate.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result))

if __name__=='__main__':main()
