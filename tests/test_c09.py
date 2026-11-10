"""C09 genuine source projection and independent procedure/NOTE mutations."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from docx import Document
import pytest

from checker_parser import parse_docx
from comparison_records import ROOT
from narrative_source import request
from c09_procedure import compare_document
from test_c08 import operator as program


def operator():
    p=program();p['cement_operator']['slurries']['Main']['additives']=[
        {'Material Type':'Anti Foam','Name':'TA-47','Physical State':'Liquid','Mix Method':'In Mix Water','User Input':0.03},
        {'Material Type':'Custom Powder','Name':'Synthetic Powder','Physical State':'Powder','Mix Method':'In Mix Water','User Input':1,'Density':1.4}]
    return {'program':p,'preparation':{'Main':{'tank_name':'Mud Reserve Tanks','dead_volume_bbl':5,'surface_hardened_hours':8}},
        'well_geometry':{'version':1,'type':'Vertical','td_m':1000}}


@pytest.fixture(scope='module')
def case():
    with tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='c09-') as folder:
        p=Path(folder)/'synthetic.docx';op=operator();source=request(op,'render_procedure',str(p))
        yield p,op,source


def test_actual_source_state_signature_and_independent_wording_oracles(case):
    p,op,source=case;ref=source['reference'];text=ref['official_generated_text']
    assert ref['approval_flags_supplied'] is False and ref['session_state_implementation']=='streamlit.runtime.state.session_state_proxy'
    assert ref['procedure_source_signature']
    assert {'phase_10_procedure.py:generate_official_procedure','phase_10_procedure.py:build_ordered_notes',
        'phase_10_procedure.py:synchronize_report_texts','phase_5_cement.py:refresh_cement_calculations'}<=set(ref['source_calls'])
    assert '1. Clean up Mud Reserve Tanks and preparing chemicals for mixing fluid.' in text
    assert 'Mix and pump 50.0 bbl Main cement slurry (104 pcf).' in text
    assert 'Add TA-47 to Fresh Water and allow mixing for 10 min.' in text
    assert 'Add Synthetic Powder and allow mixing until the cement operation will finish.' in text
    assert 'NOTE 1: The Calculated Temperature is based on True Vertical Depth.' in ref['all_source_notes']
    assert any('Surface Sample: Hardened Condition Observed After 8 Hours' in n for n in ref['all_source_notes'])
    result=compare_document(p,op)
    assert result['status']=='PARTIAL_FINDINGS_ONLY' and result['findings']
    assert any(f['result']=='MATCH' and f['field']=='procedure' for f in result['findings'])
    assert all(f['result']!='DISCREPANCY' for f in result['findings'])
    assert any(f['field']=='procedure' and f['result']=='NOT_VERIFIABLE' and 'rig-site' in f['reason'] for f in result['findings'])
    assert all(f['result']=='MATCH' for f in result['findings'] if f['field']=='ordered_notes')
    assert any(f['slurry']=='Main' and 'Mix above' in str(f['source_wording']) for f in result['findings'])
    assert result['records']==parse_docx(p)['records'] and result['unverified_record_orders']


@pytest.mark.parametrize('mutation',['wording','numbering','reorder','omit','duplicate','tank','water','mix-time','cross-fluid','cross-section','unknown-heading'])
def test_untrusted_procedure_mutations_never_false_match(case,monkeypatch,mutation):
    p,op,source=case;monkeypatch.setattr('c09_procedure.request',lambda *a:source)
    d=Document(p);start=next(i for i,x in enumerate(d.paragraphs) if x.text.strip()=='X. Cementing Procedure' or x.text.strip()=='IX. Cementing Procedure')
    paragraphs=[x for x in d.paragraphs[start+1:] if x.text.strip()]
    first=next(x for x in paragraphs if x.text.startswith('1. '))
    if mutation=='wording':first.text=first.text.replace('Clean up','Do not clean')
    elif mutation=='numbering':first.text=first.text.replace('1. ','99. ',1)
    elif mutation=='reorder':first._p.addprevious(deepcopy(paragraphs[1]._p));paragraphs[1]._p.getparent().remove(paragraphs[1]._p)
    elif mutation=='omit':first._p.getparent().remove(first._p)
    elif mutation=='duplicate':first._p.addnext(deepcopy(first._p))
    elif mutation in ('tank','water'):
        para=next(x for x in paragraphs if 'Fill up' in x.text)
        para.text=para.text.replace('Mud Reserve Tanks','Cement Unit Tanks') if mutation=='tank' else para.text.replace(' bbl','0 bbl',1)
    elif mutation=='mix-time':
        para=next(x for x in paragraphs if '10 min.' in x.text);para.text=para.text.replace('10 min.','100 min.')
    elif mutation=='cross-fluid':
        para=next(x for x in paragraphs if 'Mix and pump' in x.text);para.text=para.text.replace('Main','Tail')
    elif mutation=='cross-section':d.paragraphs[start].text='Executive Summary'
    else:first._p.get_or_add_pPr().get_or_add_pStyle().val='Heading2';first.text='Unproved subsection'
    target=p.parent/(mutation+'.docx');d.save(target)
    r=compare_document(target,op)
    assert any(f['result'] in ('DISCREPANCY','NOT_VERIFIABLE') for f in r['findings'])
    assert not any(f['field']=='procedure.sequence' and f['result']=='MATCH' for f in r['findings'])


@pytest.mark.parametrize('mutation',['duplicate','omit','renumber','tank','water','hours','cross-section','break-group'])
def test_note_identity_order_and_source_group_negatives(case,monkeypatch,mutation):
    p,op,source=case;monkeypatch.setattr('c09_procedure.request',lambda *a:source)
    d=Document(p);para=next(p for p in d.paragraphs if 'Mix above Additives in' in p.text)
    if mutation=='duplicate':para._p.addnext(deepcopy(para._p))
    elif mutation=='omit':para._p.getparent().remove(para._p)
    elif mutation=='renumber':para.text=para.text.replace('NOTE 5:','NOTE 55:')
    elif mutation=='tank':para.text=para.text.replace('Mud Reserve Tanks','Cement Unit Tanks')
    elif mutation=='water':para.text=para.text.replace(' bbl','0 bbl',1)
    elif mutation=='hours':
        para=next(p for p in d.paragraphs if 'Surface Sample:' in p.text);para.text=para.text.replace('8 Hours','80 Hours')
    elif mutation=='cross-section':
        proc=next(p for p in d.paragraphs if p.text.endswith('Cementing Procedure'));proc._p.addnext(deepcopy(para._p));para._p.getparent().remove(para._p)
    else:
        para.insert_paragraph_before('Unrelated unproved paragraph')
    target=p.parent/('note-'+mutation+'.docx');d.save(target);r=compare_document(target,op)
    assert not any(f['field']=='ordered_notes.sequence' and f['result']=='MATCH' for f in r['findings'])
    assert any(f['result'] in ('DISCREPANCY','NOT_VERIFIABLE') for f in r['findings'])


@pytest.mark.parametrize('bad',['missing','duplicate-role','negative','nan','tank','lab','ct','squeeze-incomplete','preflush','spacer'])
def test_incomplete_independent_context_and_unsupported_paths(case,bad):
    p,op,_=case;op=deepcopy(op)
    if bad=='missing':del op['preparation']
    elif bad=='duplicate-role':op['preparation']['Tail']=op['preparation']['Main']
    elif bad=='negative':op['preparation']['Main']['dead_volume_bbl']=-1
    elif bad=='nan':op['preparation']['Main']['dead_volume_bbl']=float('nan')
    elif bad=='tank':op['preparation']['Main']['tank_name']='Invented Tank'
    elif bad=='lab':del op['preparation']['Main']['surface_hardened_hours']
    elif bad=='ct':op['program']['job_type']='CMT PLUG WITH CT'
    elif bad=='squeeze-incomplete':op['program']['job_type']='CMT SQUEEZE'
    else:
        fluid='Pre Flush' if bad=='preflush' else 'Spacer'
        op['program']['fluids'][fluid]={'volume':10,'density':65,'pump_rate':2}
    result=compare_document(p,op)
    assert all(f['result']=='NOT_VERIFIABLE' for f in result['findings'])
    assert len(result['unverified_record_orders'])==len(result['records'])


def test_two_slurries_distinct_tanks_and_operational_spacer_source_projection():
    op=operator();p=op['program'];p['job_type']='CSG 7"';job=p['job_type']
    p['placement_config']['job_type']=job;p['executive_summary_config']['job_type']=job
    original=p['cement_operator']['slurries']['Main']
    p['fluids']={'Lead':{'volume':40,'density':104,'pump_rate':2},
        'Tail':{'volume':10,'density':118,'pump_rate':2},
        'Spacer Behind':{'volume':5,'density':70,'pump_rate':2,'material_name':'Synthetic operational spacer'}}
    p['cement_operator']={'job_type':job,'active_fluids':['Lead','Tail','Spacer Behind'],
        'slurries':{'Lead':{**original,'client_volume_bbl':40},'Tail':{**original,'client_volume_bbl':10,'density_pcf':118}}}
    p['tops']={n:{'top_job_type':job,'top_mode':'Depth (m MD)','top_depth':900} for n in ('Lead','Tail')}
    p['executive_summary_config']['per_slurry']={n:{'volume_basis':'client_request'} for n in ('Lead','Tail')}
    op['preparation']={'Lead':{'tank_name':'Mud Reserve Tanks','dead_volume_bbl':5,'surface_hardened_hours':8},
        'Tail':{'tank_name':'Batch Mixer Tanks','dead_volume_bbl':2,'surface_hardened_hours':10}}
    with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
        path=Path(folder)/'two-slurry.docx';source=request(op,'render_procedure',str(path));r=compare_document(path,op)
        assert not any(f['result']=='DISCREPANCY' for f in r['findings'])
        notes=[f for f in r['findings'] if f['field']=='ordered_notes' and 'Mix above' in str(f['source_wording'])]
        assert {f['slurry'] for f in notes}=={'Lead','Tail'} and all(f['result']=='MATCH' for f in notes)
        assert 'Spacer Behind' in source['reference']['official_generated_text']
        # The aggregate preparation instruction is verified as exact source text,
        # never apportioned/inverted to infer individual allowance/tank proof.
        assert 'Lead:' in source['reference']['official_generated_text'] and 'Tail:' in source['reference']['official_generated_text']


def test_manual_procedure_independent_approval_and_no_source_gate_override(case):
    p,op,_=case;op=deepcopy(op);text='1. Independent reviewed synthetic instruction.\n2. Confirm the independently reviewed plan.'
    op['manual_procedure']={'text':text,'approval_reference':'SYNTHETIC independent approval record','text_sha256':hashlib.sha256(text.encode()).hexdigest()}
    with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
        target=Path(folder)/'manual.docx';source=request(op,'render_procedure',str(target));r=compare_document(target,op)
        assert all(f['result']=='MATCH' for f in r['findings'] if f['field']=='procedure')
        assert source['reference']['kind']=='INDEPENDENT_APPROVED_MANUAL_TEXT' and source['reference']['approval_flags_supplied'] is False
        op['manual_procedure']['approval_reference']=''
        assert all(f['result']=='NOT_VERIFIABLE' for f in compare_document(target,op)['findings'])


def test_cli_determinism_preserves_document_operator_and_raw_records(case):
    p,op,_=case;operator_path=p.parent/'operator.json';operator_path.write_text(json.dumps(op));before=(p.read_bytes(),operator_path.read_bytes())
    cmd=[sys.executable,'-B',str(ROOT/'c09_procedure.py'),str(p),str(operator_path)]
    a=subprocess.run(cmd,text=True,capture_output=True,check=True);b=subprocess.run(cmd,text=True,capture_output=True,check=True)
    assert a.stdout==b.stdout
    result=json.loads(a.stdout);assert result['status']=='PARTIAL_FINDINGS_ONLY' and result['records']==parse_docx(p)['records']
    assert before==(p.read_bytes(),operator_path.read_bytes())


@pytest.mark.parametrize('location',['procedure','note','summary'])
@pytest.mark.parametrize('mechanism',['numbering','field','hidden'])
def test_automatic_word_numbering_fails_closed(case,monkeypatch,location,mechanism):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from c08_summary import compare_document as compare_summary
    p,op,source=case;monkeypatch.setattr('c09_procedure.request',lambda *a:source)
    d=Document(p)
    if location=='procedure':para=next(p for p in d.paragraphs if p.text.startswith('1. '))
    elif location=='note':para=next(p for p in d.paragraphs if 'Mix above Additives in' in p.text)
    else:para=next(p for p in d.paragraphs if p.text.startswith('Enclosed'))
    if mechanism=='numbering':
        numbering=OxmlElement('w:numPr');identifier=OxmlElement('w:numId');identifier.set(qn('w:val'),'987654')
        numbering.append(identifier);para._p.get_or_add_pPr().append(numbering)
    elif mechanism=='field':para._p.append(OxmlElement('w:fldSimple'))
    else:para.runs[0]._r.get_or_add_rPr().append(OxmlElement('w:vanish'))
    target=p.parent/(mechanism+'-'+location+'.docx');d.save(target)
    r=compare_summary(target,op['program']) if location=='summary' else compare_document(target,op)
    assert all(f['result']=='NOT_VERIFIABLE' for f in r['findings'])


def test_r2f_source_placeholders_never_complete_an_ordered_sequence(case,monkeypatch):
    p,op,source=case;monkeypatch.setattr('c09_procedure.request',lambda *a:source)
    r=compare_document(p,op)
    unresolved=[f for f in r['findings'] if f['field']=='procedure' and 'rig-site' in f['reason']]
    assert unresolved and all(f['result']=='NOT_VERIFIABLE' for f in unresolved)
    sequence=next(f for f in r['findings'] if f['field']=='procedure.sequence')
    assert sequence['result']=='NOT_VERIFIABLE', 'An unresolved source placeholder received complete-sequence MATCH'


def test_r2f_CT_source_block_cannot_complete_C09(case):
    p,op,_=case;op=deepcopy(op);op['program']['job_type']='CMT PLUG WITH CT'
    r=compare_document(p,op)
    assert r['status']=='NOT_VERIFIABLE', 'Unadmitted CT narrative reported a completed partial adapter'
    assert r['records']==parse_docx(p)['records'] and len(r['unverified_record_orders'])==len(r['records'])
    assert all(f['result']=='NOT_VERIFIABLE' for f in r['findings'])


@pytest.mark.parametrize('fluid',['Spacer','Scavenger','Pre Flush','Diesel'])
def test_r2f_special_fluid_blocks_all_unadmitted_stage_credit(case,fluid):
    p,op,_=case;op=deepcopy(op);op['program']['fluids'][fluid]={'volume':5,'density':70,'pump_rate':2}
    r=compare_document(p,op);a=r['availability']
    assert r['status']=='NOT_VERIFIABLE' and not a['source_reference_admitted']
    assert a['source_sha']=='60dffefb8c941ad90cb7caba0992126a35803717'
    assert {s['stage'] for s in a['stages']}=={'procedure','ordered_notes'}
    assert all(s['state']=='SOURCE_BLOCKED' and not s['sequence_complete'] and s['physical_findings']==0 for s in a['stages'])
    assert {(s['stage'],s['fluid']) for s in a['role_stages']}=={(stage,role) for stage in ('procedure','ordered_notes') for role in op['program']['fluids']}
    assert all(s['state']=='SOURCE_BLOCKED' and s['physical_findings']==0 and s['reason'] for s in a['role_stages'])
    assert a['verified_production_claim_instances']==0 and a['authentic_golden_status']=='NOT_RUN'
    assert len(r['unverified_record_orders'])==len(r['records'])
    actual=[x for x in r['records'] if x['section']!='excluded' and (x['section']=='procedure' or x['note'] is not None)]
    assert [(f['original_source_order'],f['raw_reported_text'],f['locator']) for f in r['findings']]==[(x['source_order'],x['raw_text'],x['locator']) for x in actual]


@pytest.mark.parametrize('mutation',['operator','source'])
def test_r2f_forged_reference_never_admits_physical_or_role_credit(case,monkeypatch,mutation):
    p,op,source=case;swapped=deepcopy(source);swapped['operator_input_sha256' if mutation=='operator' else 'source_sha']='0'*64
    monkeypatch.setattr('c09_procedure.request',lambda *a:swapped);r=compare_document(p,op)
    assert r['status']=='NOT_VERIFIABLE' and r['reference']=={}
    assert all(s['state']=='SOURCE_BLOCKED' and s['physical_findings']==0 for s in r['availability']['role_stages'])


def test_r2f_physical_visibility_failure_is_distinct_from_source_admission(case,monkeypatch):
    from docx.oxml import OxmlElement
    p,op,source=case;monkeypatch.setattr('c09_procedure.request',lambda *a:source);d=Document(p)
    para=next(x for x in d.paragraphs if x.text.startswith('1. '));para.runs[0]._r.get_or_add_rPr().append(OxmlElement('w:vanish'))
    target=p.parent/'r2f-hidden.docx';d.save(target);r=compare_document(target,op)
    assert r['status']=='NOT_VERIFIABLE' and r['availability']['source_reference_admitted']
    assert all(s['state']=='PHYSICAL_ASSOCIATION_UNPROVEN' and not s['sequence_complete'] for s in r['availability']['stages'])
    assert r['records']==parse_docx(target)['records'] and len(r['unverified_record_orders'])==len(r['records'])


def test_r2f_manual_text_cannot_bypass_special_source_or_forge_approval(case):
    p,op,_=case;op=deepcopy(op);text='1. Synthetic independently supplied text.'
    op['manual_procedure']={'text':text,'approval_reference':'SYNTHETIC reference only','text_sha256':'0'*64}
    assert compare_document(p,op)['status']=='NOT_VERIFIABLE'
    op['manual_procedure']['text_sha256']=hashlib.sha256(text.encode()).hexdigest();op['program']['job_type']='CMT PLUG WITH CT'
    r=compare_document(p,op)
    assert r['status']=='NOT_VERIFIABLE' and not r['availability']['source_reference_admitted']


@pytest.mark.parametrize('role',['Spacer Ahead','Spacer Behind'])
def test_r2f_operational_spacer_identity_is_not_standalone_recipe(role):
    op=operator();p=op['program'];p['fluids'][role]={'volume':5,'density':70,'pump_rate':2,'material_name':'Synthetic operational spacer'}
    p['cement_operator']['active_fluids']=['Spacer Ahead','Main'] if role=='Spacer Ahead' else ['Main','Spacer Behind']
    with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
        target=Path(folder)/'operational.docx';source=request(op,'render_procedure',str(target));r=compare_document(target,op)
        assert role in source['reference']['official_generated_text'] and 'Spacer' not in source['reference']['preparation']
        assert r['status']=='PARTIAL_FINDINGS_ONLY' and r['availability']['source_reference_admitted']
        assert r['availability']['verified_production_claim_instances']==0
        own=[s for s in r['availability']['role_stages'] if s['fluid']==role and s['stage']=='ordered_notes']
        assert len(own)==1 and own[0]['state']=='PHYSICAL_ASSOCIATION_UNPROVEN' and own[0]['physical_findings']==0


def test_r2f_original_CT_stage_authority_is_available_but_not_C09_admission():
    from narrative_source import SNAPSHOT
    from c02_engine import verify_source
    verify_source()
    code='''
import copy,json
from ct_stages import ct_stage_projection,stage_note,allocate_stages
from materials_db import CT_JOB,get_available_tanks
assert 'Mud Reserve Tanks' in get_available_tanks(CT_JOB)
s={'job_type':CT_JOB,'fluids_config':{'active':['Main'],'params':{'Main':{'volume':20}}},
   'ct_stage_config':{'job_type':CT_JOB,'main_volume':'20','count':2},
   'cement_params':{'Main':{'mix_water':9,'dead_vol':1,'tank_name':'Mud Reserve Tanks'}}}
p=ct_stage_projection(s)
assert tuple(map(str,p['cement_bbl']))==('10','10') and p['count']==2
assert 'Main cement stages (bbl): 10 + 10.' in stage_note(p)
bad=[]
for change in ('missing','stale','boolean','capacity','wrong-job'):
 t=copy.deepcopy(s)
 if change=='missing':t.pop('ct_stage_config')
 elif change=='stale':t['ct_stage_config']['main_volume']='19'
 elif change=='boolean':t['ct_stage_config']['count']=True
 elif change=='capacity':t['fluids_config']['params']['Main']['volume']=37;t['ct_stage_config']['main_volume']='37'
 else:t['ct_stage_config']['job_type']='CSG 7"'
 try:ct_stage_projection(t)
 except ValueError:bad.append(change)
assert len(bad)==5
assert tuple(map(str,allocate_stages(12)))==('12',)
print(json.dumps({'scope':'SYNTHETIC SOURCE STAGE UNIT CONTROL ONLY; NOT CT PROJECT/C09/WORD ADMISSION','negative_controls':bad}))
'''
    result=subprocess.run([sys.executable,'-B','-c',code],cwd=SNAPSHOT,text=True,capture_output=True,check=True)
    assert json.loads(result.stdout)['negative_controls']==['missing','stale','boolean','capacity','wrong-job']
    verify_source()


def test_r2f_factorized_matrix_covers_original_jobs_roles_and_stage_boundaries():
    import ast
    from narrative_source import SNAPSHOT
    text=(ROOT/'docs/coverage/R2F-ct-special-stage.md').read_text();d=json.loads(text.split('```json\n',1)[1].split('\n```',1)[0])
    tree=ast.parse((SNAPSHOT/'materials_db.py').read_text());values={}
    for n in tree.body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
            name=n.targets[0].id
            if name=='CT_JOB':values[name]=ast.literal_eval(n.value)
            if name=='JOB_TYPES':values[name]=[v.value if isinstance(v,ast.Constant) else values[v.id] for v in n.value.elts]
    assert [j['job_type'] for j in d['jobs']]==values['JOB_TYPES'] and [j['id'] for j in d['jobs']]==[f'J{i:02}' for i in range(1,16)]
    assert [r['fluid'] for r in d['roles']]==['Diesel','Pre Flush','Spacer','Spacer Ahead','Scavenger','Main','Lead','Lead #1','Lead #2','Tail','Spacer Behind','Displacement Fluid']
    assert {s['stage'] for s in d['stages']}=={'summary','procedure','ordered_notes'}
    assert len({(j['job_type'],r['fluid'],s['stage']) for j in d['jobs'] for r in d['roles'] for s in d['stages']})==540
    ct=next(j for j in d['jobs'] if j['job_type']==values['CT_JOB']);assert ct['current_C09_reference']==ct['current_g07_procedure']=='SOURCE_BLOCKED' and ct['reason']
    assert {r['fluid'] for r in d['roles'] if r['C09_reference']=='SOURCE_BLOCKED'}=={'Diesel','Pre Flush','Spacer','Scavenger'}
    assert all(j['reason'] for j in d['jobs']) and all(r['reason'] for r in d['roles'])
    assert d['source_commit']=='60dffefb8c941ad90cb7caba0992126a35803717' and d['template_sha256']=='a1128b0e9352e1dd7c8768eecc9335c50858356cee80ed33c0ec275e26c4d08b'
    assert d['physical_default']=='PHYSICAL_ASSOCIATION_UNPROVEN' and d['production_claim_credit']==0 and d['authentic_golden']=='NOT_RUN'
    assert set(d['excluded'])=={'cover/document control','Survey','Centralizer','pore/fracture pressure','IOD','figures/schematics','attachments/TOC'}


def test_r2f_squeeze_scope_is_not_inferred_from_candidate_Word():
    op=operator();p=op['program'];job='CMT SQUEEZE';p['job_type']=job;p['cement_operator']['job_type']=job
    p['placement_config']['job_type']=job;p['executive_summary_config']['job_type']=job
    p['tops']['Main']['top_job_type']=job
    assert 'squeeze_scope' not in p['executive_summary_config']
    with pytest.raises(ValueError,match='Independent squeeze scope required'):
        request(op,'procedure')


def test_r2g2_source_density_expression_has_physical_atomic_attribution(case):
    import ast
    from docx.oxml.ns import qn
    from narrative_source import SNAPSHOT
    p,op,source=case
    tree=ast.parse((SNAPSHOT/'phase_10_procedure.py').read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_ordered_notes')
    assignment=next(n for n in function.body if isinstance(n,ast.Assign) and
        isinstance(n.targets[0],ast.Subscript) and isinstance(n.targets[0].slice,ast.Constant) and
        n.targets[0].slice.value=='note_densities')
    expression=ast.literal_eval(assignment.value.args[0])
    full=source['reference']['all_source_notes'][1]
    assert full.endswith(expression) and full.count(expression)==1
    result=compare_document(p,op)
    parent=next(f for f in result['findings'] if f['field']=='ordered_notes' and (f['source_wording'] or '').endswith(full))
    assert parent['result']=='MATCH' and parent['slurry'] is None
    paragraph=Document(p).element.body[parent['locator']['body_block']]
    texts=list(paragraph.iter(qn('w:t')))
    assert len(texts)==1 and texts[0].text==full
    from checker_parser import text_of
    templates=[node for node in Document(SNAPSHOT/'master_template.docx').element.body.iter(qn('w:p'))
        if '{{ note_densities }}' in text_of(node)]
    assert len(templates)==1
    prefix,suffix=text_of(templates[0]).split('{{ note_densities }}')
    assert suffix=='' and parent['raw_reported_text']==prefix+full
    proof={'source_line':assignment.lineno,'source_expression_sha256':hashlib.sha256(expression.encode()).hexdigest(),
        'source_document_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'locator':parent['locator'],
        'character_start':len(prefix+full)-len(expression),'character_end':len(prefix+full),'text_nodes':1}
    (ROOT/'evidence'/('r2g2-expression-proof-'+proof['source_document_sha256']+'.json')).write_text(json.dumps(proof,indent=2))
    atom=next((f for f in result['findings'] if f['field']=='ordered_notes.density_conditions.atom'),None)
    assert atom is not None, 'MISSING_ATOMIC_ATTRIBUTION_FOR_PROVED_SOURCE_EXPRESSION'
    assert atom['result']=='MATCH' and atom['raw_reported_text']==expression
    assert atom['atom_proof']['character_span']==[proof['character_start'],proof['character_end']]
    assert atom['read_only'] and atom['correction_eligible'] is False
    assert atom['unit'] is atom['full_precision_expected'] is None


@pytest.mark.parametrize('mutation',['duplicate-text','duplicate-paragraph','missing','reorder','split-paragraph',
    'split-runs','merged-runs','wrapped-run','unit','case','punctuation','line-break','numbering','hidden','field','excluded','cross-role'])
def test_r2g2_uncertain_physical_atom_never_receives_credit(case,monkeypatch,mutation):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    p,op,source=case;monkeypatch.setattr('c09_procedure.request',lambda *a:source)
    d=Document(p);full=source['reference']['all_source_notes'][1]
    para=next(x for x in d.paragraphs if x.text.endswith(full));raw=para.text
    if mutation=='duplicate-text':para.text=raw+raw
    elif mutation=='duplicate-paragraph':para._p.addnext(deepcopy(para._p))
    elif mutation=='missing':para._p.getparent().remove(para._p)
    elif mutation=='reorder':
        other=para._p.getnext();other.addnext(para._p)
    elif mutation=='split-paragraph':
        para.text=raw[:20];para.insert_paragraph_before(raw[20:])
    elif mutation=='split-runs':
        para.clear();para.add_run(raw[:20]);para.add_run(raw[20:])
    elif mutation=='merged-runs':
        para.clear();para.add_run(raw)
    elif mutation=='wrapped-run':
        run=next(r for r in para.runs if r.text.endswith(full));wrapper=OxmlElement('w:hyperlink');run._r.addprevious(wrapper);wrapper.append(run._r)
    elif mutation=='unit':para.text=raw.replace('degF','degC')
    elif mutation=='case':para.text=raw.lower()
    elif mutation=='punctuation':para.text=raw.replace('atmosphere','atmosphere;')
    elif mutation=='line-break':para.text=raw.replace(' and ','\n and ')
    elif mutation=='numbering':para._p.get_or_add_pPr().append(OxmlElement('w:numPr'))
    elif mutation=='hidden':para.runs[-1]._r.get_or_add_rPr().append(OxmlElement('w:vanish'))
    elif mutation=='field':para._p.append(OxmlElement('w:fldSimple'))
    elif mutation=='excluded':para.insert_paragraph_before('Document Control')
    else:
        other=next(x for x in d.paragraphs if 'Mix above Additives' in x.text);other._p.addnext(deepcopy(para._p))
    target=p.parent/('atom-'+mutation+'.docx');d.save(target);before=target.read_bytes()
    result=compare_document(target,op)
    atoms=[f for f in result.get('findings',[]) if f['field']=='ordered_notes.density_conditions.atom']
    assert not atoms or all(f['result']=='NOT_VERIFIABLE' and f['atom_proof'] is None for f in atoms)
    assert target.read_bytes()==before


@pytest.mark.parametrize('mutation',['operator','source','module','format','placeholder','document'])
def test_r2g2_crossed_source_receipts_and_formatting_have_no_atom(case,monkeypatch,mutation):
    p,op,source=case;bad=deepcopy(source)
    if mutation=='operator':bad['operator_input_sha256']='0'*64
    elif mutation=='source':bad['source_sha']='0'*40
    elif mutation=='module':bad['source_module_sha256']['phase_10_procedure.py']='0'*64
    elif mutation=='format':bad['reference']['all_source_notes'][1]=bad['reference']['all_source_notes'][1].replace('70','70.000')
    elif mutation=='placeholder':bad['reference']['all_source_notes'][1]='NOTE ....: rig-site value unknown'
    else:
        import c09_procedure
        original=c09_procedure.parse_docx
        def crossed(path):
            result=original(path);result['source_document_sha256']='0'*64;return result
        monkeypatch.setattr(c09_procedure,'parse_docx',crossed)
    monkeypatch.setattr('c09_procedure.request',lambda *a:bad)
    result=compare_document(p,op)
    atoms=[f for f in result['findings'] if f['field']=='ordered_notes.density_conditions.atom']
    if not result['reference']:
        assert not atoms  # Preserve the original one-to-one source-blocked raw findings.
    else:
        assert len(atoms)==1 and atoms[0]['result']=='NOT_VERIFIABLE' and atoms[0]['atom_proof'] is None


def test_r2g2_global_literal_does_not_promote_embedded_numbers_or_slurry_fields(case,monkeypatch):
    p,op,source=case;monkeypatch.setattr('c09_procedure.request',lambda *a:source)
    result=compare_document(p,op);atoms=[f for f in result['findings'] if f.get('atom_proof')]
    assert len(atoms)==1 and atoms[0]['slurry'] is None
    assert atoms[0]['association_scope']=='GLOBAL_DENSITY_DISPLAY_CONVENTION_NOT_A_SLURRY'
    assert atoms[0]['unit'] is atoms[0]['full_precision_expected'] is None
    assert atoms[0]['atom_proof']['measurement'] is False
    assert next(f for f in result['findings'] if f['field']=='procedure.sequence')['result']=='NOT_VERIFIABLE'


def test_r2g2_expression_ast_must_be_the_exact_hashed_source_bytes(case,monkeypatch):
    import ast
    from narrative_source import SNAPSHOT
    p,op,source=case;monkeypatch.setattr('c09_procedure.request',lambda *a:source)
    target=SNAPSHOT/'phase_10_procedure.py';original=Path.read_text;tree=ast.parse(original(target))
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_ordered_notes')
    assignment=next(n for n in function.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Subscript)
        and isinstance(n.targets[0].slice,ast.Constant) and n.targets[0].slice.value=='note_densities')
    expected=assignment.value.args[0].value
    assignment.value.args[0]=ast.Constant(expected[-5:])
    forged=ast.unparse(tree)
    # Simulate different contents on a second source read; never mutate the snapshot.
    monkeypatch.setattr(Path,'read_text',lambda self,*a,**k:forged if self==target else original(self,*a,**k))
    result=compare_document(p,op)
    atom=next(f for f in result['findings'] if f['field']=='ordered_notes.density_conditions.atom')
    assert atom['result']=='NOT_VERIFIABLE' or atom['source_wording']==expected
