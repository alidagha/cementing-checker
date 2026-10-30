"""Small mutation controls for source locking, public exclusion and CI admission."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import pytest
from tools import ci,provision,public_scan

def certificate_fixture():
    schedule={'A':['test_a.py'],'B':['test_b.py'],'C':['test_c.py']}
    nodes=[m[0]+'::test_one' for m in schedule.values()]
    discovery={'nodeids':nodes,'exitstatus':0,'warnings':[]}
    shards={s:{'nodeids':[m[0]+'::test_one'],'exitstatus':0,'warnings':[],
        'reports':[{'nodeid':m[0]+'::test_one','phase':p,'outcome':'passed','xfail':False} for p in ('setup','call','teardown')]} for s,m in schedule.items()}
    return schedule,discovery,shards

def test_complete_native_routing_and_phase_evidence():
    s,d,r=certificate_fixture()
    assert ci.certify(d,r,s)['tests']==3
    for kind in ('gap','overlap','skip','phase','missing-shard','warning','drift'):
        ss,dd,rr=deepcopy((s,d,r))
        if kind=='gap':ss['A']=[]
        if kind=='overlap':ss['B']+=ss['A']
        if kind=='skip':rr['A']['reports'][1]['outcome']='skipped'
        if kind=='phase':rr['A']['reports'].pop()
        if kind=='missing-shard':rr.pop('C')
        if kind=='warning':rr['A']['warnings']=['warning']
        if kind=='drift':rr['A']['nodeids']=['test_a.py::unknown']
        with pytest.raises(ValueError):ci.certify(dd,rr,ss)

def test_final_schedule_bytes_hash_and_mutation(tmp_path):
    (tmp_path/'tools').mkdir()
    raw=json.dumps(certificate_fixture()[0]).encode()
    schedule=tmp_path/'tools/test-schedule.json';schedule.write_bytes(raw)
    (tmp_path/'tools/test-schedule.sha256').write_text(hashlib.sha256(raw).hexdigest())
    assert ci.load_schedule(tmp_path)==certificate_fixture()[0]
    schedule.write_bytes(raw+b' ')
    with pytest.raises(ValueError,match='digest'):ci.load_schedule(tmp_path)

def archive(name='root/file.py',data=b'original',link=False):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as t:
        m=tarfile.TarInfo(name)
        if link:m.type=tarfile.SYMTYPE;m.linkname='/tmp/escape'
        else:m.size=len(data)
        t.addfile(m,None if link else io.BytesIO(data))
    return stream.getvalue()

def test_external_source_lock_and_archive_escape_fail_closed():
    data=b'original';lock={'files':[{'path':'file.py','sha256':hashlib.sha256(data).hexdigest(),
        'git_blob':hashlib.sha1(b'blob 8\0'+data).hexdigest()}]}
    assert provision.verify_members(archive(),lock)=={'file.py':data}
    for raw in (archive(data=b'changed'),archive('../escape'),archive(link=True),archive('root/extra.py')):
        with pytest.raises(ValueError):provision.verify_members(raw,lock)

def test_public_inventory_and_secret_private_controls(tmp_path):
    p=tmp_path/'readme.md';p.write_text('Fresh generic test text')
    assert public_scan.scan(tmp_path)[0]['classification'].startswith('PROPOSED PUBLIC')
    p.write_text('ghp_'+'x'*36)
    with pytest.raises(ValueError):public_scan.scan(tmp_path)
    p.write_text('ok');(tmp_path/'private.docx').write_bytes(b'not public')
    with pytest.raises(ValueError):public_scan.scan(tmp_path)

def test_accepted_source_and_test_identity():
    provision.verify_candidate(Path(__file__).resolve().parents[1])

def test_provision_never_overwrites_or_uses_candidate(tmp_path):
    with pytest.raises(ValueError,match='new'):provision.create(tmp_path)
    with pytest.raises(ValueError,match='separate'):provision.create(provision.ROOT/'new-child')

def test_provision_from_actual_git_checkout_excludes_only_git(tmp_path,monkeypatch):
    import shutil
    import subprocess
    checkout=tmp_path/'checkout';checkout.mkdir()
    template=tmp_path/'empty-template';template.mkdir()
    subprocess.run(['git','init','-q','--template='+str(template),'--initial-branch=fixture',str(checkout)],check=True)
    (checkout/'.git/private-marker').write_text('metadata must never be copied')
    original=Path(__file__).resolve().parents[1]
    accepted=json.loads((original/'accepted.lock.json').read_text())
    for item in [*accepted['files'],{'path':'accepted.lock.json'}]:
        target=checkout/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(original/item['path'],target)
    # A tiny independently hashed transport fixture exercises the real verifier;
    # hosted provisioning separately verifies every one of the 143 pinned files.
    data=b'original';manifest=hashlib.sha256(data).hexdigest()+'  snapshot/file.py\n'
    lock=json.loads((original/'upstream.lock.json').read_text())
    lock['files']=[{'path':'file.py','sha256':hashlib.sha256(data).hexdigest(),
                   'git_blob':hashlib.sha1(b'blob 8\0'+data).hexdigest()}]
    lock['snapshot_manifest_sha256']=hashlib.sha256(manifest.encode()).hexdigest()
    (checkout/'upstream.lock.json').write_text(json.dumps(lock))
    monkeypatch.setattr(provision,'ROOT',checkout)
    monkeypatch.setattr(provision.urllib.request,'urlopen',lambda *a,**k:io.BytesIO(archive()))
    destination=tmp_path/'runtime'
    result=provision.create(destination)
    assert result['verified_source_files']==1
    assert (destination/'snapshot/file.py').read_bytes()==data
    assert not any('.git' in p.relative_to(destination).parts for p in destination.rglob('*'))
    provision.verify_candidate(destination)
    (checkout/'escape').symlink_to(tmp_path/'outside')
    with pytest.raises(ValueError,match='symlink'):provision.create(tmp_path/'reject-link')
    (checkout/'escape').unlink()
    (checkout/'.runtime').mkdir();(checkout/'.runtime/private').write_text('private generated data')
    with pytest.raises(ValueError,match='generated'):provision.create(tmp_path/'reject-generated')

def test_strict_hosted_identity_and_nonpassing_evidence_controls():
    s,d,r=certificate_fixture()
    identity={'head':'a'*40,'tree':'b'*40,'run':'123','attempt':'2','schedule':'c'*64,
              'source_lock':'d'*64,'accepted_lock':'e'*64,'requirements':'f'*64}
    d['identity']=deepcopy(identity)
    for shard in r.values():shard['identity']=deepcopy(identity)
    assert ci.certify(d,r,s,identity)['identity']==identity
    for key in identity:
        dd,rr=deepcopy((d,r));dd['identity'][key]='stale'
        for shard in rr.values():shard['identity'][key]='stale'
        with pytest.raises(ValueError):ci.certify(dd,rr,s,identity)
    for kind in ('missing-identity','duplicate-phase','xfail','setup-fail','teardown-fail'):
        dd,rr=deepcopy((d,r))
        if kind=='missing-identity':dd.pop('identity')
        elif kind=='duplicate-phase':rr['A']['reports'].append(deepcopy(rr['A']['reports'][0]))
        elif kind=='xfail':rr['A']['reports'][1]['xfail']=True
        elif kind=='setup-fail':rr['A']['reports'][0]['outcome']='failed'
        else:rr['A']['reports'][2]['outcome']='failed'
        with pytest.raises(ValueError):ci.certify(dd,rr,s,identity)

def test_artifact_manifest_checksum_allowlist_and_attempt_controls(tmp_path):
    identity={'head':'a'*40,'run':'123','attempt':'2'}
    for name in ('collection.json','A.json','source.json','environment.json'):
        (tmp_path/name).write_text('{}')
    ci.seal(tmp_path,'A',identity)
    assert ci.read_bundle(tmp_path,'A',identity)[1]['identity']==identity
    with pytest.raises(ValueError):ci.read_bundle(tmp_path,'A',dict(identity,attempt='1'))
    (tmp_path/'A.json').write_text('{"changed":true}')
    with pytest.raises(ValueError,match='checksum'):ci.read_bundle(tmp_path,'A',identity)
    (tmp_path/'A.json').write_text('{}');(tmp_path/'extra.json').write_text('{}')
    with pytest.raises(ValueError,match='Unexpected'):ci.read_bundle(tmp_path,'A',identity)
    (tmp_path/'extra.json').unlink();(tmp_path/'source.json').unlink()
    with pytest.raises(ValueError):ci.read_bundle(tmp_path,'A',identity)

def test_checkout_proof_uses_real_clean_git_head(tmp_path,monkeypatch):
    import shutil
    import subprocess
    checkout=tmp_path/'checkout';checkout.mkdir()
    template=tmp_path/'template';template.mkdir()
    def git(*args):
        return subprocess.check_output(['git','-C',str(checkout),*args],text=True).strip()
    git('init','-q','--template='+str(template),'--initial-branch=fixture')
    git('config','user.name','CI Fixture');git('config','user.email','fixture@example.invalid')
    root=Path(__file__).resolve().parents[1]
    names=[x['path'] for x in json.loads((root/'accepted.lock.json').read_text())['files']]
    names+=['accepted.lock.json','upstream.lock.json','requirements.txt','tools/test-schedule.json']
    for name in names:
        target=checkout/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target)
    git('add','--',*names);git('-c','commit.gpgsign=false','commit','-qm','Synthetic checkout identity control')
    head=git('rev-parse','HEAD');proof=tmp_path/'proof.json'
    monkeypatch.setenv('CHECKER_TESTED_HEAD',head);monkeypatch.setenv('GITHUB_RUN_ID','123');monkeypatch.setenv('GITHUB_RUN_ATTEMPT','2')
    actual=ci.capture_checkout(checkout,proof)
    assert actual['head']==head and actual['tree']==git('rev-parse','HEAD^{tree}')
    monkeypatch.setenv('GITHUB_ACTIONS','true');monkeypatch.setenv('CHECKER_CHECKOUT_PROOF',str(proof))
    assert ci.execution_identity(checkout)==actual
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT','3')
    with pytest.raises(ValueError):ci.execution_identity(checkout)
    monkeypatch.setenv('CHECKER_TESTED_HEAD','0'*40)
    with pytest.raises(ValueError,match='Checkout'):ci.capture_checkout(checkout,tmp_path/'rejected.json')


def test_ci01_workflow_event_and_dependency_structure():
    text=(Path(__file__).resolve().parents[1]/'.github/workflows/checker-regression.yml').read_text()
    assert text.split('permissions:',1)[0]==('name: checker-regression\non:\n'
        '  pull_request:\n    branches: [main]\n  push:\n    branches: [main]\n')
    fast=text.split('  fast-gate:\n',1)[1].split('  focused:\n',1)[0]
    focused=text.split('  focused:\n',1)[1].split('  regression:\n',1)[0]
    aggregate=text.split('  regression:\n',1)[1]
    for block in (fast,focused,aggregate):
        assert 'fetch-depth: 0' in block and 'python -B tools/ci.py checkout' in block
        assert 'test "$(git rev-parse HEAD)" = "$CHECKER_TESTED_HEAD"' in block
    assert 'pip install' not in fast and 'provision.py' not in fast and 'ci.py collect' not in fast
    assert "    if: github.event_name == 'pull_request'\n    needs: fast-gate\n" in focused
    assert 'fail-fast: false' in focused and 'shard: [A, B, C]' in focused
    assert '    if: always()\n    needs: [fast-gate, focused]\n' in aggregate
    assert 'CHECKER_NEEDS_JSON: ${{ toJSON(needs) }}' in aggregate
    assert aggregate.index('python -B tools/ci.py gate')<aggregate.index('actions/download-artifact@')
    # Every artifact/certificate step is PR-only; main cannot manufacture a certificate.
    for step in aggregate.split('      - ')[1:]:
        if 'download-artifact@' in step or 'ci.py certify' in step or 'upload-artifact@' in step:
            assert "if: github.event_name == 'pull_request'" in step
    assert 'native-${{ github.run_id }}-${{ github.run_attempt }}-*' in aggregate
    assert 'certificate-${{ github.run_id }}-${{ github.run_attempt }}' in aggregate


def test_ci01_event_and_dependency_gate_is_fail_closed():
    pr={'fast-gate':{'result':'success','outputs':{}},'focused':{'result':'success','outputs':{}}}
    main=deepcopy(pr);main['focused']['result']='skipped'
    assert ci.dependency_gate('pull_request','refs/pull/9/merge','main',pr)['mode']=='PR_FULL'
    actual=ci.dependency_gate('push','refs/heads/main','',main)
    assert actual['mode']=='MAIN_FAST_ONLY' and actual['full_regression_certified'] is False
    for event,ref,base in [('workflow_dispatch','refs/heads/main',''),('push','refs/heads/feature',''),
            ('push','refs/heads/main','main'),('pull_request','refs/heads/main','main'),
            ('pull_request','refs/pull/9/merge','develop'),('pull_request','refs/pull/no/merge','main')]:
        with pytest.raises(ValueError):ci.dependency_gate(event,ref,base,pr)
    for event,ref,base,valid in [('pull_request','refs/pull/9/merge','main',pr),('push','refs/heads/main','',main)]:
        for state in ('failure','cancelled','skipped','missing'):
            invalid=deepcopy(valid)
            if state=='missing':invalid.pop('fast-gate')
            else:invalid['fast-gate']['result']=state
            with pytest.raises(ValueError):ci.dependency_gate(event,ref,base,invalid)
        for state in ('failure','cancelled','missing','skipped' if event=='pull_request' else 'success'):
            invalid=deepcopy(valid)
            if state=='missing':invalid.pop('focused')
            else:invalid['focused']['result']=state
            with pytest.raises(ValueError):ci.dependency_gate(event,ref,base,invalid)
    for invalid in (None,[],{},dict(pr,unknown={'result':'success'}),dict(pr,focused=None)):
        with pytest.raises(ValueError):ci.dependency_gate('pull_request','refs/pull/9/merge','main',invalid)
    # A green aggregate dependency alone never substitutes for all three sealed test artifacts.
    schedule,discovery,shards=certificate_fixture();shards.pop('C')
    with pytest.raises(ValueError):ci.certify(discovery,shards,schedule)


def test_ci01_checkout_and_gate_cli_real_git_mutations(tmp_path):
    import os
    import shutil
    import subprocess
    import sys
    checkout=tmp_path/'checkout';checkout.mkdir();template=tmp_path/'template';template.mkdir()
    def git(*args):return subprocess.check_output(['git','-C',str(checkout),*args],text=True).strip()
    git('init','-q','--template='+str(template),'--initial-branch=fixture')
    git('config','user.name','CI Fixture');git('config','user.email','fixture@example.invalid')
    root=Path(__file__).resolve().parents[1]
    names=[x['path'] for x in json.loads((root/'accepted.lock.json').read_text())['files']]
    names+=['accepted.lock.json','upstream.lock.json','requirements.txt','tools/ci.py',
            'tools/test-schedule.json','tools/test-schedule.sha256']
    for name in names:
        p=checkout/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,p)
    def commit():
        git('add','--',*names);git('-c','commit.gpgsign=false','commit','-qm','Synthetic CI policy control')
        return git('rev-parse','HEAD')
    head=commit();proof=tmp_path/'checkout.json'
    env=dict(os.environ,GITHUB_ACTIONS='true',GITHUB_EVENT_NAME='push',GITHUB_REF='refs/heads/main',
        GITHUB_BASE_REF='',CHECKER_TESTED_HEAD=head,GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='2',
        CHECKER_CHECKOUT_PROOF=str(proof),PYTHONDONTWRITEBYTECODE='1')
    def run(action):
        return subprocess.run([sys.executable,'-B',str(checkout/'tools/ci.py'),action],cwd=checkout,
                              env=env,capture_output=True,text=True)
    assert run('checkout').returncode==0
    assert json.loads(proof.read_text())['head']==head
    env['CHECKER_TESTED_HEAD']='0'*40
    assert run('checkout').returncode!=0
    env['CHECKER_TESTED_HEAD']=head
    for name,reason in [(names[0],'Accepted source/test identity mismatch'),
                        ('accepted.lock.json','Accepted source/test identity mismatch'),
                        ('tools/test-schedule.json','Schedule final-byte digest mismatch')]:
        p=checkout/name;original=p.read_bytes()
        if name=='accepted.lock.json':
            lock=json.loads(original);lock['files'][0]['sha256']='0'*64;p.write_text(json.dumps(lock))
        else:p.write_bytes(original+b'\n')
        env['CHECKER_TESTED_HEAD']=commit();proof.unlink(missing_ok=True)
        rejected=run('checkout')
        assert rejected.returncode!=0 and reason in rejected.stderr and not proof.exists()
        p.write_bytes(original);env['CHECKER_TESTED_HEAD']=commit()
    assert run('checkout').returncode==0
    env.update(GITHUB_EVENT_NAME='pull_request',GITHUB_REF='refs/pull/9/merge',GITHUB_BASE_REF='main',
        CHECKER_NEEDS_JSON=json.dumps({'fast-gate':{'result':'success'},'focused':{'result':'success'}}))
    assert run('checkout').returncode==0
    gate=run('gate');assert gate.returncode==0 and json.loads(gate.stdout)['mode']=='PR_FULL'
    env['CHECKER_NEEDS_JSON']='{"fast-gate":{"result":"success"},"focused":{"result":"skipped"}}'
    assert run('gate').returncode!=0
    env.update(GITHUB_EVENT_NAME='push',GITHUB_REF='refs/heads/main',GITHUB_BASE_REF='')
    gate=run('gate');assert gate.returncode==0 and json.loads(gate.stdout)['full_regression_certified'] is False
    for value in ('{}','not-json','null'):
        env['CHECKER_NEEDS_JSON']=value
        assert run('gate').returncode!=0
    env['GITHUB_REF']='refs/heads/feature';assert run('checkout').returncode!=0
