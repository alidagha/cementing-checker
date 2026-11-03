"""Real source controls and pure/session presentation guards; browser proof is separate."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import zipfile

from docx import Document
from docx.oxml import OxmlElement
import pytest
import g07_report as g


def submitted(op):
    return dict(job_type=op['job_type'],mud_type='WBM',active_fluids=op['active_fluids'],
        cement=deepcopy(op),fluids=None,hardware=None,lab=None,summary=None)


@pytest.fixture(scope='session')
def controls():
    op=json.loads((g.ROOT/'c02/fixtures/operator-neat.json').read_text())
    with tempfile.TemporaryDirectory(dir=g.ROOT/'c04/tmp',prefix='g07-control-') as folder:
        path=Path(folder)/'source.docx'
        g.c04_runtime.call({'action':'fixture','operator':op,'docx':str(path),
            'fixture':{'Main':{'dead':5,'tank':'Mud Reserve Tanks'}}})
        good=path.read_bytes();d=Document(path)
        table=next(t for t in d.tables if t.cell(0,0).text=='Main Cement Slurry Blend Data')
        table.rows[2].cells[3].text='999.9 sks';d.save(path)
        yield {'op':op,'good':good,'bad':path.read_bytes()}


def test_real_source_discrepancy_and_message_original_bytes_and_complete_evidence(controls):
    session=g.PrivateSession();path=session.store('independent.docx',controls['bad']);original=path.read_bytes()
    result=session.check(path,submitted(controls['op']))
    message=g.engineer_message(result)
    assert 'Main sacks: expected 154.4 sks.' in message and '999.9' not in message
    assert any('MATCH' in r['Status'] and r['Field']=='yield' for r in result['rows'])
    assert result['status']=='PARTIAL_FINDINGS_ONLY' and result['docx_written'] is result['word_modified'] is False
    assert path.read_bytes()==original and result['document_sha256']==sha256(original).hexdigest()
    assert result['results']['C03']['c02']['findings'] and result['original_records']
    assert all('NOT_RUN' in result['availability'][k] for k in ('C05','C06','C07','C08','C09','C10'))


def test_source_good_control_and_hidden_claim_cannot_produce_message(controls):
    s=g.PrivateSession();path=s.store('good.docx',controls['good']);r=s.check(path,submitted(controls['op']))
    assert 'No discrepancies detected in checks completed' in g.engineer_message(r)
    d=Document(path);t=next(t for t in d.tables if t.cell(0,0).text=='Main Cement Slurry Blend Data')
    p=t.rows[2].cells[3].paragraphs[0];p.runs[0].text='999.9 sks';p.runs[0]._r.get_or_add_rPr().append(OxmlElement('w:vanish'))
    other=s.folder/'changed.docx';d.save(other)
    hidden=s.store('hidden.docx',other.read_bytes());r=s.check(hidden,submitted(controls['op']))
    assert 'expected 154.4' not in g.engineer_message(r)
    assert any('UI: NOT_VERIFIABLE' in row['Status'] for row in r['rows'])
    assert 'No discrepancies detected' not in r['message'] and 'manual review' in r['message']


@pytest.mark.parametrize('token',['-','N/A','not numeric','0','duplicate'])
def test_real_missing_malformed_zero_and_ambiguous_Word_claims(controls,token):
    s=g.PrivateSession();original=s.store('source.docx',controls['good']);d=Document(original)
    table=next(t for t in d.tables if t.cell(0,0).text=='Main Cement Slurry Blend Data')
    if token=='duplicate': table._tbl.addnext(deepcopy(table._tbl))
    else: table.rows[2].cells[3].text=token+' sks'
    changed=s.folder/'synthetic-mutation.docx';d.save(changed)
    path=s.store('mutation.docx',changed.read_bytes());r=s.check(path,submitted(controls['op']))
    sacks=[f for f in r['results']['C03']['c02']['findings'] if f['field']=='sacks']
    if token=='0':
        assert sacks[0]['result']=='DISCREPANCY' and 'expected 154.4 sks.' in g.engineer_message(r)
    else:
        assert all(f['result'] not in ('MATCH','DISCREPANCY') for f in sacks)
        assert 'expected 154.4 sks.' not in g.engineer_message(r)


@pytest.mark.parametrize('name,raw',[('bad.pdf',b'abc'),('../x.docx',b'abc'),('folder\\x.docx',b'abc'),
    ('bad.docx',b'not a zip'),('empty.docx',b''),('large.docx',b'x'*(g.LIMIT+1))])
def test_upload_name_size_actual_structure_rejected(name,raw):
    with pytest.raises((ValueError,OSError,RuntimeError,zipfile.BadZipFile)):
        g.PrivateSession().store(name,raw)


def test_session_isolation_symlink_traversal_and_stale_results(controls):
    a=g.PrivateSession();b=g.PrivateSession();assert a.folder!=b.folder
    path=a.store('a.docx',controls['good']);other=b.store('b.docx',controls['good'])
    assert a.folder.stat().st_mode & 0o077 == 0
    with pytest.raises(ValueError): b.check(path,{})
    alias=a.folder/'alias.docx';alias.symlink_to(other)
    with pytest.raises(ValueError): a.check(alias,{})
    with pytest.raises(ValueError): a.check(a.folder/'..'/a.folder.name/path.name,{})
    assert a.invalidate('revision-a') is True;a.result={'private':'session a'}
    assert not a.invalidate('revision-a') and a.result
    assert b.result is None and a.invalidate('revision-b') and a.result is None


def test_duplicate_and_overlapping_judgments_preserve_statuses_once(controls):
    f={'section':'cement','slurry':'Main','field':'sacks','locator':{'body_block':1},
        'raw_reported_text':'999.9 sks','source_rounded_expected':'154.4','unit':'sks','result':'DISCREPANCY'}
    rows=g.findings_table({'A':{'status':'PARTIAL_FINDINGS_ONLY','findings':[f,f]},'B':{'status':'PARTIAL_FINDINGS_ONLY','findings':[dict(f,result='NOT_VERIFIABLE')]}})
    assert len(rows)==1 and len(rows[0]['Judgments'])==2
    rows[0]['Message eligible']=True
    assert 'expected' not in g.engineer_message({'rows':rows,'run_outcome':'PARTIAL_FINDINGS_ONLY'})
    assert 'DISCREPANCY' in rows[0]['Status'] and 'NOT_VERIFIABLE' in rows[0]['Status']


@pytest.mark.parametrize('status',['NOT_VERIFIABLE','UNIMPLEMENTED','INPUT_REJECTED','MISSING','DASH','NA_PRINTED','AMBIGUOUS'])
def test_unknown_or_absent_tokens_never_become_discrepancy_message(status):
    f={'section':'cement','field':'unknown','result':status,'raw_reported_text':'0' if status=='MISSING' else status}
    rows=g.findings_table({'A':{'status':'PARTIAL_FINDINGS_ONLY','findings':[f]}})
    assert status in rows[0]['Status'] and g.engineer_message(rows).startswith('NOT_VERIFIABLE')


def test_english_labels_raw_provenance_and_exclusions():
    f={'section':'cement','field':'sacks','raw_reported_text':'نمونه','result':'UNIMPLEMENTED'}
    rows=g.findings_table({'A':{'status':'PARTIAL_FINDINGS_ONLY','findings':[f,dict(f,section='excluded')]}})
    assert len(rows)==1 and rows[0]['Word value'].isascii() and rows[0]['Judgments'][0]['finding']==f
    assert g.engineer_message(rows).isascii() and 'program is correct' not in g.engineer_message(rows)
    assert g.clean_rows([{'dose':0,'missing':None},{'dose':float('nan')},{'dose':''}])==[{'dose':0}]


def test_only_supplied_compatible_sections_execute_and_original_statuses_remain(controls):
    s=g.PrivateSession();p=s.store('source.docx',controls['good'])
    request=submitted(controls['op']);request['cement']=None
    request['fluids']={'job_type':'CSG 20"','fluids':{'Main':{'volume':50,'density':104,'pump_rate':5}}}
    result=s.check(p,request)
    assert set(result['results'])=={'C05'} and result['run_outcome']=='INPUT_INCOMPLETE'
    assert result['availability']['C02/C03'].startswith('INPUT_INCOMPLETE')
    assert 'No discrepancies detected' not in result['message']
    assert 'NOT_RUN' in result['availability']['C09']


def test_runtime_and_source_catalog_and_app_initial_state(monkeypatch):
    cat=g.catalog();assert len(cat['jobs'])==15 and cat['cement_names']
    assert 'Main' in cat['eligible']['CSG 20"']['WBM']
    monkeypatch.setenv('STREAMLIT_BROWSER_GATHER_USAGE_STATS','false')
    from streamlit.testing.v1 import AppTest
    from streamlit import config
    previous=config.get_option('browser.gatherUsageStats')
    try:
        config.set_option('browser.gatherUsageStats',False)
        app=AppTest.from_file(str(g.ROOT/'checker_ui.py'),default_timeout=30).run()
    finally: config.set_option('browser.gatherUsageStats',previous)
    assert not app.exception
    assert app.selectbox(key='job').value is None and app.selectbox(key='mud').value is None
    assert app.button[0].disabled
    assert any('PARTIAL_FINDINGS_ONLY' in caption.value for caption in app.caption)


def test_active_cement_missing_payload_is_explicitly_incomplete(controls):
    session=g.PrivateSession();path=session.store('source.docx',controls['bad'])
    request={'job_type':'CSG 20"','mud_type':'WBM','active_fluids':['Main'],
        'cement':None,'fluids':None,'hardware':None,'lab':None,'summary':None}
    result=session.check(path,request)
    assert result.get('run_outcome')=='INPUT_INCOMPLETE', 'Active cement silently skipped: '+str(result['availability'])
    assert 'C03' not in result['results']
    assert 'No discrepancies detected' not in result['message']
    assert result['receipt']['C02_status']=='NOT_RUN' and result['receipt']['cement_admission']['status']=='INPUT_INCOMPLETE'


def test_exact_empty_additives_source_receipt_and_run_identity(controls):
    s=g.PrivateSession();p=s.store('source.docx',controls['bad']);request=submitted(controls['op'])
    draft={'neat_confirmations':{'Main':True},'slurries':deepcopy(request['cement']['slurries'])}
    s.invalidate('submitted-revision');r=s.check(p,request,revision='submitted-revision',draft=draft)
    receipt=r['receipt'];f=receipt['sacks_findings'][0]
    assert receipt['cement_admission']['status']=='SOURCE_ADMITTED'
    assert receipt['cement_operator_sha256']==g.digest(controls['op'])
    assert receipt['submission_sha256']==g.digest(request) and receipt['inputs_snapshot']==request
    assert receipt['widget_snapshot']==draft
    assert receipt['document_sha256']==sha256(controls['bad']).hexdigest()
    assert f['mapping_state']=='IDENTIFIED' and f['result']=='DISCREPANCY'
    assert (f['source_rounded_expected'],f['raw_reported_text'],f['delta'],f['tolerance'])==('154.4','999.9 sks','845.5','1')
    assert r['report_id']==g.report_identity(r) and s.current() is r
    stored=json.loads((s.folder/('run-'+receipt['run_id']+'.json')).read_text());assert stored==r
    request['cement']['slurries']['Main']['client_volume_bbl']=55
    assert receipt['inputs_snapshot']['cement']['slurries']['Main']['client_volume_bbl']==50
    other=g.PrivateSession();other.result=r;other.document=p
    with pytest.raises(ValueError):other.current()
    assert s.invalidate('edited-revision') and s.current() is None


@pytest.mark.parametrize('mutation',['missing-value','missing-additives','invalid-number','wrong-job','extra-field','source-invalid'])
def test_active_cement_submission_schema_fails_closed(controls,mutation):
    s=g.PrivateSession();p=s.store('source.docx',controls['bad']);request=submitted(controls['op'])
    item=request['cement']['slurries']['Main']
    if mutation=='missing-value':item['cement_sg']=None
    elif mutation=='missing-additives':item['additives']=None
    elif mutation=='invalid-number':item['density_pcf']='104'
    elif mutation=='wrong-job':request['cement']['job_type']='CSG 24"'
    elif mutation=='source-invalid':item['density_pcf']=1
    else:item['invented_measurement']=0
    r=s.check(p,request)
    assert r['run_outcome'] in ('INPUT_INCOMPLETE','INPUT_REJECTED')
    assert 'C03' not in r['results'] and 'No discrepancies detected' not in r['message']
    if mutation=='source-invalid':
        assert r['receipt']['cement_source_attempted'] is True and r['receipt']['C02_status']=='INPUT_REJECTED'


def test_no_cement_applicability_and_zero_executed_coverage(controls):
    s=g.PrivateSession();p=s.store('source.docx',controls['good'])
    request={'job_type':'CSG 20"','mud_type':'WBM','active_fluids':['Displacement Fluid'],
        'cement':None,'fluids':None,'hardware':None,'lab':None,'summary':None}
    r=s.check(p,request)
    assert r['receipt']['cement_admission']['status']=='NOT_APPLICABLE'
    assert r['run_outcome']=='CHECK_NOT_RUN' and not r['completed_adapters']
    assert r['message'].startswith('CHECK_NOT_RUN')


def test_stale_submission_and_tampered_receipt_are_rejected(controls):
    s=g.PrivateSession();p=s.store('source.docx',controls['bad']);s.invalidate('current')
    with pytest.raises(ValueError):s.check(p,submitted(controls['op']),revision='stale')
    r=s.check(p,submitted(controls['op']),revision='current')
    r['receipt']['cement_operator_sha256']='0'*64
    with pytest.raises(ValueError):s.current()


def test_revision_binds_admission_and_neat_confirmation(controls):
    raw=controls['bad'];ready=submitted(controls['op']);missing=deepcopy(ready);missing['cement']=None
    draft={'neat_confirmations':{'Main':True},'slurries':deepcopy(ready['cement']['slurries'])}
    revision=g.submission_revision(raw,'a.docx',ready,draft)
    assert revision!=g.submission_revision(raw,'a.docx',missing,draft)
    altered=deepcopy(draft);altered['neat_confirmations']['Main']=False
    assert revision!=g.submission_revision(raw,'a.docx',ready,altered)
    assert revision!=g.submission_revision(controls['good'],'a.docx',ready,draft)


def test_noncement_rejected_adapter_is_not_zero_completed_success(controls):
    s=g.PrivateSession();p=s.store('source.docx',controls['good'])
    request={'job_type':'CSG 20"','mud_type':'WBM','active_fluids':['Displacement Fluid'],'cement':None,
        'fluids':{'job_type':'CSG 20"','fluids':{'Displacement Fluid':{'volume':10,'density':75,'pump_rate':0}}},
        'hardware':None,'lab':None,'summary':None}
    r=s.check(p,request)
    assert r['receipt']['cement_admission']['status']=='NOT_APPLICABLE'
    assert r['run_outcome']=='INPUT_REJECTED' and not r['completed_adapters']
    assert r['message'].startswith('INPUT_REJECTED') and 'No discrepancies detected' not in r['message']


def test_ui_main_only_persistence_and_incomplete_lead_blocks_run(controls,monkeypatch):
    # AppTest has no uploader interaction. Supply only that transport prerequisite;
    # all engineering inputs use the real widgets, without session-state injection.
    from io import BytesIO
    import streamlit as st
    from streamlit import config
    from streamlit.testing.v1 import AppTest
    upload=BytesIO(controls['bad']);upload.name='independent.docx'
    monkeypatch.setattr(st,'file_uploader',lambda *args,**kwargs:upload)
    previous=config.get_option('browser.gatherUsageStats')
    try:
        config.set_option('browser.gatherUsageStats',False)
        app=AppTest.from_file(str(g.ROOT/'checker_ui.py'),default_timeout=30).run()
        app.selectbox(key='job').select('CSG 20"').run()
        app.selectbox(key='mud').select('WBM').run()
        active=app.multiselect(key='active:CSG 20":WBM')
        active.select('Main').run()
        assert app.button[0].disabled, 'Run Check admits an incomplete active cement formulation'
        prefix='CSG 20":Main:'
        app.number_input(key=prefix+'volume').set_value(50.0)
        app.number_input(key=prefix+'density').set_value(104.0)
        app.selectbox(key=prefix+'base').select('Cement G Delijan')
        app.number_input(key=prefix+'sg').set_value(3.2)
        app.checkbox(key=prefix+'neat').check().run()
        assert not app.exception and not app.button[0].disabled
        app.run()
        assert app.multiselect(key='active:CSG 20":WBM').value==['Main']
        committed=json.loads(next(c.value for c in app.code if '"revision"' in c.value))
        assert committed['inputs']['active_fluids']==['Main']
        assert committed['inputs']['cement']['slurries']['Main']['additives']==[]
        app.button[0].click().run()
        assert not app.exception
        assert app.session_state['_private'].result['receipt']['cement_admission']['status']=='SOURCE_ADMITTED'
        assert app.text_area(key='engineer_message').value.startswith('Your program contains')
        app.multiselect(key='active:CSG 20":WBM').select('Lead').run()
        assert app.button[0].disabled
        assert app.session_state['_private'].result is None
        assert not any(t.key=='engineer_message' for t in app.text_area)
        committed=json.loads(next(c.value for c in app.code if '"revision"' in c.value))
        assert committed['inputs']['active_fluids']==['Main','Lead'] and committed['inputs']['cement'] is None
        assert committed['draft']['slurries']['Lead']['client_volume_bbl'] is None
        lead='CSG 20":Lead:'
        app.number_input(key=lead+'volume').set_value(50.0)
        app.number_input(key=lead+'density').set_value(104.0)
        app.selectbox(key=lead+'base').select('Cement G Delijan')
        app.number_input(key=lead+'sg').set_value(3.2)
        app.checkbox(key=lead+'neat').check().run()
        assert not app.button[0].disabled
        app.button[0].click().run()
        assert not app.exception
        result=app.session_state['_private'].result
        assert set(result['results']['C03']['c02']['reference']['slurries'])=={'Main','Lead'}
        assert result['receipt']['inputs_snapshot']['active_fluids']==['Main','Lead']
        app.multiselect(key='active:CSG 20":WBM').unselect('Lead').run()
        assert not app.button[0].disabled
        assert app.session_state['_private'].result is None
        assert not any(t.key=='engineer_message' for t in app.text_area)
        assert app.number_input(key=prefix+'volume').value==50.0
        assert app.multiselect(key='active:CSG 20":WBM').value==['Main']
    finally:config.set_option('browser.gatherUsageStats',previous)


def test_complete_eligible_main_and_lead_are_both_source_checked(controls):
    s=g.PrivateSession();p=s.store('independent.docx',controls['bad'])
    request=submitted(controls['op']);request['active_fluids']=['Main','Lead']
    request['cement']['active_fluids']=['Main','Lead']
    request['cement']['slurries']['Lead']=deepcopy(request['cement']['slurries']['Main'])
    r=s.check(p,request)
    assert r['receipt']['cement_admission']['status']=='SOURCE_ADMITTED'
    assert r['receipt']['cement_admission']['roles']==['Main','Lead']
    assert set(r['results']['C03']['c02']['reference']['slurries'])=={'Main','Lead'}
    assert r['receipt']['inputs_snapshot']==request
    assert r['receipt']['C02_status']==r['receipt']['C03_status']=='PARTIAL_FINDINGS_ONLY'


def test_completed_c08_discrepancy_without_safe_replacement_is_acknowledged():
    finding={'section':'summary','field':'executive_summary','result':'DISCREPANCY',
        'locator':{'body_block':4},'raw_reported_text':'Different Word narrative',
        'source_wording':'Independent reference narrative'}
    rows=g.findings_table({'C08':{'status':'PARTIAL_FINDINGS_ONLY','findings':[finding]}})
    rows[0]['Message eligible']=False
    report={'status':'PARTIAL_FINDINGS_ONLY','run_outcome':'PARTIAL_FINDINGS_ONLY',
        'completed_adapters':['C08'],'rows':rows}
    message=g.engineer_message(report)
    assert 'No discrepancies detected' not in message
    assert 'discrepanc' in message.lower() and 'manual review' in message.lower()
    assert finding['source_wording'] not in message and 'expected' not in message


def test_original_source_c08_narrative_discrepancy_gets_review_without_replacement():
    from test_c08 import operator as summary_operator
    from narrative_source import request
    from c08_summary import compare_document
    with tempfile.TemporaryDirectory(dir=g.ROOT/'tmp',prefix='g07-summary-') as directory:
        path=Path(directory)/'source.docx';op=summary_operator()
        source=request(op,'render_summary',str(path));original=path.read_bytes()
        document=Document(path)
        para=next(p for p in document.paragraphs if p.text.startswith('Enclosed are our recommendations'))
        assert para.text==source['reference']['text'] and '50.0 bbl' in para.text
        para.text=para.text.replace('50.0 bbl','51.0 bbl')
        bad=Path(directory)/'changed.docx';document.save(bad);before=bad.read_bytes()
        result=compare_document(bad,op);finding=result['findings'][0]
        assert result['status']=='PARTIAL_FINDINGS_ONLY' and finding['result']=='DISCREPANCY'
        assert finding['reference_kind']=='LOCKED_SOURCE_FROM_INDEPENDENT_INPUTS'
        assert finding['source_wording']==source['reference']['text']
        assert finding.get('source_rounded_expected') is None
        rows=g.findings_table({'C08':result})
        g.literal(document.element.body[finding['locator']['body_block']],document)
        rows[0]['Message eligible']=True
        message=g.engineer_message({'run_outcome':'PARTIAL_FINDINGS_ONLY','completed_adapters':['C08'],'rows':rows})
        assert 'No discrepancies detected' not in message and 'manual review' in message
        assert finding['source_wording'] not in message and 'expected' not in message
        assert path.read_bytes()==original and bad.read_bytes()==before


@pytest.mark.parametrize('unsafe',['visibility','overlap','conflicting-expectations','locator','inferred-c03'])
def test_flagged_unsafe_discrepancy_never_gets_exact_replacement(unsafe):
    finding={'section':'cement','slurry':'Main','field':'sacks','result':'DISCREPANCY',
        'locator':{'body_block':53},'source_rounded_expected':'154.4','unit':'sks'}
    adapter='C03' if unsafe=='inferred-c03' else 'C02'
    row={'Fluid/Slurry':'Main','Field':'sacks','Message eligible':unsafe!='visibility',
        'Judgments':[{'adapter':adapter,'finding':finding}]}
    if unsafe=='overlap':row['Judgments'].append({'adapter':adapter,'finding':dict(finding,result='NOT_VERIFIABLE')})
    if unsafe=='conflicting-expectations':row['Judgments'].append({'adapter':adapter,'finding':dict(finding,source_rounded_expected='conflicting source display')})
    if unsafe=='locator':finding['locator']=None
    message=g.engineer_message({'run_outcome':'PARTIAL_FINDINGS_ONLY','completed_adapters':[adapter],'rows':[row]})
    assert 'discrepanc' in message and 'manual review' in message
    assert 'No discrepancies detected' not in message and '154.4' not in message and 'expected' not in message


def test_safe_suggestion_with_another_flagged_finding_mentions_manual_review():
    safe={'Fluid/Slurry':'Main','Field':'sacks','Message eligible':True,'Judgments':[{'adapter':'C02','finding':{
        'result':'DISCREPANCY','locator':{'body_block':53},'source_rounded_expected':'154.4','unit':'sks'}}]}
    unsafe={'Message eligible':False,'Judgments':[{'adapter':'C08','finding':{'result':'DISCREPANCY'}}]}
    message=g.engineer_message({'run_outcome':'PARTIAL_FINDINGS_ONLY','completed_adapters':['C02','C08'],'rows':[safe,unsafe]})
    assert '- Main sacks: expected 154.4 sks.' in message
    assert 'Additional table-flagged discrepancies require manual review' in message


@pytest.mark.parametrize('status',['MATCH','NOT_VERIFIABLE','UNIMPLEMENTED','INPUT_REJECTED'])
def test_completed_checks_without_flagged_discrepancy_keep_qualified_zero_wording(status):
    # Display labels do not override the structured source judgment.
    row={'Status':'DISCREPANCY','Judgments':[{'adapter':'C08','finding':{'result':status}}]}
    message=g.engineer_message({'run_outcome':'PARTIAL_FINDINGS_ONLY','completed_adapters':['C08'],'rows':[row]})
    assert message.startswith('No discrepancies detected in checks completed.')
    assert 'Unverified' in message and 'partial check' in message


def test_zero_completed_adapters_cannot_claim_completed_zero_discrepancies():
    row={'Message eligible':True,'Judgments':[{'adapter':'C08','finding':{'result':'DISCREPANCY'}}]}
    message=g.engineer_message({'run_outcome':'PARTIAL_FINDINGS_ONLY','completed_adapters':[],'rows':[row]})
    assert message.startswith('CHECK_NOT_RUN') and 'No discrepancies detected' not in message


@pytest.fixture
def ui_boundary(controls, monkeypatch):
    """Only upload transport is substituted; engineering inputs use real widgets."""
    from io import BytesIO
    import streamlit as st
    from streamlit import config
    from streamlit.testing.v1 import AppTest
    upload = BytesIO(controls['bad']); upload.name = 'independent.docx'
    uploads = [upload]
    monkeypatch.setattr(st, 'file_uploader', lambda *args, **kwargs: uploads[0])
    previous = config.get_option('browser.gatherUsageStats')
    try:
        config.set_option('browser.gatherUsageStats', False)
        yield lambda: AppTest.from_file(str(g.ROOT/'checker_ui.py'), default_timeout=30), uploads
    finally:
        config.set_option('browser.gatherUsageStats', previous)


@pytest.fixture(scope='module')
def procedure_control():
    from test_c08 import operator
    from narrative_source import request
    program = operator('CSG 7"')
    op = {'program': program, 'preparation': {'Main': {
        'tank_name': 'Mud Reserve Tanks', 'dead_volume_bbl': 5,
        'surface_hardened_hours': 8}},
        'well_geometry': {'version': 1, 'type': 'Vertical', 'td_m': 1000}}
    with tempfile.TemporaryDirectory(dir=g.ROOT/'tmp', prefix='g08a3-control-') as folder:
        path = Path(folder)/'source.docx'
        source = request(op, 'render_procedure', str(path))
        inputs = submitted(program['cement_operator'])
        inputs['fluids'] = {'job_type': program['job_type'], 'mud_type': 'WBM',
                            'fluids': deepcopy(program['fluids'])}
        inputs['hardware'] = {'job_type': program['job_type'],
                              'hardware': deepcopy(program['hardware'])}
        inputs['procedure'] = op
        yield path.read_bytes(), inputs, source


def test_c09_selected_source_route_and_readonly_receipt(procedure_control):
    original, inputs, source = procedure_control
    session = g.PrivateSession(); path = session.store('procedure.docx', original)
    draft = {'procedure': procedure_context(inputs['procedure'])}
    revision = g.submission_revision(original, 'procedure.docx', inputs, draft)
    session.invalidate(revision)
    result = session.check(path, deepcopy(inputs), revision=revision, draft=draft)
    assert 'C09' in result['results']
    c09 = result['results']['C09']
    assert any(f['field'] == 'procedure' and f['result'] == 'MATCH' and f['locator']
               for f in c09['findings'])
    assert any(f['field'] == 'ordered_notes' and f['result'] == 'MATCH'
               and f['slurry'] == 'Main' for f in c09['findings'])
    assert c09['reference']['operator_input_sha256'] == source['operator_input_sha256']
    assert 'C09' in result['completed_adapters']
    assert result['receipt']['C09_operator_sha256'] == g.digest(inputs['procedure'])
    assert result['receipt']['C09_status'] == 'PARTIAL_FINDINGS_ONLY'
    assert result['status'] == 'PARTIAL_FINDINGS_ONLY'
    assert result['docx_written'] is result['word_modified'] is False
    assert path.read_bytes() == original
    assert result['receipt']['widget_snapshot'] == draft
    assert session.current() == result
    other = g.PrivateSession(); other.result = result; other.document = path
    with pytest.raises(ValueError): other.current()
    incomplete = deepcopy(draft); incomplete['procedure']['roles']['Main']['surface_hardened_hours'] = None
    revised = g.submission_revision(original, 'procedure.docx', inputs, incomplete)
    assert session.invalidate(revised) and session.current() is None
    with pytest.raises(ValueError, match='committed independent draft'):
        session.check(path, deepcopy(inputs), revision=revised, draft=incomplete)


def ready_boundary_page(ui_boundary):
    make_page, _ = ui_boundary
    app = make_page().run()
    app.selectbox(key='job').select('CSG 20"').run()
    app.selectbox(key='mud').select('WBM').run()
    app.multiselect(key='active:CSG 20":WBM').select('Main').run()
    prefix = 'CSG 20":Main:'
    app.number_input(key=prefix+'volume').set_value(50.0)
    app.number_input(key=prefix+'density').set_value(104.0)
    app.selectbox(key=prefix+'base').select('Cement G Delijan')
    app.number_input(key=prefix+'sg').set_value(3.2)
    app.checkbox(key=prefix+'neat').check().run()
    assert not app.exception and not app.button[0].disabled
    return app


def assert_no_boundary_result(app):
    assert app.session_state['_private'].result is None
    assert 'engineer_message' not in app.session_state
    assert not any(t.key == 'engineer_message' for t in app.text_area)
    assert not any(t.value.startswith('Run receipt:') for t in app.text)
    assert not any('No discrepancies detected' in c.value for c in app.code)


def test_ui_malformed_upload_page_boundary(ui_boundary, controls):
    from io import BytesIO
    app = ready_boundary_page(ui_boundary)
    app.button[0].click().run()
    assert not app.exception
    before = app.session_state['_private'].result
    assert before['receipt']['sacks_findings'][0]['source_rounded_expected'] == '154.4'
    private = app.session_state['_private']
    original = private.document.read_bytes()
    malformed = BytesIO(b'not a zip'); malformed.name = 'private-customer-marker.docx'
    ui_boundary[1][0] = malformed
    app.run()
    assert_no_boundary_result(app)
    app.button[0].click().run()
    assert not app.exception, [e.message for e in app.exception]
    assert any('INPUT_REJECTED' in e.value and 'DOCX' in e.value for e in app.error)
    assert all('private-customer-marker' not in e.value and str(private.folder) not in e.value for e in app.error)
    assert_no_boundary_result(app)
    assert private.document.read_bytes() == original
    assert any(p.read_bytes() == b'not a zip' for p in private.folder.glob('*.docx'))
    valid = BytesIO(controls['bad']); valid.name = 'independent.docx'
    ui_boundary[1][0] = valid
    app.run(); app.button[0].click().run()
    assert not app.exception
    result = private.current()
    assert result['status'] == 'PARTIAL_FINDINGS_ONLY'
    assert result['receipt']['run_id'] != before['receipt']['run_id']
    assert result['receipt']['sacks_findings'][0]['result'] == 'DISCREPANCY'
    assert private.document.read_bytes() == original


def test_ui_catalog_timeout_page_boundary(ui_boundary, monkeypatch):
    import subprocess
    make_page, _ = ui_boundary
    original_run = subprocess.run; calls = []
    def catalog_timeout(command, *args, **kwargs):
        if len(command) >= 3 and Path(command[2]).name == 'g07_report.py':
            calls.append((command, kwargs['timeout']))
            raise subprocess.TimeoutExpired(command, kwargs['timeout'], output='private-payload-marker', stderr='/private/catalog-marker')
        return original_run(command, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(subprocess, 'run', catalog_timeout)
        app = make_page()
        app.session_state['engineer_message'] = 'stale-message-marker'
        app.run()
    assert len(calls) == 1 and calls[0][1] == 60
    assert not app.exception, [e.message for e in app.exception]
    assert 'engineer_message' not in app.session_state
    assert len(app.error) == 1
    assert 'NOT_VERIFIABLE' in app.error[0].value and 'INPUT_REJECTED' not in app.error[0].value
    assert all(token not in app.error[0].value for token in ('private-payload-marker', '/private/catalog-marker', 'g07_report.py'))
    assert not app.button and not app.code
    app.run()
    assert not app.exception and app.button[0].disabled


def test_ui_source_timeout_page_boundary(ui_boundary, monkeypatch):
    import subprocess
    app = ready_boundary_page(ui_boundary)
    app.button[0].click().run()
    assert not app.exception
    private = app.session_state['_private']; before = private.current()
    original = private.document.read_bytes()
    original_run = subprocess.run; calls = []
    def source_timeout(command, *args, **kwargs):
        if len(command) >= 3 and Path(command[2]).name == 'c04_runtime.py':
            payload = json.loads(kwargs['input'])
            calls.append((payload['action'], kwargs['timeout']))
            raise subprocess.TimeoutExpired(command, kwargs['timeout'], output='private-payload-marker', stderr='/private/source-marker')
        return original_run(command, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(subprocess, 'run', source_timeout)
        app.button[0].click().run()
    assert calls == [('baseline', 90)]
    assert not app.exception, [e.message for e in app.exception]
    assert len(app.error) == 1
    assert 'NOT_VERIFIABLE' in app.error[0].value and 'INPUT_REJECTED' not in app.error[0].value
    assert all(token not in app.error[0].value for token in ('private-payload-marker', '/private/source-marker', 'c04_runtime.py', str(private.folder)))
    assert_no_boundary_result(app)
    assert private.document.read_bytes() == original
    assert app.number_input(key='CSG 20":Main:volume').value == 50.0
    app.button[0].click().run()
    assert not app.exception
    result = private.current()
    assert result['receipt']['run_id'] != before['receipt']['run_id']
    assert result['receipt']['cement_admission']['status'] == 'SOURCE_ADMITTED'
    finding = result['receipt']['sacks_findings'][0]
    assert (finding['source_rounded_expected'], finding['raw_reported_text'], finding['delta']) == ('154.4', '999.9 sks', '845.5')
    assert app.text_area(key='engineer_message').value.startswith('Your program contains')
    app.number_input(key='CSG 20":Main:density').set_value(1.0).run()
    app.button[0].click().run()
    assert not app.exception
    assert private.current()['run_outcome'] == 'INPUT_REJECTED'
    assert app.text_area(key='engineer_message').value.startswith('INPUT_REJECTED')
    assert private.document.read_bytes() == original


def test_ui_malformed_current_receipt_page_boundary(ui_boundary):
    app = ready_boundary_page(ui_boundary)
    app.button[0].click().run()
    assert not app.exception
    private = app.session_state['_private']; original_path = private.document
    original = original_path.read_bytes()
    # An untrusted/stale document pointer must not escape the receipt rejection.
    # The original is untouched; the separate malformed copy uses intake's 0600 storage.
    with pytest.raises(zipfile.BadZipFile):
        private.store('malformed-copy.docx', b'not a zip')
    private.document = private.folder/(sha256(b'not a zip').hexdigest()+'.docx')
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    assert any('Run receipt rejected' in e.value for e in app.error)
    assert_no_boundary_result(app)
    assert all(str(private.folder) not in e.value for e in app.error)
    assert original_path.read_bytes() == original


@pytest.mark.parametrize('editor', ['additives', 'hardware'])
def test_ui_editors_preserve_source_numeric_types_and_text_syntax(editor):
    import pandas as pd
    from streamlit import config
    from streamlit.testing.v1 import AppTest
    previous = config.get_option('browser.gatherUsageStats')
    try:
        config.set_option('browser.gatherUsageStats', False)
        app = AppTest.from_file(str(g.ROOT/'checker_ui.py'), default_timeout=30).run()
        app.selectbox(key='job').select('CSG 20"').run()
        app.selectbox(key='mud').select('WBM').run()
        app.multiselect(key='active:CSG 20":WBM').select('Main').run()
        if editor == 'hardware':
            next(c for c in app.checkbox if c.label == 'Check independently entered hardware').check().run()
        assert not app.exception
        frame = app.dataframe[0 if editor == 'additives' else 1].value
        numeric = ('User Input', 'Density') if editor == 'additives' else (
            'ID (in)', 'Joint (m)', 'Weight (ppf)', 'Collapse (psi)', 'Burst (psi)')
        text = ('Material Type', 'Name', 'Physical State', 'Mix Method') if editor == 'additives' else (
            'Description', 'MD (m)', 'Size (in)', 'Grade')
        assert frame.empty  # no numeric defaults or synthesized engineering facts
        assert all(pd.api.types.is_float_dtype(frame[k]) for k in numeric), frame.dtypes
        assert all(pd.api.types.is_object_dtype(frame[k]) for k in text), frame.dtypes
        assert app.button[0].disabled
    finally:
        config.set_option('browser.gatherUsageStats', previous)


def procedure_context(operator):
    p = operator['program']; pc = p['placement_config']
    return {'selected': True, 'well_type': operator['well_geometry']['type'],
        'td_m': operator['well_geometry']['td_m'], 'geo_md': p['geo_md'],
        'target_mode': pc['target_row'], 'target_depth_m': pc['manual_depth_m'],
        'excess_mode': pc['chart_excess_mode'], 'excess': {}, 'no_additional_context': True,
        'roles': {name: {**setup, 'top_mode': p['tops'][name]['top_mode'],
            'top_depth': p['tops'][name]['top_depth'],
            'volume_basis': p['executive_summary_config']['per_slurry'][name]['volume_basis']}
            for name, setup in operator['preparation'].items()}}


@pytest.fixture(scope='module')
def procedure_catalog():
    return g.catalog()


@pytest.mark.parametrize('missing', ['td_m', 'geo_md', 'target_depth_m', 'target_mode',
    'no_additional_context', 'hardware', 'fluids', 'top_mode', 'volume_basis',
    'dead_volume_bbl', 'surface_hardened_hours', 'apply_excess'])
def test_c09_incomplete_independent_context_is_not_synthesized(procedure_control, procedure_catalog, missing):
    _, inputs, _ = procedure_control; inputs = deepcopy(inputs)
    context = procedure_context(inputs['procedure'])
    if missing in ('hardware', 'fluids'): inputs[missing] = None
    elif missing in context: context[missing] = None
    elif missing == 'apply_excess': context['excess_mode'] = 'apply'
    else: context['roles']['Main'][missing] = None
    op, status = g.procedure_input(inputs, context, procedure_catalog)
    assert op is None and status.startswith('NOT_RUN / NOT_VERIFIABLE')


def test_c09_catalog_identity_zero_and_surface_choice(procedure_control, procedure_catalog):
    _, inputs, _ = procedure_control; context = procedure_context(inputs['procedure'])
    op, status = g.procedure_input(inputs, context, procedure_catalog)
    assert op == inputs['procedure'] and status.startswith('READY')
    assert 'Mud Reserve Tanks' in procedure_catalog['procedure']['tanks']['CSG 7"']
    assert set(procedure_catalog['procedure']['well_types']) == {'Vertical', 'Directional'}
    context['roles']['Main'].update(dead_volume_bbl=0, surface_hardened_hours=0, top_mode='Surface', top_depth=None)
    op, _ = g.procedure_input(inputs, context, procedure_catalog)
    assert op['preparation']['Main']['dead_volume_bbl'] == op['preparation']['Main']['surface_hardened_hours'] == 0
    assert op['program']['tops']['Main']['top_depth'] == 0
    assert g.procedure_input(inputs, {'selected': False}, procedure_catalog)[0] is None


@pytest.mark.parametrize('unsupported', ['Directional', 'CMT PLUG', 'Pre Flush', 'crossed_volume'])
def test_c09_unsupported_or_crossed_inputs_do_not_become_reference(procedure_control, procedure_catalog, unsupported):
    _, inputs, _ = procedure_control; inputs = deepcopy(inputs)
    context = procedure_context(inputs['procedure'])
    if unsupported == 'Directional': context['well_type'] = unsupported
    elif unsupported == 'CMT PLUG': inputs['job_type'] = unsupported
    elif unsupported == 'Pre Flush': inputs['active_fluids'].insert(0, unsupported)
    else: inputs['fluids']['fluids']['Main']['volume'] = 49
    op, status = g.procedure_input(inputs, context, procedure_catalog)
    assert op is None and 'NOT_VERIFIABLE' in status


@pytest.mark.parametrize('failure', ['timeout', 'refused', 'source_rejected', 'crossed_operator'])
def test_c09_failure_preserves_other_adapters_and_safe_coverage(procedure_control, monkeypatch, failure):
    import c09_procedure
    from subprocess import TimeoutExpired
    original, inputs, _ = procedure_control; inputs = deepcopy(inputs)
    if failure == 'crossed_operator':
        inputs['procedure']['program']['fluids']['Main']['volume'] = 49
        monkeypatch.setattr(c09_procedure, 'compare_document', lambda *args: pytest.fail('Crossed reference was dispatched'))
    elif failure == 'source_rejected':
        inputs['procedure']['preparation']['Main']['surface_hardened_hours'] = -1
    else:
        def unavailable(*args):
            if failure == 'timeout': raise TimeoutExpired('/private/secret-worker', 90, stderr='PRIVATE-C09-STDERR')
            raise ValueError('/private/secret-worker PRIVATE-C09-STDERR')
        monkeypatch.setattr(c09_procedure, 'compare_document', unavailable)
    session = g.PrivateSession(); path = session.store('source.docx', original)
    result = session.check(path, inputs)
    assert {'C02', 'C03', 'C05', 'C06'} <= set(result['completed_adapters'])
    assert 'C09' not in result['completed_adapters'] and 'NOT_VERIFIABLE' in result['availability']['C09']
    assert 'PRIVATE-C09-STDERR' not in json.dumps(result) and '/private/secret-worker' not in json.dumps(result)
    assert result['run_outcome'] == 'PARTIAL_FINDINGS_ONLY' and path.read_bytes() == original


@pytest.mark.parametrize('mutation', ['hours', 'hidden'])
def test_c09_physical_note_conflict_and_visibility_keep_safe_message(procedure_control, mutation):
    original, inputs, _ = procedure_control; session = g.PrivateSession()
    path = session.store('source.docx', original); document = Document(path)
    para = next(p for p in document.paragraphs if 'Surface Sample:' in p.text)
    if mutation == 'hours': para.text = para.text.replace('8 Hours', '80 Hours')
    else: para.runs[0]._r.get_or_add_rPr().append(OxmlElement('w:vanish'))
    changed = session.folder/'mutated.docx'; document.save(changed)
    path = session.store('independent.docx', changed.read_bytes()); result = session.check(path, deepcopy(inputs))
    if mutation == 'hours':
        assert any(f['result'] == 'DISCREPANCY' and f['locator'] for f in result['results']['C09']['findings'])
        assert 'manual review' in result['message'] and 'No discrepancies detected' not in result['message']
        assert 'Observed After 8 Hours' not in result['message']
    else:
        assert 'C09' not in result['completed_adapters'] and 'NOT_VERIFIABLE' in result['availability']['C09']
    assert result['docx_written'] is result['word_modified'] is False
    assert session.folder.joinpath(sha256(original).hexdigest() + '.docx').read_bytes() == original


def test_c09_two_source_slurries_keep_distinct_tops_tanks_and_observations(procedure_control, procedure_catalog):
    from narrative_source import request
    _, original_inputs, _ = procedure_control; inputs = deepcopy(original_inputs); op = inputs['procedure']; p = op['program']
    recipe = p['cement_operator']['slurries']['Main']
    recipes = {'Lead': {**deepcopy(recipe), 'client_volume_bbl': 40},
               'Tail': {**deepcopy(recipe), 'client_volume_bbl': 10, 'density_pcf': 118}}
    p['cement_operator'] = {'job_type': p['job_type'], 'active_fluids': ['Lead', 'Tail'], 'slurries': recipes}
    p['fluids'] = {'Lead': {'volume': 40, 'density': 104, 'pump_rate': 2}, 'Tail': {'volume': 10, 'density': 118, 'pump_rate': 2}}
    p['tops'] = {n: {'top_job_type': p['job_type'], 'top_mode': 'Depth (m MD)', 'top_depth': v}
                 for n, v in (('Lead', 800), ('Tail', 900))}
    p['executive_summary_config']['per_slurry'] = {n: {'volume_basis': 'client_request'} for n in recipes}
    op['preparation'] = {'Lead': {'tank_name': 'Mud Reserve Tanks', 'dead_volume_bbl': 5, 'surface_hardened_hours': 8},
        'Tail': {'tank_name': 'Batch Mixer Tanks', 'dead_volume_bbl': 2, 'surface_hardened_hours': 10}}
    inputs.update(active_fluids=['Lead', 'Tail'], cement=p['cement_operator'])
    inputs['fluids']['fluids'] = p['fluids']
    bound, _ = g.procedure_input(inputs, procedure_context(op), procedure_catalog); assert bound == op
    with tempfile.TemporaryDirectory(dir=g.ROOT/'tmp') as folder:
        path = Path(folder)/'two.docx'; request(op, 'render_procedure', str(path)); original = path.read_bytes()
        session = g.PrivateSession(); stored = session.store('two.docx', original); result = session.check(stored, inputs)
        notes = [f for f in result['results']['C09']['findings'] if f['field'] == 'ordered_notes' and 'Mix above' in str(f.get('source_wording'))]
        assert {f['slurry'] for f in notes if f['result'] == 'MATCH'} == {'Lead', 'Tail'}
        assert result['receipt']['inputs_snapshot']['procedure']['preparation'] == op['preparation']
        assert stored.read_bytes() == original


def test_ui_c09_incomplete_draft_invalidates_without_blocking_cement(ui_boundary, controls):
    make_page, _ = ui_boundary
    app = make_page().run(); op = controls['op']; item = op['slurries']['Main']; job = op['job_type']
    app.selectbox(key='job').select(job).run(); app.selectbox(key='mud').select('WBM').run()
    app.multiselect(key=f'active:{job}:WBM').select('Main').run()
    app.checkbox(key=f'{job}:Main:neat').check().run()
    app.number_input(key=f'{job}:Main:volume').set_value(item['client_volume_bbl']).run()
    app.number_input(key=f'{job}:Main:density').set_value(item['density_pcf']).run()
    app.selectbox(key=f'{job}:Main:base').select(item['base_cement']).run()
    app.number_input(key=f'{job}:Main:sg').set_value(item['cement_sg']).run()
    app.checkbox(key='c09:selected').check().run()
    app.selectbox(key=f'c09:{job}:well_type').select('Vertical').run()
    assert not app.exception and not app.button[0].disabled
    app.button[0].click().run()
    report = app.session_state['_private'].current()
    assert {'C02', 'C03'} <= set(report['completed_adapters']) and 'C09' not in report['completed_adapters']
    assert report['availability']['C09'].startswith('NOT_RUN')
    old_revision = report['receipt']['revision']
    app.number_input(key=f'c09:{job}:td').set_value(0).run()
    session = app.session_state['_private']
    assert session.revision != old_revision and session.current() is None
    assert not any(t.label == 'Engineer message' for t in app.text_area)
    revision = session.revision; app.run()
    assert app.number_input(key=f'c09:{job}:td').value == 0 and session.revision == revision
    assert session.current() is None and not app.exception


@pytest.fixture(scope='session')
def r2b_catalog():
    return g.catalog()


@pytest.mark.parametrize('job', ['CSG 20"', 'LNR 7"', 'CMT PLUG WITH CT', 'CMT SQUEEZE'])
@pytest.mark.parametrize('mud', ['WBM', 'OBM'])
def test_r2b_catalog_conditional_roles_preserve_source_order(r2b_catalog, job, mud):
    """Actual source projection, not a new mandatory-fluid or CT-stage rule."""
    eligible = r2b_catalog['eligible'][job][mud]
    assert eligible == [f for f in r2b_catalog['order'] if f in eligible]
    assert ('Diesel' in eligible) == (mud == 'OBM')
    roles = [f for f in eligible if f in r2b_catalog['cement_roles']]
    assert roles == (['Main'] if job == 'CMT PLUG WITH CT' else ['Scavenger', 'Main', 'Lead', 'Lead #1', 'Lead #2', 'Tail'])
    request = {'job_type': job, 'mud_type': mud, 'active_fluids': ['Main'], 'cement': None}
    assert g.cement_admission(request, r2b_catalog)['status'] == 'INPUT_INCOMPLETE'
    request['active_fluids'] = ['Displacement Fluid']
    assert g.cement_admission(request, r2b_catalog)['status'] == 'NOT_APPLICABLE'


@pytest.mark.parametrize('mutation', ['CT-lead', 'WBM-diesel', 'duplicate', 'wrong-role', 'bool', 'string', 'nonfinite'])
def test_r2b_ineligible_or_untyped_submission_cannot_be_admitted(controls, r2b_catalog, mutation):
    request = submitted(controls['op'])
    if mutation == 'CT-lead':
        request['job_type'] = 'CMT PLUG WITH CT'; request['active_fluids'] = ['Main', 'Lead']
    elif mutation == 'WBM-diesel': request['active_fluids'] = ['Diesel', 'Main']
    elif mutation == 'duplicate': request['active_fluids'] = ['Main', 'Main']
    elif mutation == 'wrong-role': request['cement']['slurries']['Lead'] = request['cement']['slurries'].pop('Main')
    else:
        request['cement']['slurries']['Main']['client_volume_bbl'] = {'bool': True, 'string': '50', 'nonfinite': float('inf')}[mutation]
    assert g.cement_admission(request, r2b_catalog)['status'] == 'INPUT_REJECTED'


@pytest.mark.parametrize('job', ['CSG 20"', 'LNR 7"', 'CMT PLUG WITH CT', 'CMT SQUEEZE'])
def test_r2b_typed_source_receipt_is_not_job_or_Golden_certification(controls, job):
    request = submitted(controls['op']); request['job_type'] = request['cement']['job_type'] = job
    request['cement']['slurries']['Main']['client_volume_bbl'] = 50.0
    draft = {'slurries': deepcopy(request['cement']['slurries']), 'neat_confirmations': {'Main': True}}
    session = g.PrivateSession(); path = session.store('synthetic-control.docx', controls['bad'])
    original = path.read_bytes(); revision = g.submission_revision(original, 'synthetic-control.docx', request, draft)
    session.invalidate(revision); result = session.check(path, request, revision=revision, draft=draft)
    receipt = result['receipt']; c02 = result['results']['C03']['c02']
    assert receipt['cement_admission']['status'] == 'SOURCE_ADMITTED'
    assert receipt['inputs_snapshot'] == request and receipt['widget_snapshot'] == draft
    assert type(receipt['inputs_snapshot']['cement']['slurries']['Main']['client_volume_bbl']) is float
    assert receipt['submission_sha256'] == g.digest(request)
    assert receipt['cement_operator_sha256'] == c02['reference']['operator_input_sha256'] == g.digest(request['cement'])
    assert c02['reference']['job_applicability'] == 'NOT_VERIFIED'
    sacks = receipt['sacks_findings']; assert len(sacks) == 1
    assert sacks[0]['mapping_state'] == 'IDENTIFIED' and sacks[0]['locator'] and sacks[0]['slurry'] == 'Main'
    assert sacks[0]['raw_reported_text'] == '999.9 sks' and sacks[0]['result'] == 'DISCREPANCY'
    assert path.read_bytes() == original and result['document_sha256'] == sha256(original).hexdigest()
    assert result['docx_written'] is False and result['word_modified'] is False
    if job == 'CMT PLUG WITH CT':
        assert all(f['status'] == 'NOT_VERIFIABLE' for f in result['results']['C03']['water_findings'])
    # Frozen source identity and role association survive caller edits; changed drafts invalidate all optional state.
    request['cement']['slurries']['Main']['client_volume_bbl'] = 51.0
    assert receipt['inputs_snapshot']['cement']['slurries']['Main']['client_volume_bbl'] == 50.0
    assert session.invalidate(g.submission_revision(original, 'synthetic-control.docx', request, draft))
    assert session.current() is None and session.volume_preview is None and session.dv_preview is None
    assert session.copy_proposal is None and session.copy_output is None


def test_r2b_unprinted_active_Lead_never_borrows_Main_claims(controls):
    request = submitted(controls['op']); request['active_fluids'] = ['Main', 'Lead']
    request['cement']['active_fluids'] = ['Main', 'Lead']
    request['cement']['slurries']['Lead'] = {**deepcopy(request['cement']['slurries']['Main']), 'client_volume_bbl': 30.0}
    session = g.PrivateSession(); path = session.store('only-Main-printed.docx', controls['bad'])
    result = session.check(path, request); c03 = result['results']['C03']; c02 = c03['c02']
    assert result['receipt']['cement_admission']['roles'] == ['Main', 'Lead']
    assert result['receipt']['inputs_snapshot']['cement']['slurries']['Lead']['client_volume_bbl'] == 30.0
    assert set(c02['reference']['slurries']) == {'Main', 'Lead'}
    assert c02['reference']['slurries']['Main']['calc']['field_sacks'] != c02['reference']['slurries']['Lead']['calc']['field_sacks']
    assert not any(r.get('association') == 'Lead' for r in result['original_records'])
    assert not any(f.get('slurry') == 'Lead' for f in c02['findings'])  # no fictional Word claim/locator
    missing = next(f for f in c03['water_findings'] if f['slurry'] == 'Lead')
    assert missing['status'] == 'NOT_VERIFIABLE' and missing['reason'] and missing.get('locator') is None
    assert c02['reference']['job_applicability'] == 'NOT_VERIFIED'
    assert path.read_bytes() == controls['bad'] and result['word_modified'] is False
    wrong = deepcopy(request); del wrong['cement']['slurries']['Lead']
    assert g.cement_admission(wrong, session.source_catalog)['status'] == 'INPUT_REJECTED'
