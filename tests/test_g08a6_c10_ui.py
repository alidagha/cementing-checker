"""Selective UI-copy transactions use original C10 and independently entered inputs."""
from copy import deepcopy
from io import BytesIO
import json
import pytest
from docx import Document
import g07_report as g
from test_c08 import operator as program_operator
from test_g07 import submitted


@pytest.fixture(scope='module')
def copy_control():
    # Reuse the accepted independent program inputs; no unused C09 Word render.
    program = program_operator('CSG 7"')
    inputs = submitted(program['cement_operator'])
    inputs['fluids'] = {'job_type':program['job_type'], 'mud_type':'WBM', 'fluids':deepcopy(program['fluids'])}
    inputs['hardware'] = {'job_type':program['job_type'], 'hardware':deepcopy(program['hardware'])}
    inputs['procedure'] = {'program':program, 'preparation':{'Main':{
        'tank_name':'Mud Reserve Tanks', 'dead_volume_bbl':5, 'surface_hardened_hours':8}},
        'well_geometry':{'version':1, 'type':'Vertical', 'td_m':1000}}
    s = g.PrivateSession(); source = s.folder/'source.docx'
    g.c04_runtime.call({'action':'fixture','operator':inputs['cement'],'docx':str(source),
        'fixture':{'Main':{'dead':5,'tank':'Mud Reserve Tanks'}}})
    original = source.read_bytes(); d = Document(BytesIO(original))
    data = next(t for t in d.tables if t.cell(0,0).text == 'Main Cement Slurry Data')
    blend = next(t for t in d.tables if t.cell(0,0).text == 'Main Cement Slurry Blend Data')
    data.rows[4].cells[1].text = '9.900 cuft/sk'; blend.rows[2].cells[3].text = '999.9 sks'
    stream = BytesIO(); d.save(stream); path = s.store('synthetic.docx', stream.getvalue())
    before = deepcopy(s.check(path, inputs))
    return s, path, before, source, original


@pytest.fixture(scope='module')
def proof(copy_control):
    s, path, before, _, _ = copy_control
    inspection = deepcopy(s.inspect_copy_proposals()); copies = {}
    for field in ('yield','sacks'):
        ids = [p['finding_id'] for p in inspection['proposal']['proposals'] if p['action']=='SELECTABLE' and p['field']==field]
        assert len(ids) == 1
        copies[field] = deepcopy(s.create_selected_copy(ids, True))
    return {'inspection':inspection, 'copies':copies}


@pytest.fixture
def checked(copy_control, proof):
    s, path, before, _, _ = copy_control
    s.result = deepcopy(before); s.document = path; s.revision = before['receipt']['revision']
    s.volume_preview = None; s.volume_request_sha = None; s.dv_preview = None; s.dv_request_sha = None
    s._clear_copy(); s.copy_proposal = deepcopy(proof['inspection'])
    return s, path, deepcopy(before)


def ids(proof, field):
    return [p['finding_id'] for p in proof['inspection']['proposal']['proposals'] if p['field']==field and p['action']=='SELECTABLE']


def retain_copy(s, value):
    s.copy_output = deepcopy(value); s.copy_choice_sha = value['receipt']['choice_sha256']


def test_explicit_selected_Yield_copy_uses_C10_and_keeps_other_claims(checked, copy_control, proof):
    from hashlib import sha256
    import zipfile
    s, path, before = checked; _, _, _, source, original = copy_control
    result = proof['copies']['yield']; retain_copy(s, result)
    after = result['transaction']['comparison_after']; rows = {f['field']:f for f in after['findings'] if f['field'] in ('yield','sacks')}
    assert rows['yield']['result']=='MATCH' and rows['yield']['raw_reported_text']=='1.818 cuft/sk'
    assert rows['sacks']['result']=='DISCREPANCY' and rows['sacks']['raw_reported_text']=='999.9 sks'
    assert result['transaction']['dependency_group_complete'] is False
    assert result['receipt']['output_sha256']==sha256(result['bytes']).hexdigest()
    assert s.current_created_copy(ids(proof,'yield'),True)==result and s.current()==before
    with zipfile.ZipFile(BytesIO(path.read_bytes())) as old, zipfile.ZipFile(BytesIO(result['bytes'])) as new:
        assert old.namelist()==new.namelist() and old.comment==new.comment
        assert [n for n in old.namelist() if old.read(n)!=new.read(n)]==['word/document.xml']
        assert old.read('word/document.xml').replace(b'9.900 cuft/sk',b'1.818 cuft/sk',1)==new.read('word/document.xml')
        for a,b in zip(old.infolist(),new.infolist()):
            assert (a.filename,a.date_time,a.extra,a.comment,a.external_attr,a.flag_bits)==(b.filename,b.date_time,b.extra,b.comment,b.external_attr,b.flag_bits)
    assert source.read_bytes()==original and 'output_path' not in result['transaction']
    assert not list((g.ROOT/'tmp').glob('g07-c10-*'))


def test_explicit_Sacks_copy_and_unselected_Yield_are_source_rechecked(checked, proof):
    s, path, before = checked; result=proof['copies']['sacks']; retain_copy(s,result)
    rows={f['field']:f for f in result['transaction']['comparison_after']['findings'] if f['field'] in ('yield','sacks')}
    assert rows['sacks']['result']=='MATCH' and rows['sacks']['raw_reported_text']=='154.4 sks'
    assert rows['yield']['result']=='DISCREPANCY' and rows['yield']['raw_reported_text']=='9.900 cuft/sk'
    assert result['transaction']['comparison_before']==before['results']['C03']['c02']
    assert s.current_created_copy(ids(proof,'sacks'),True)==result and s.current()==before


def test_no_implicit_selection_consent_or_unadmitted_transport(checked, proof, monkeypatch):
    import c10_corrections as c
    s, path, before=checked; y=ids(proof,'yield')
    def unexpected(*a):pytest.fail('Invalid selection/admission reached C10 transport')
    monkeypatch.setattr(c,'apply',unexpected);monkeypatch.setattr(c,'propose',unexpected)
    for selection,consent in (([],True),(None,True),(y,False),(y,None),(y,1),(y*2,True),(['forged'],True),([True],True)):
        retain_copy(s,proof['copies']['yield'])
        with pytest.raises(ValueError):s.create_selected_copy(selection,consent)
        assert s.copy_output is None and s.current()==before
    for kind in ('absent','incomplete','rejected','operator','c03','foreign'):
        s.result=deepcopy(before);s.document=path;s.copy_proposal=deepcopy(proof['inspection'])
        if kind=='absent':s.result=None
        elif kind=='incomplete':s.result['run_outcome']='INPUT_INCOMPLETE'
        elif kind=='rejected':s.result['receipt']['cement_admission']['status']='INPUT_REJECTED'
        elif kind=='operator':s.result['receipt']['inputs_snapshot']['cement']['slurries']['Main']['client_volume_bbl']=99
        elif kind=='c03':s.result['results']['C03']['status']='INPUT_REJECTED'
        else:
            alias=s.folder/'alias.docx';alias.symlink_to(path);s.document=alias
        if s.result is not None:
            s.result['report_id']=g.report_identity(s.result);s.result['receipt']['report_id']=s.result['report_id']
        with pytest.raises(ValueError):s.create_selected_copy(y,True)
        assert s.copy_output is None


def test_choice_consent_run_and_foreign_session_invalidate_copies(checked, proof):
    s,path,before=checked;y=ids(proof,'yield');other=ids(proof,'sacks')
    retain_copy(s,proof['copies']['yield'])
    assert s.current_created_copy(other,True) is None and s.current_created_copy(y,True) is None
    retain_copy(s,proof['copies']['yield'])
    with pytest.raises(ValueError):s.current_created_copy(y,False)
    assert s.current_created_copy(y,True) is None
    for kind in ('bytes','choice','receipt','proposal'):
        s.copy_proposal=deepcopy(proof['inspection']);retain_copy(s,proof['copies']['yield'])
        if kind=='bytes':s.copy_output['bytes']+=b'forged'
        elif kind=='choice':s.copy_output['receipt']['choice']['selected_ids']=other
        elif kind=='receipt':s.copy_output['receipt']['request']['session_id']='foreign'
        else:s.copy_proposal['proposal']['proposals'][0]['replacement']='forged'
        with pytest.raises(ValueError):s.current_created_copy(y,True)
        assert s.copy_output is None
    s.copy_proposal=deepcopy(proof['inspection']);retain_copy(s,proof['copies']['yield'])
    foreign=g.PrivateSession();foreign.result=deepcopy(before);foreign.document=path
    foreign.copy_proposal=deepcopy(proof['inspection']);retain_copy(foreign,proof['copies']['yield'])
    with pytest.raises(ValueError):foreign.current_created_copy(y,True)
    assert foreign.copy_output is None and s.current()==before
    assert s.invalidate('changed-independent-input') and s.copy_proposal is s.copy_output is None


def test_original_source_receipts_and_recheck_failures_cannot_enable_download(checked, proof, monkeypatch):
    import c10_corrections as c
    s,path,before=checked;y=ids(proof,'yield');original=path.read_bytes()
    def replay(value):
        def run(source,operator,selection,output):
            assert selection=={'schema':'c10.1','bindings':proof['inspection']['proposal']['bindings'],
                'selected':proof['copies']['yield']['transaction']['selected']}
            assert source.parent.parent==g.ROOT/'tmp' and source.stat().st_mode & 0o077==0
            assert source.parent.stat().st_mode & 0o077==0 and source.read_bytes()==original
            output.write_bytes(proof['copies']['yield']['bytes'])
            result=deepcopy(value);result['output_path']=str(output);return result
        return run
    for kind in ('preview','binding','before','selected','unselected','after','source','calls','hash','package','dependency'):
        bad=deepcopy(proof['copies']['yield']['transaction'])
        if kind=='preview':bad['transaction_status']='PREVIEW_ONLY'
        elif kind=='binding':bad['bindings']['source_sha']='forged'
        elif kind=='before':bad['comparison_before']['findings']=[]
        elif kind=='selected':bad['selected']=[]
        elif kind=='unselected':bad['unselected']=[]
        elif kind=='after':bad['comparison_after']['findings'][0]['result']='NOT_VERIFIABLE'
        elif kind=='source':bad['comparison_after']['reference']['slurries']={}
        elif kind=='calls':bad['comparison_after']['reference']['source_calls']=[]
        elif kind=='hash':bad['new_document_sha256']='forged'
        elif kind=='package':bad['unchanged_package_parts']=False
        else:bad['dependency_group_complete']=True
        monkeypatch.setattr(c,'apply',replay(bad))
        with pytest.raises(ValueError):s.create_selected_copy(y,True)
        assert s.copy_output is None and s.current()==before and path.read_bytes()==original
        assert not list((g.ROOT/'tmp').glob('g07-c10-*'))


def test_timeout_output_collision_symlink_and_cleanup_fail_closed(checked, proof, monkeypatch):
    from subprocess import TimeoutExpired
    from pathlib import Path
    import c10_corrections as c
    s,path,before=checked;y=ids(proof,'yield');original=path.read_bytes();factory=g.tempfile.mkdtemp
    def failed(*a):raise TimeoutExpired('/private/SECRET',120,stderr='SECRET-PAYLOAD')
    monkeypatch.setattr(c,'apply',failed)
    with pytest.raises(ValueError) as error:s.create_selected_copy(y,True)
    assert 'SECRET' not in str(error.value) and '/private/' not in str(error.value)
    for kind in ('collision','symlink'):
        def changed_directory(*a,**kw):
            folder=Path(factory(*a,**kw))
            if kw.get('prefix')=='g07-c10-':
                if kind=='collision':(folder/'selected-copy.docx').write_bytes(b'occupied')
                else:(folder/'input.docx').symlink_to(path)
            return str(folder)
        monkeypatch.setattr(g.tempfile,'mkdtemp',changed_directory)
        with pytest.raises(ValueError):s.create_selected_copy(y,True)
        assert s.copy_output is None and path.read_bytes()==original
        assert not list((g.ROOT/'tmp').glob('g07-c10-*'))
    monkeypatch.setattr(g.tempfile,'mkdtemp',factory)
    rmdir=Path.rmdir;left=[]
    def blocked(folder):
        if folder.name.startswith('g07-c10-'):left.append(folder);raise OSError('cleanup unavailable')
        return rmdir(folder)
    def valid(source,operator,selection,output):
        output.write_bytes(proof['copies']['yield']['bytes'])
        result=deepcopy(proof['copies']['yield']['transaction']);result['output_path']=str(output);return result
    monkeypatch.setattr(c,'apply',valid);monkeypatch.setattr(Path,'rmdir',blocked)
    try:
        with pytest.raises(ValueError):s.create_selected_copy(y,True)
        assert left and s.copy_output is None and s.current()==before
    finally:
        monkeypatch.setattr(Path,'rmdir',rmdir)
        for folder in left:assert not list(folder.iterdir());folder.rmdir()


def test_real_hidden_claim_is_manual_and_never_selected(checked, monkeypatch):
    import c10_corrections as c
    from docx.oxml import OxmlElement
    s,path,before=checked;d=Document(path)
    table=next(t for t in d.tables if t.cell(0,0).text=='Main Cement Slurry Data')
    table.rows[4].cells[1].paragraphs[0].runs[0]._r.get_or_add_rPr().append(OxmlElement('w:vanish'))
    stream=BytesIO();d.save(stream);other=g.PrivateSession();p=other.store('hidden.docx',stream.getvalue())
    # Physical C10 admission consumes cement only; optional unrelated adapters
    # are exercised on the complete positive sibling control, not repeated here.
    baseline=deepcopy(other.check(p,submitted(before['receipt']['inputs_snapshot']['cement'])))
    inspection=other.inspect_copy_proposals();manual=next(p for p in inspection['proposal']['proposals'] if p['field']=='yield')
    assert manual['action']=='MANUAL_CORRECTION_REQUIRED' and manual['replacement'] is None
    def unexpected(*a):pytest.fail('Manual item reached C10 apply')
    monkeypatch.setattr(c,'apply',unexpected)
    with pytest.raises(ValueError):other.create_selected_copy([manual['finding_id']],True)
    assert other.copy_output is None and other.current()==baseline


def test_actual_G06_previews_and_C09_message_survive_C10_transaction(checked, proof):
    s,path,before=checked
    a=deepcopy(s.preview_volume('Main',55));b=deepcopy(s.preview_dead_volume('Main',0))
    assert before['receipt']['C09_operator_sha256']==g.digest(before['receipt']['inputs_snapshot']['procedure'])
    assert before['results']['C09']['reference']['operator_input_sha256']==before['receipt']['C09_operator_sha256']
    result=s.create_selected_copy(ids(proof,'yield'),True)
    assert result['transaction']['transaction_status']=='COPY_CREATED' and s.current()==before
    assert s.current_volume_preview('Main',55)==a and s.current_dead_volume_preview('Main',0)==b
    assert s.current()['message']==before['message']


def test_resealed_copy_metadata_still_requires_current_source_and_run(checked, proof):
    s, _, before = checked
    for kind in ('request','bindings','status','output-hash','before'):
        retain_copy(s,proof['copies']['yield']);value=s.copy_output
        if kind=='request':value['receipt']['request']['session_id']='foreign'
        elif kind=='bindings':value['transaction']['bindings']['source_sha']='forged'
        elif kind=='status':value['transaction']['transaction_status']='PREVIEW_ONLY'
        elif kind=='output-hash':value['transaction']['new_document_sha256']='forged'
        else:value['transaction']['comparison_before']['findings']=[]
        value['receipt']['transaction_sha256']=g.digest(value['transaction'])
        value['copy_id']=g.digest({k:v for k,v in value.items() if k not in ('bytes','copy_id')})
        with pytest.raises(ValueError):s.current_created_copy(ids(proof,'yield'),True)
        assert s.copy_output is None and s.current()==before
