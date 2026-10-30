"""Selected ordinary-slurry scenario preview. Never writes/approves a DOCX."""
import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import sys

from c04_runtime import HERE,ROOT,PIN,PINS,call,local_path,verify_parents


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def validate_edit(edit):
    if type(edit) is not dict or set(edit)!={'slurry','corrected_dead_volume_bbl'}:
        raise ValueError('Exactly one edit object with slurry and corrected_dead_volume_bbl required')
    if type(edit['slurry']) is not str or not edit['slurry']:
        raise ValueError('Explicit exact slurry identity required')
    value=edit['corrected_dead_volume_bbl']
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:
        raise ValueError('Proposed Dead Volume must be a finite nonnegative JSON number')


def bind(baseline,operator,document_sha):
    ref=baseline['c02']['reference']
    if baseline['source_sha']!=PIN or ref['source_sha']!=PIN:
        raise RuntimeError('Source SHA drift')
    if baseline['source_document_sha256']!=document_sha or baseline['c02']['source_document_sha256']!=document_sha:
        raise RuntimeError('Document SHA drift')
    if ref['operator_input_sha256']!=digest(operator):raise RuntimeError('Operator SHA drift')
    if baseline['status']!='PARTIAL_FINDINGS_ONLY':raise RuntimeError('Unexpected C03 contract')


def compose(baseline,operator,edit,document_sha):
    """Internal child-only composition. No cached-baseline product API."""
    validate_edit(edit);bind(baseline,operator,document_sha)
    import c03_source as cs
    import materials_db as db
    import engineering_tools as eng
    import phase_10_procedure as report
    if cs.HERE!=HERE:raise RuntimeError('C04 source process not isolated')
    result={'schema':'c04.1','status':'PARTIAL_FINDINGS_ONLY','c03':baseline,
        'selected_dead_volume_preview':None,'source_sha':PIN,'accepted_parent_sha256':PINS,
        'hashes':{'original_document_sha256':document_sha,'new_document_sha256':document_sha,
            'original_operator_sha256':digest(operator),'new_operator_sha256':digest(operator),
            'edit_request_sha256':digest(edit),'original_source_sha':PIN,'new_source_sha':PIN,
            'scenario_input_sha256':digest({'operator':operator,'document_sha256':document_sha,'edit':edit,'source_sha':PIN,'accepted_c03':PINS})},
        'docx_written':False,'limitations':['Read-only proposed scenario, not a measured tank heel or overall PASS',
            'No DOCX/Procedure rewrite; remaining C03 findings/statuses stay unchanged']}
    fluid=edit['slurry']
    if operator['job_type']==db.CT_JOB or fluid not in db.PLACEMENT_SLURRIES:
        result.update(status='UNSUPPORTED',reason='CT/nonordinary cement role is outside this slice');return result
    if fluid not in operator['active_fluids'] or fluid not in baseline['c02']['reference']['slurries']:
        result.update(status='NOT_VERIFIABLE',reason='Selected slurry is not a uniquely active referenced formulation');return result
    matches=[w for w in baseline['water_findings'] if w['slurry']==fluid]
    if len(matches)!=1 or matches[0]['status']!='INFERRED_AT_DISPLAY_PRECISION':
        result.update(status='NOT_VERIFIABLE',reason='Selected C03 water/tank/NOTE proof is missing or ambiguous');return result
    water=matches[0];before=baseline['source_projections']['projections'][fluid]
    s=baseline['c02']['reference']['slurries'][fluid]
    proposed=edit['corrected_dead_volume_bbl']
    try:
        source=cs.run({'action':'gross','operator':operator,'allowances':{fluid:{'proposed':proposed}}})
    except ValueError as error:
        if 'invariance failed' in str(error):
            result.update(status='STOP_ENGINEERING_REVIEW',reason=str(error));return result
        raise
    if source['source_sha']!=PIN or not source['base_invariants_preserved']:
        raise RuntimeError('Source/protected base projection mismatch')
    after=source['projections'][fluid]['proposed']
    # Authorized operational-water addition, identical to source Phase V.
    pure=s['calc']['field_water_bbl'];total=pure+proposed
    if not math.isfinite(total):raise ValueError('Source operational total is not representable')
    display=f'{eng.round_half_up(total,1):.1f}'
    source_word_projection=report._word_program_quantities({'mix_water_bbl':pure,'total_water_bbl':total})
    findings=[]
    for row in after['additives']:
        original={}
        for label,projection in before.items():
            candidates=[r for r in projection['additives'] if (r['Item'],r['Name'],r['Material Type'])==(row['Item'],row['Name'],row['Material Type'])]
            if len(candidates)!=1:raise RuntimeError('Nonunique source row correspondence')
            original[label]=candidates[0]['lbs or gal (with dead Vol.)']
        unit='gal' if row['lbs or gal (with dead Vol.)'].endswith(' gal') else 'lb'
        def numeric(text):return Decimal(text.removesuffix(' gal'))
        values=[numeric(t) for t in original.values()];after_value=numeric(row['lbs or gal (with dead Vol.)'])
        located=[g for g in baseline['gross_additive_findings'] if g['slurry']==fluid and g['material']==row['Name'] and g['material_type']==row['Material Type']]
        unique=len(located)==1 and located[0]['status']!='NOT_VERIFIABLE'
        findings.append({'material':row['Name'],'material_type':row['Material Type'],'source_item':row['Item'],'unit':unit,
            'before_qualification':'INFERRED_NONUNIQUE_AT_WORD_DISPLAY_PRECISION',
            'before_source_displays':original,'before_source_display_range':[str(min(values)),str(max(values))],
            'after_qualification':'SOURCE_CALCULATED_FROM_EXPLICIT_OPERATOR_PROPOSAL',
            'after_source_display':row['lbs or gal (with dead Vol.)'],
            'delta_from_before_source_display_range':[str(after_value-max(values)),str(after_value-min(values))],
            'delta_from_before_nominal_display':str(after_value-numeric(original['nominal'])) if 'nominal' in original else None,
            'display_dependency':'UNCHANGED_OVER_BEFORE_ENCLOSURE' if all(x==after_value for x in values) else 'SCENARIO_DEPENDENT',
            'word_mapping':'PROVED' if unique else 'REQUIRES_MANUAL_VERIFICATION',
            'word_records':located,'source_function':'phase_5_cement.build_cement_tables'})
    locations=[{'section':water['section'],'locator':water['locator'],'note':water['note'],'kind':'Preparation NOTE','status':'REQUIRES_MANUAL_VERIFICATION'}]
    locations += [{'section':g['section'],'locator':g['locator'],'kind':'Gross additive quantity','material':g['material'],'status':'POTENTIAL_CORRECTION_LOCATION'} for g in baseline['gross_additive_findings'] if g['slurry']==fluid and g['status']!='NOT_VERIFIABLE']
    locations += [{'section':'procedure','locator':p['record']['locator'],'kind':'Potential Procedure water dependency','status':'REQUIRES_MANUAL_VERIFICATION'} for p in baseline['procedure_water_evidence'] if p['fluid'] in (None,fluid)]
    raw_lab=[f for f in baseline['c02']['findings'] if f['section']=='lab']
    result['selected_dead_volume_preview']={'slurry':fluid,'tank_from_word':water['Mixing Tank Selected in Word'],
        'original_note_locator':water['locator'],'original_note_number':water['note'],'original_note_raw_text':water['raw_text'],
        'word_reported_preparation_water':water['Total Preparation Water Reported in Word'],
        'original_inferred_dead_volume':water['Dead Volume Included by Engineer'],
        'proposed_dead_volume_bbl':proposed,'proposal_qualification':'Explicit operator scenario at original App numeric precision; not inferred/measured',
        'pure_mix_water_full_precision_bbl':pure,'new_preparation_water_full_precision_bbl':total,
        'new_preparation_water_note_display_bbl':display,'source_word_numeric_projection':source_word_projection,
        'delta_water_from_word_display_bbl':str(Decimal(str(total))-Decimal(water['Total Preparation Water Reported in Word']['raw'])),
        'delta_dv_from_inferred_nominal_bbl':str(Decimal(str(proposed))-Decimal(water['Dead Volume Included by Engineer']['nominal_bbl'])),
        'gross_additive_preview':findings,'after_source_tables':after,
        'unaffected':{'source_invariants_preserved':source['base_invariants_preserved'],'base_reference':s,
            'source_after_blend':after['blend'],'raw_lab_findings_sha256_before':digest(raw_lab),'raw_lab_findings_sha256_after':digest(raw_lab),
            'unselected_slurry_references':{f:r for f,r in baseline['c02']['reference']['slurries'].items() if f!=fluid}},
        'word_locations_potentially_requiring_correction':locations,
        'mixing_note_preview':{'status':'REQUIRES_MANUAL_VERIFICATION','reason':'Full numbered NOTE builder requires unrelated laboratory observation inputs; none invented. No replacement sentence emitted.'}}
    return result


def preview(docx,operator,edit):
    verify_parents();validate_edit(edit);path=local_path(docx)
    document_sha=hashlib.sha256(path.read_bytes()).hexdigest();op_sha=digest(operator);edit_sha=digest(edit)
    result=call({'action':'preview','docx':str(path),'operator':operator,'edit':edit})
    if hashlib.sha256(path.read_bytes()).hexdigest()!=document_sha or digest(operator)!=op_sha or digest(edit)!=edit_sha:
        raise RuntimeError('Input SHA drift during scenario')
    if 'c03' in result:bind(result['c03'],operator,document_sha)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operator_json');parser.add_argument('docx');parser.add_argument('edit_json');args=parser.parse_args()
    try:
        verify_parents()
        sys.path.insert(0,str(ROOT/'c02'))
        from c02_engine import read_json
        paths=[local_path(x) for x in (args.operator_json,args.docx,args.edit_json)]
        hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        result=preview(paths[1],read_json(paths[0].read_text()),read_json(paths[2].read_text()))
        if hashes!=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]:raise RuntimeError('CLI input SHA drift')
        result['input_file_sha256']={'operator':hashes[0],'docx':hashes[1],'edit':hashes[2]}
    except (ValueError,TypeError,OSError,ArithmeticError) as error:result={'status':'INPUT_REJECTED','reason':str(error),'selected_dead_volume_preview':None}
    except RuntimeError as error:result={'status':'INTEGRITY_REJECTED','reason':str(error),'selected_dead_volume_preview':None}
    print(json.dumps(result,allow_nan=False,indent=2));return 0 if result['status']=='PARTIAL_FINDINGS_ONLY' else 2


if __name__=='__main__':raise SystemExit(main())
