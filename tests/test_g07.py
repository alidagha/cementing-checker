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
