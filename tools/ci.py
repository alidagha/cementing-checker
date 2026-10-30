"""Whole-module three-shard proposal; fail closed on collection or phase gaps."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import importlib.metadata

ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def lock_identity(root):
    lock=json.loads((root/'upstream.lock.json').read_text())
    return {'schedule':digest(root/'tools/test-schedule.json'),
            'source_lock':digest(root/'upstream.lock.json'),
            'accepted_lock':digest(root/'accepted.lock.json'),
            'requirements':digest(root/'requirements.txt'),
            'upstream_commit':lock['commit'],
            'snapshot_manifest':lock['snapshot_manifest_sha256'],
            'python':sys.version.split()[0]}

def capture_checkout(root, destination):
    expected=os.environ['CHECKER_TESTED_HEAD']
    if len(expected)!=40 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError('Full tested head SHA required')
    def git(*args):
        return subprocess.check_output(['git','-C',str(root),*args],
            env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'),text=True).strip()
    if git('rev-parse','HEAD')!=expected or git('rev-parse','--is-shallow-repository')!='false':
        raise ValueError('Checkout head/shallow identity mismatch')
    if Path(git('rev-parse','--show-toplevel')).resolve()!=root.resolve() or git('status','--porcelain=v1'):
        raise ValueError('Checkout root must be exact and clean')
    for entry in json.loads((root/'accepted.lock.json').read_text())['files']:
        if digest(root/entry['path'])!=entry['sha256']:
            raise ValueError('Accepted source/test identity mismatch')
    identity=dict(lock_identity(root),head=expected,tree=git('rev-parse','HEAD^{tree}'),
        run=os.environ['GITHUB_RUN_ID'],attempt=os.environ['GITHUB_RUN_ATTEMPT'])
    if not identity['run'].isdigit() or not identity['attempt'].isdigit():
        raise ValueError('GitHub run/attempt required')
    destination.write_text(json.dumps(identity,sort_keys=True,indent=2))
    return identity

def execution_identity(root=ROOT):
    locks=lock_identity(root)
    if os.environ.get('GITHUB_ACTIONS')!='true':
        return dict(locks,head='LOCAL_UNCOMMITTED',tree='LOCAL',run='LOCAL',attempt='LOCAL')
    identity=json.loads(Path(os.environ['CHECKER_CHECKOUT_PROOF']).read_text())
    expected=dict(locks,head=os.environ['CHECKER_TESTED_HEAD'],tree=identity['tree'],
        run=os.environ['GITHUB_RUN_ID'],attempt=os.environ['GITHUB_RUN_ATTEMPT'])
    if identity!=expected or len(identity['tree'])!=40:
        raise ValueError('Verified checkout/run/attempt/lock drift')
    return identity

def source_proof(root=ROOT):
    lock=json.loads((root/'upstream.lock.json').read_text())
    manifest=root/'evidence/snapshot.sha256'
    if digest(manifest)!=lock['snapshot_manifest_sha256']:
        raise ValueError('Snapshot manifest mismatch')
    snapshot=root/'snapshot'
    expected={item['path'] for item in lock['files']}
    if {str(p.relative_to(snapshot)) for p in snapshot.rglob('*') if p.is_file()}!=expected:
        raise ValueError('Snapshot file-set mismatch')
    for item in lock['files']:
        path=snapshot/item['path']
        if path.is_symlink() or not path.resolve().is_relative_to(snapshot.resolve()):
            raise ValueError('Snapshot path escape')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['sha256'] or hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=item['git_blob']:
            raise ValueError('Snapshot source/blob mismatch')
    return {'upstream_commit':lock['commit'],'template_blob':lock['template_blob'],
            'manifest':digest(manifest),'source_lock':digest(root/'upstream.lock.json'),
            'verified_files':len(expected)}

def pinned_packages(root=ROOT):
    return dict(line.strip().split('==') for line in (root/'requirements.txt').read_text().splitlines()
                if line.strip() and not line.startswith('#'))

def environment_proof(root=ROOT):
    packages={name:importlib.metadata.version(name) for name in pinned_packages(root)}
    if packages!=pinned_packages(root):
        raise ValueError('Installed dependency version drift')
    return {'python':sys.version.split()[0],'requirements':digest(root/'requirements.txt'),'packages':packages}

def seal(evidence, shard, identity):
    files={}
    for name in ('collection.json',shard+'.json','source.json','environment.json'):
        p=evidence/name
        if p.is_symlink():raise ValueError('Evidence symlink')
        files[name]={'sha256':digest(p),'bytes':p.stat().st_size}
    manifest={'identity':identity,'shard':shard,'files':files}
    (evidence/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2))
    return manifest

def read_bundle(folder, shard, identity):
    if folder.is_symlink() or (folder/'manifest.json').is_symlink():
        raise ValueError('Evidence symlink')
    manifest=json.loads((folder/'manifest.json').read_text())
    names={'collection.json',shard+'.json','source.json','environment.json'}
    if manifest['identity']!=identity or manifest['shard']!=shard or set(manifest['files'])!=names:
        raise ValueError('Artifact run/attempt/shard or allowlist mismatch')
    if {p.name for p in folder.iterdir()}!=names|{'manifest.json'}:
        raise ValueError('Unexpected artifact files')
    data={}
    for name,entry in manifest['files'].items():
        p=folder/name
        if p.is_symlink() or entry!={'sha256':digest(p),'bytes':p.stat().st_size}:
            raise ValueError('Evidence checksum/size mismatch')
        data[name]=json.loads(p.read_text())
    return data,manifest

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

def certify(discovery, shards, schedule, expected_identity=None):
    expected=validate_discovery(discovery['nodeids'],schedule)
    if discovery['exitstatus'] or discovery['warnings']:
        raise ValueError('Discovery failure/warning')
    if expected_identity is not None and discovery.get('identity')!=expected_identity:
        raise ValueError('Evidence does not belong to this checkout/run/attempt')
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
            'identity':discovery.get('identity'),
            'shard_tests':{k:len(v) for k,v in expected.items()},
            'whole_program_certification':False}

def execute(root,args,output):
    environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(root/'tmp'),
        XDG_CACHE_HOME=str(root/'cache'),XDG_CONFIG_HOME=str(root/'cache/config'),MPLCONFIGDIR=str(root/'cache/mpl'))
    command=[sys.executable,'-B','-m','pytest','-p','no:cacheprovider','--audit-file',str(output),*args]
    print(json.dumps({'command':command,'cwd':str(root)}),flush=True)
    return subprocess.run(command,cwd=root,env=environment).returncode

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['checkout','collect','run','seal','certify'])
    parser.add_argument('--shard',choices=list('ABC'))
    parser.add_argument('--evidence',type=Path)
    args=parser.parse_args()
    schedule=load_schedule()
    if args.action=='checkout':
        print(json.dumps(capture_checkout(ROOT,Path(os.environ['CHECKER_CHECKOUT_PROOF']))))
        return
    identity=execution_identity()
    evidence=args.evidence or ROOT/'evidence/native'
    evidence.mkdir(parents=True,exist_ok=True)
    if args.action=='collect':
        (evidence/'source.json').write_text(json.dumps(source_proof(),sort_keys=True,indent=2))
        (evidence/'environment.json').write_text(json.dumps(environment_proof(),sort_keys=True,indent=2))
        code=execute(ROOT,['--collect-only','-q'],evidence/'collection.json')
        if code:raise SystemExit(code)
        print(json.dumps(validate_discovery(json.loads((evidence/'collection.json').read_text())['nodeids'],schedule)))
    elif args.action=='run':
        if not args.shard:parser.error('--shard required')
        discovery=json.loads((evidence/'collection.json').read_text())
        if discovery['identity']!=identity:raise ValueError('Stale discovery')
        source_proof()
        selected=validate_discovery(discovery['nodeids'],schedule)[args.shard]
        modules=list(dict.fromkeys(n.split('::',1)[0] for n in selected))
        code=execute(ROOT,[*modules,'-q'],evidence/(args.shard+'.json'))
        raise SystemExit(code)
    elif args.action=='seal':
        if not args.shard:parser.error('--shard required')
        if json.loads((evidence/'source.json').read_text())!=source_proof():
            raise ValueError('Source drift during tests')
        print(json.dumps(seal(evidence,args.shard,identity)))
    else:
        manifests={}
        if (evidence/'collection.json').exists():
            if os.environ.get('GITHUB_ACTIONS')=='true':
                raise ValueError('Hosted certification requires three sealed independent artifacts')
            discovery=json.loads((evidence/'collection.json').read_text())
            shards={s:json.loads((evidence/(s+'.json')).read_text()) for s in 'ABC'}
        else:
            prefix='native-'+identity['run']+'-'+identity['attempt']+'-'
            if {p.name for p in evidence.iterdir()}!={prefix+s for s in 'ABC'}:
                raise ValueError('Missing/duplicate/stale shard artifacts')
            bundles={}
            for s in 'ABC':
                bundles[s],manifests[s]=read_bundle(evidence/(prefix+s),s,identity)
                source=bundles[s]['source.json'];environment=bundles[s]['environment.json']
                if source['source_lock']!=identity['source_lock'] or source['manifest']!=identity['snapshot_manifest'] or source['upstream_commit']!=identity['upstream_commit'] or source['verified_files']!=143:
                    raise ValueError('Source verification evidence mismatch')
                if environment!={'python':identity['python'],'requirements':identity['requirements'],'packages':pinned_packages()}:
                    raise ValueError('Environment evidence mismatch')
            collections=[bundles[s]['collection.json'] for s in 'ABC']
            if not all(d==collections[0] for d in collections):
                raise ValueError('Independent native discovery drift')
            discovery=collections[0]
            shards={s:bundles[s][s+'.json'] for s in 'ABC'}
        result=certify(discovery,shards,schedule,identity)
        result.update(authority='GITHUB_ACTIONS_CURRENT_SCOPE' if os.environ.get('GITHUB_ACTIONS')=='true' else 'LOCAL_ONLY_NOT_CERTIFICATION',
                      artifact_manifests=manifests)
        certificate=evidence/'certificate.json'
        certificate.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
        (evidence/'certificate.sha256').write_text(digest(certificate)+'  certificate.json\n')
        print(json.dumps(result))

if __name__=='__main__':main()
