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
