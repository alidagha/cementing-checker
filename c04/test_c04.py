"""Bounded C04 controls; source-rendered synthetic documents, not goldens."""
from copy import deepcopy
from decimal import Decimal
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from docx import Document
import pytest
import c04_preview as cp
import c04_runtime as rt


@pytest.fixture(scope='session')
def cases(tmp_path_factory):
    folder=tmp_path_factory.mktemp('source-rendered')
    main=json.loads((rt.HERE/'fixtures/operator-main.json').read_text())
    out={'main':{'path':rt.HERE/'fixtures/synthetic-main.docx','op':main,
        'expected':json.loads((rt.HERE/'fixtures/synthetic-main-source.json').read_text())}}
    for name in ('source10','two','zero','neat'):
        op=deepcopy(main)
        if name=='two':
            recipe=op['slurries'].pop('Main');op['active_fluids']=['Lead','Tail'];op['job_type']='CSG 9 5/8"'
            op['slurries']={'Lead':recipe,'Tail':dict(recipe,density_pcf=118)}
        elif name=='zero':
            for row in op['slurries']['Main']['additives']:row['User Input']=0
        elif name=='neat':op['slurries']['Main']['additives']=[]
        path=folder/(name+'.docx')
        setup={f:{'dead':10 if name=='source10' else 2 if f=='Tail' else 5,
                  'tank':'Batch Mixer Tanks' if f=='Tail' else 'Mud Reserve Tanks'} for f in op['slurries']}
        expected=rt.call({'action':'fixture','operator':op,'docx':str(path),'fixture':setup})
        target=rt.HERE/'fixtures'/(name+'.docx');target.write_bytes(path.read_bytes())
        (rt.HERE/'fixtures'/(name+'-operator.json')).write_text(json.dumps(op,indent=2))
        (rt.HERE/'fixtures'/(name+'-source.json')).write_text(json.dumps(expected,indent=2))
        out[name]={'path':target,'op':op,'expected':expected}
    return out


@lru_cache(maxsize=32)
def computed(path,operator,edit):
    return cp.preview(path,json.loads(operator),json.loads(edit))


def scenario(case,dead=10,fluid='Main'):
    return deepcopy(computed(str(case['path']),json.dumps(case['op'],sort_keys=True),json.dumps({'slurry':fluid,'corrected_dead_volume_bbl':dead},sort_keys=True)))


def selected(result):
    assert result['status']=='PARTIAL_FINDINGS_ONLY',result.get('reason')
    assert not result['docx_written']
    return result['selected_dead_volume_preview']


def test_red_case_green_source_native_independent_projection(cases):
    r=scenario(cases['main']);p=selected(r)
    before=json.loads((rt.HERE/'evidence/c03-baseline.json').read_text())
    assert r['c03']==before
    assert p['slurry']=='Main' and p['tank_from_word']=='Mud Reserve Tanks'
    assert p['after_source_tables']=={k:cases['source10']['expected']['fixture_expected']['Main'][k] for k in ('blend','additives')}
    assert p['proposed_dead_volume_bbl']==10
    assert p['new_preparation_water_note_display_bbl']=='44.2'
    assert p['mixing_note_preview']['status']=='REQUIRES_MANUAL_VERIFICATION'
    assert any(f['result']=='UNIMPLEMENTED' for f in r['c03']['c02']['findings'])
    assert r['hashes']['original_document_sha256']==r['hashes']['new_document_sha256']
    assert r['hashes']['original_operator_sha256']==r['hashes']['new_operator_sha256']
    assert p['original_inferred_dead_volume']['not_a_measured_heel']
    assert all(g['before_qualification']=='INFERRED_NONUNIQUE_AT_WORD_DISPLAY_PRECISION' for g in p['gross_additive_preview'])


def test_independently_pinned_neat_reference_and_zero(cases):
    p=selected(scenario(cases['neat'],10))
    # Pinned original neat reference already established independently in C02/C03.
    assert abs(p['pure_mix_water_full_precision_bbl']-34.848484848484844)<1e-12
    assert abs(p['new_preparation_water_full_precision_bbl']-44.848484848484844)<1e-12
    z=selected(scenario(cases['neat'],0))
    assert z['new_preparation_water_full_precision_bbl']==z['pure_mix_water_full_precision_bbl']
    assert z['new_preparation_water_note_display_bbl']=='34.8'


def test_powder_liquid_salt_dry_blend_and_unaffected_lab(cases):
    z=selected(scenario(cases['main'],0));p=selected(scenario(cases['main'],10))
    assert {g['material'] for g in p['gross_additive_preview']}=={'C03 Powder','C03 Liquid','SALT'}
    for a,b in zip(z['gross_additive_preview'],p['gross_additive_preview']):
        assert Decimal(a['after_source_display'].removesuffix(' gal'))<Decimal(b['after_source_display'].removesuffix(' gal'))
        assert all(Decimal(x)>0 for x in b['delta_from_before_source_display_range'])
    assert p['unaffected']['source_invariants_preserved']
    assert p['unaffected']['base_reference']==z['unaffected']['base_reference']
    assert p['after_source_tables']['blend']==z['after_source_tables']['blend']
    assert any(x['Name']=='C03 Dry' for x in p['after_source_tables']['blend'])
    for label in ('calc','lab','raw_lab','display','density','operator_additives'):
        assert p['unaffected']['base_reference'][label]==z['unaffected']['base_reference'][label]
    assert p['unaffected']['raw_lab_findings_sha256_before']==p['unaffected']['raw_lab_findings_sha256_after']


def test_same_fixture_value_and_inferred_nominal_no_false_exact(cases):
    r=scenario(cases['main'],5);p=selected(r)
    expected=cases['main']['expected']['fixture_expected']['Main']
    assert p['after_source_tables']=={k:expected[k] for k in ('blend','additives')}
    assert all(Decimal(g['delta_from_before_source_display_range'][0])<=0<=Decimal(g['delta_from_before_source_display_range'][1]) for g in p['gross_additive_preview'])
    nominal=float(p['original_inferred_dead_volume']['nominal_bbl'])
    same=selected(scenario(cases['main'],nominal))
    assert same['new_preparation_water_note_display_bbl']==same['word_reported_preparation_water']['raw']
    assert all(Decimal(g['delta_from_before_nominal_display'])==0 for g in same['gross_additive_preview'])
    assert same['original_inferred_dead_volume']['compatible_display_dv_interval_bbl']['lower']!=same['original_inferred_dead_volume']['compatible_display_dv_interval_bbl']['upper']


def test_selected_lead_and_tail_are_isolated(cases):
    a=scenario(cases['two'],10,'Lead');b=scenario(cases['two'],0,'Lead')
    p=selected(a);q=selected(b)
    assert p['tank_from_word']=='Mud Reserve Tanks'
    tail=next(w for w in a['c03']['water_findings'] if w['slurry']=='Tail')
    assert tail['Mixing Tank Selected in Word']=='Batch Mixer Tanks'
    assert tail==next(w for w in b['c03']['water_findings'] if w['slurry']=='Tail')
    assert p['unaffected']['unselected_slurry_references']==q['unaffected']['unselected_slurry_references']
    assert p['original_note_locator']!=tail['locator']
    assert a['c03']==b['c03']
    reverse=selected(scenario(cases['two'],0,'Tail'))
    assert reverse['tank_from_word']=='Batch Mixer Tanks' and 'Lead' in reverse['unaffected']['unselected_slurry_references']


def test_zero_dose_gross_unchanged(cases):
    p=selected(scenario(cases['zero'],10))
    assert len(p['gross_additive_preview'])==3
    assert all(g['display_dependency']=='UNCHANGED_OVER_BEFORE_ENCLOSURE' and Decimal(g['after_source_display'].removesuffix(' gal'))==0 for g in p['gross_additive_preview'])


@pytest.mark.parametrize('target,printed',[(35.049,'35.0'),(35.05,'35.1'),(35.051,'35.1')])
def test_original_source_half_up_note_boundaries(cases,target,printed):
    pure=34.848484848484844
    p=selected(scenario(cases['neat'],target-pure))
    assert p['new_preparation_water_full_precision_bbl']==target
    assert p['new_preparation_water_note_display_bbl']==printed


@pytest.mark.parametrize('value',[-1,'0','N/A',None,True,float('nan'),float('inf'),float('-inf')])
def test_invalid_edit_values_fail_closed(cases,value):
    with pytest.raises(ValueError):cp.preview(cases['main']['path'],cases['main']['op'],{'slurry':'Main','corrected_dead_volume_bbl':value})


@pytest.mark.parametrize('edit',[{},[{'slurry':'Main','corrected_dead_volume_bbl':1}]*2,{'slurry':'Main','corrected_dead_volume_bbl':1,'tank':'Guess'},{'slurry':'','corrected_dead_volume_bbl':0}])
def test_invalid_or_duplicate_edit_shape(cases,edit):
    with pytest.raises(ValueError):cp.preview(cases['main']['path'],cases['main']['op'],edit)


@pytest.mark.parametrize('fluid',['Ghost','Spacer','Scavenger'])
def test_unsupported_or_nonexistent_roles(cases,fluid):
    r=scenario(cases['main'],0,fluid)
    assert r['status'] in ('NOT_VERIFIABLE','UNSUPPORTED') and r['selected_dead_volume_preview'] is None
    assert r['c03']['status']=='PARTIAL_FINDINGS_ONLY'


def test_ct_and_duplicate_active_identity_rejected(cases):
    op=deepcopy(cases['main']['op']);op['job_type']='CMT PLUG WITH CT'
    r=cp.preview(cases['main']['path'],op,{'slurry':'Main','corrected_dead_volume_bbl':0})
    assert r['status']=='UNSUPPORTED' and r['selected_dead_volume_preview'] is None
    op=deepcopy(cases['main']['op']);op['active_fluids']=['Main','Main']
    with pytest.raises(ValueError):cp.preview(cases['main']['path'],op,{'slurry':'Main','corrected_dead_volume_bbl':0})


@pytest.mark.parametrize('kind',['missing','duplicate','wrong_tank','wrong_note'])
def test_unproved_note_never_applies_edit(cases,tmp_path,kind):
    d=Document(cases['main']['path']);n=next(p for p in d.paragraphs if 'Mix above Additives in' in p.text)
    if kind=='missing':n._element.getparent().remove(n._element)
    elif kind=='duplicate':n._element.addnext(deepcopy(n._element))
    elif kind=='wrong_tank':n.text=n.text.replace('Mud Reserve Tanks','Batch Mixer Tanks')
    else:n.text=n.text.replace('Mix above Additives','Unproved wording')
    path=tmp_path/'negative.docx';d.save(path);original=path.read_bytes()
    r=cp.preview(path,cases['main']['op'],{'slurry':'Main','corrected_dead_volume_bbl':10})
    assert r['status']=='NOT_VERIFIABLE' and r['selected_dead_volume_preview'] is None
    assert r['c03']['water_findings'][0]['status']=='NOT_VERIFIABLE'
    assert path.read_bytes()==original


def test_binding_source_operator_document_drift(cases):
    baseline=scenario(cases['main'])['c03'];sha=baseline['source_document_sha256']
    op=deepcopy(cases['main']['op']);op['slurries']['Main']['client_volume_bbl']=100
    with pytest.raises(RuntimeError):cp.bind(baseline,op,sha)
    with pytest.raises(RuntimeError):cp.bind(baseline,cases['main']['op'],'0'*64)
    changed=deepcopy(baseline);changed['source_sha']='0'*40
    with pytest.raises(RuntimeError):cp.bind(changed,cases['main']['op'],sha)


def test_parent_pin_guard_without_mutating_parents(monkeypatch):
    bad=dict(rt.PINS);bad['c03/c03_water.py']='0'*64
    monkeypatch.setattr(rt,'PINS',bad)
    with pytest.raises(RuntimeError):rt.verify_parents()


def test_real_input_change_during_call_fails_closed(cases,tmp_path,monkeypatch):
    path=tmp_path/'drift.docx';path.write_bytes(cases['main']['path'].read_bytes())
    def changed(payload):
        path.write_bytes(path.read_bytes()+b'deliberate test mutation')
        return {'status':'NOT_VERIFIABLE'}
    monkeypatch.setattr(cp,'call',changed)
    with pytest.raises(RuntimeError,match='Input SHA drift'):cp.preview(path,cases['main']['op'],{'slurry':'Main','corrected_dead_volume_bbl':0})


def test_cli_determinism_hashes_original_bytes_and_duplicate_json(cases,tmp_path):
    op=tmp_path/'operator.json';op.write_text(json.dumps(cases['main']['op']))
    edit=tmp_path/'edit.json';edit.write_text('{"slurry":"Main","corrected_dead_volume_bbl":10}')
    original=cases['main']['path'].read_bytes()
    cmd=[sys.executable,'-B',str(rt.HERE/'c04_preview.py'),str(op),str(cases['main']['path']),str(edit)]
    a=subprocess.run(cmd,capture_output=True,text=True);b=subprocess.run(cmd,capture_output=True,text=True)
    assert a.returncode==b.returncode==0 and a.stdout==b.stdout,(a.stderr,b.stderr)
    r=json.loads(a.stdout);assert r['input_file_sha256']['docx']==hashlib.sha256(original).hexdigest()
    assert cases['main']['path'].read_bytes()==original
    (rt.HERE/'output/cli-main10.json').write_text(a.stdout)
    edit.write_text('{"slurry":"Main","slurry":"Tail","corrected_dead_volume_bbl":10}')
    rejected=subprocess.run(cmd,capture_output=True,text=True)
    assert rejected.returncode==2 and json.loads(rejected.stdout)['status']=='INPUT_REJECTED'


def test_symlink_path_network_write_boundaries(cases,tmp_path):
    escape=tmp_path/'escape.docx';escape.symlink_to(rt.ROOT/'c03/fixtures/mixed5.docx')
    with pytest.raises(ValueError):cp.preview(escape,cases['main']['op'],{'slurry':'Main','corrected_dead_volume_bbl':0})
    with pytest.raises(ValueError):rt.local_path(rt.HERE/'../c03/fixtures/mixed5.docx')
    code="""from pathlib import Path
import sys,socket
sys.path.insert(0,str(Path.cwd().parent/'c03'))
import c03_source
c03_source.HERE=Path.cwd();c03_source.install_audit()
for action in (lambda: Path('/tmp/c04-forbidden-write').write_text('x'),lambda: socket.getaddrinfo('example.com',443)):
    try:action()
    except RuntimeError:pass
    else:raise AssertionError('boundary failed')
print('BLOCKED')
"""
    p=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,cwd=rt.HERE)
    assert p.returncode==0 and 'BLOCKED' in p.stdout,p.stderr
