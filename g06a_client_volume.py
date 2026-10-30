"""Read-only, source-backed client-volume reference impact; never a Word repair."""
from copy import deepcopy
import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from docx import Document
from io import BytesIO
from c10_corrections import ROOT, Refusal, digest, identities, private_path, target, verify_json_files
from checker_parser import safe_input
from c02_engine import read_json

SCHEMA = 'g06a.1'


def inspect_reference(docx, operator, slurry):
    return call({'docx':str(docx),'operator':operator,'slurry':slurry})


def volume_impact(docx, operator, edit):
    return call({'docx':str(docx),'operator':operator,'edit':edit})


def same_claim(a, b):
    return all(a[k]==b[k] for k in ('locator','section','slurry','field','raw_reported_text','source_document_sha256'))


def source_row(name, old, new, old_display, new_display, unit, function):
    return {'dependency':name,'classification':'SOURCE_UNCHANGED' if old==new else 'SOURCE_CHANGED',
        'old_full_precision':old,'new_full_precision':new,'old_source_display':old_display,
        'new_source_display':new_display,'source_display_changed':None if old_display is None or new_display is None else old_display!=new_display,
        'unit':unit,'source_function':function,'classification_scope':'SOURCE_REFERENCE_ONLY'}


def source_ledger(old, new, old_op, new_op):
    import phase_10_procedure as report
    def displays(s):
        return report._word_program_quantities({'solution':s['calc']['field_solution_bbl'],
            'mix_water_bbl':s['calc']['field_water_bbl'],'total_sacks':s['calc']['field_sacks'],
            'yield_cuft_sk':s['calc']['yield_ft3_per_sk']})
    a,b=displays(old),displays(new)
    rows=[source_row('client_requested_volume',old_op['client_volume_bbl'],new_op['client_volume_bbl'],
        None,None,'bbl','Independent operator input; no proven C02 Word-volume mapping')]
    for name,key,display,unit in [('sacks','field_sacks','total_sacks','sks'),
        ('pure_mix_water','field_water_bbl','mix_water_bbl','bbl'),
        ('solution_not_pure_water','field_solution_bbl','solution','bbl'),
        ('yield','yield_ft3_per_sk','yield_cuft_sk','cuft/sk')]:
        rows.append(source_row(name,old['calc'][key],new['calc'][key],a[display],b[display],unit,
            'phase_5_cement.calculate_base_results / engineering_tools.calculate_slurry_from_components / phase_10_procedure._word_program_quantities'))
    def field_display(s):
        # C02's zero-DV base bookkeeping is not an independent actual tank allowance.
        return {'blend_additives':s['blend'][1:], 'additives':[{k:v for k,v in row.items() if k!='lbs or gal (with dead Vol.)'} for row in s['additives']]}
    def field_values(s):
        return {key:s['calc'][key] for key in ('field_powders','field_liquids','salt_field_lb')}
    rows.append(source_row('base_field_materials',field_values(old),field_values(new),field_display(old),field_display(new),
        'Original source row units','engineering_tools.calculate_slurry_from_components / phase_5_cement.build_cement_tables'))
    rows.append(source_row('calculated_600ml_recipe',old['raw_lab'],new['raw_lab'],old['lab'],new['lab'],
        'g/600 mL','phase_7_lab.build_lab_df_from_phase5 / phase_10_procedure.separate_lab_tables'))
    rows.append(source_row('density',old['density'],new['density'],old['density'],new['density'],
        'pcf','Original independent density; unchanged formulation'))
    return rows


def unresolved_ledger():
    return [
        {'dependency':'total_preparation_water_and_gross_with_dead_volume','classification':'NOT_VERIFIABLE',
         'reason':'No explicit independent Dead Volume in this C02 input contract. Word rounded total is not used to infer/carry an allowance. No total/gross-with-DV projection is claimed.'},
        {'dependency':'mixing_tank_and_preparation_NOTE','classification':'MANUAL_REVIEW_REQUIRED',
         'reason':'Independent water/DV/tank and complete source NOTE context are not provided. C03 inference and C04 proposal are not invoked.'},
        {'dependency':'fluid_duration_and_cumulative_time','classification':'NOT_VERIFIABLE',
         'reason':'C05 requires independent active-fluid volumes/densities/rates and applicability; missing rates are not invented.'},
        {'dependency':'Executive_Summary_Procedure_and_ordered_NOTES','classification':'MANUAL_REVIEW_REQUIRED',
         'reason':'C08/C09 require complete independent program/placement/preparation context; no wording or numbering is reconstructed.'},
        {'dependency':'geometry_and_excess','classification':'NOT_VERIFIABLE',
         'reason':'No independent geometry supplied; geometry is informational and never replaces client volume or causes an automatic discrepancy.'},
        {'dependency':'measured_Lab_observations','classification':'NOT_VERIFIABLE',
         'reason':'Not inputs/outputs of this C02 reference edit. No measurements, review, signatures or refreshed observations are synthesized.'},
        {'dependency':'CT_stages_and_Spacer_solver_cascades','classification':'NOT_VERIFIABLE',
         'reason':'Unsupported scope, not an ordinary-slurry projection or an added mandatory fluid.'}]


def execute(docx, operator, slurry=None, edit=None, json_inputs=None):
    import c02_compare as cc
    verify_json_files(json_inputs,operator,edit)
    path=private_path(docx); original=safe_input(path); operator_sha=digest(operator); pins=identities()
    if edit is not None:
        if slurry is not None or type(edit) is not dict or set(edit)!={'schema','bindings','slurry','client_volume_bbl'} or edit['schema']!=SCHEMA:
            raise Refusal('EXACTLY_ONE_BOUND_CLIENT_VOLUME_EDIT_REQUIRED')
        slurry=edit['slurry']; value=edit['client_volume_bbl']
        if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
            raise Refusal('FINITE_POSITIVE_CLIENT_VOLUME_REQUIRED')
    if type(slurry) is not str or not slurry: raise Refusal('EXPLICIT_EXACT_SLURRY_REQUIRED')
    before=cc.compare_document(path,operator)
    if before['status']!='PARTIAL_FINDINGS_ONLY' or digest(operator)!=operator_sha:
        raise Refusal('SOURCE_REFERENCE_OR_DOCUMENT_NOT_VERIFIABLE')
    reference=before['reference']
    if reference['operator_input_sha256']!=operator_sha or before['source_document_sha256']!=sha256(original).hexdigest():
        raise Refusal('SOURCE_REFERENCE_DOCUMENT_DRIFT')
    import materials_db as db
    import project_state as state_source
    if operator['job_type'] in (db.CT_JOB,'CMT SQUEEZE') or slurry not in db.PLACEMENT_SLURRIES:
        raise Refusal('UNSUPPORTED_JOB_OR_NONORDINARY_ROLE')
    if slurry not in operator['active_fluids'] or slurry not in reference['slurries']:
        raise Refusal('MISSING_OR_INACTIVE_SLURRY')
    # Source sensitivity probes prove selected-role eligibility without guessing actual Mud Type.
    eligibility=[slurry in state_source.available_fluid_types({'job_type':operator['job_type'],'mud_type':mud}) for mud in ('WBM','OBM')]
    if not all(eligibility) or reference['slurries'][slurry]['program_section']!='cement':
        raise Refusal('SELECTED_ROLE_APPLICABILITY_UNPROVED')
    document=Document(BytesIO(original)); proof=[]
    for field in ('yield','sacks'):
        candidates=[f for f in before['findings'] if f['slurry']==slurry and f['field']==field]
        if (len(candidates)!=1 or candidates[0]['mapping_state']!='IDENTIFIED'
                or candidates[0]['association_state']!='EXPLICIT' or candidates[0]['section']!='cement'):
            raise Refusal('UNIQUE_PRINTED_SLURRY_IDENTITY_NOT_VERIFIABLE')
        target(document,candidates[0]);proof.append(candidates[0]['locator'])
    bindings=dict(pins,original_document_sha256=sha256(original).hexdigest(),original_operator_sha256=operator_sha,
        original_reference_sha256=digest(reference['slurries']),selected_slurry=slurry,parser_schema=before['parser_schema'])
    result={'schema':SCHEMA,'status':'PARTIAL_FINDINGS_ONLY','operation':'REFERENCE_INSPECTION_ONLY',
        'bindings':bindings,'slurry_identity_proof':proof,'original_comparison':before,
        'docx_written':False,'word_modified':False,
        'eligibility_proof':{'function':'project_state.available_fluid_types','calls':2,
            'selected_role_available_for_both_source_mud_types':eligibility,
            'actual_mud_type_and_unselected_fluid_eligibility':'NOT_VERIFIED'},
        'unresolved_dependencies':unresolved_ledger()}
    if edit is not None:
        if edit['bindings']!=bindings: raise Refusal('STALE_OR_FORGED_REFERENCE_SELECTION_BINDINGS')
        edited=deepcopy(operator);edited['slurries'][slurry]['client_volume_bbl']=value
        edited_sha=digest(edited)
        after=cc.compare_document(path,edited)
        if after['status']!='PARTIAL_FINDINGS_ONLY' or digest(edited)!=edited_sha or after['reference']['operator_input_sha256']!=edited_sha:
            raise Refusal('EDITED_SOURCE_REFERENCE_NOT_VERIFIABLE')
        expected=deepcopy(edited);expected['slurries'][slurry]['client_volume_bbl']=operator['slurries'][slurry]['client_volume_bbl']
        if expected!=operator: raise Refusal('UNSELECTED_OPERATOR_INPUT_CHANGED')
        a=reference['slurries'][slurry]; b=after['reference']['slurries'][slurry]
        if any(a[k]!=b[k] for k in ('density','base_cement','operator_additives','raw_lab','lab')) or a['calc']['yield_ft3_per_sk']!=b['calc']['yield_ft3_per_sk']:
            raise Refusal('STOP_ENGINEERING_REVIEW_UNEXPECTED_RECIPE_INVARIANT_CHANGE')
        others={f:digest(s) for f,s in reference['slurries'].items() if f!=slurry}
        if others!={f:digest(s) for f,s in after['reference']['slurries'].items() if f!=slurry}:
            raise Refusal('UNSELECTED_SLURRY_SOURCE_CHANGED')
        old=before['findings'];new=after['findings']
        if len(old)!=len(new): raise Refusal('ORIGINAL_CLAIM_LOSS')
        impacts=[]
        for x,y in zip(old,new):
            if not same_claim(x,y): raise Refusal('WORD_OR_LOCATOR_CHANGED')
            identified=x['mapping_state']=='IDENTIFIED' and y['mapping_state']=='IDENTIFIED'
            changed=any(x[k]!=y[k] for k in ('source_rounded_expected','full_precision_expected'))
            classification=('SOURCE_CHANGED' if changed else 'SOURCE_UNCHANGED') if identified else 'NOT_VERIFIABLE'
            if x['slurry']!=slurry and x!=y: raise Refusal('UNSELECTED_FINDING_CHANGED')
            impacts.append({'locator':x['locator'],'section':x['section'],'slurry':x['slurry'],'field':x['field'],
                'original_raw_claim':x['raw_reported_text'],'classification':classification,
                'old_source_value':x['full_precision_expected'],'new_source_value':y['full_precision_expected'],
                'old_source_display':x['source_rounded_expected'],'new_source_display':y['source_rounded_expected'],
                'source_display_changed':None if not identified or x['source_rounded_expected'] is None or y['source_rounded_expected'] is None else x['source_rounded_expected']!=y['source_rounded_expected'],
                'old_comparison':x['result'],'new_comparison':y['result'],'old_delta':x['delta'],'new_delta':y['delta'],
                'unit':x['unit'],'tolerance':x['tolerance'],'source_function':x['source_function'],
                'word_modified':False,'classification_scope':'SOURCE_REFERENCE_ONLY',
                'reason':('Independent source expectation changed; original Word claim retained' if changed else 'Source expectation and original Word claim unchanged') if identified else y['reason']})
        result.update(operation='CLIENT_VOLUME_REFERENCE_IMPACT',edited_operator_reference=edited,
            edited_operator_sha256=edited_sha,edit_request_sha256=digest(edit),
            edited_reference_sha256=digest(after['reference']['slurries']),edited_comparison=after,
            source_dependency_ledger=source_ledger(a,b,operator['slurries'][slurry],edited['slurries'][slurry]),
            word_claim_impacts=impacts,unselected_slurry_source_hashes=others,
            invariants={'yield_and_calculated_600ml_recipe':True,'other_slurries':True,'measured_results_refreshed':False},
            reference_dead_volume_policy='C02_INTERNAL_ZERO_BASE_BOOKKEEPING_ONLY; no actual DV inferred or carried, no operational total/gross-with-DV claim')
    if identities()!=pins or safe_input(private_path(path))!=original or digest(operator)!=operator_sha:
        raise Refusal('ORIGINAL_OR_SOURCE_CHANGED')
    verify_json_files(json_inputs,operator,edit)
    result.update(original_document_sha256=bindings['original_document_sha256'],unchanged_document_sha256=sha256(original).hexdigest())
    return result


def call(payload):
    environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp'),
        XDG_CACHE_HOME=str(ROOT/'cache'),XDG_CONFIG_HOME=str(ROOT/'cache/config'),MPLCONFIGDIR=str(ROOT/'cache/mpl'))
    p=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--worker'],input=json.dumps(payload,allow_nan=False),
        capture_output=True,text=True,cwd=ROOT,env=environment,timeout=120)
    if p.returncode not in (0,2): raise Refusal('ISOLATED_REFERENCE_PROCESS_FAILED')
    result=read_json(p.stdout)
    if (p.returncode==0)!=(result.get('status')=='PARTIAL_FINDINGS_ONLY'): raise Refusal('REFERENCE_PROCESS_STATUS_MISMATCH')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--worker',action='store_true')
    parser.add_argument('operator_json',nargs='?');parser.add_argument('docx',nargs='?')
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--slurry');mode.add_argument('--edit')
    args=parser.parse_args()
    try:
        if args.worker:
            from engineering_source import install_audit
            install_audit()
            import c02_compare as cc
            from c02_engine import reference
            cc.engine=reference  # Accepted C03/C10 pure-source subprocess bridge; no engine/state patch.
            result=execute(**read_json(sys.stdin.read()))
        else:
            if not args.docx or not args.operator_json or (args.slurry is None and args.edit is None): raise Refusal('EXPLICIT_REFERENCE_AND_SELECTION_REQUIRED')
            files=[Path(args.operator_json).absolute()]+([Path(args.edit).absolute()] if args.edit else [])
            for p in files:
                if p.resolve()!=p or not p.is_file() or not p.is_relative_to(ROOT/'tmp'):
                    raise Refusal('PRIVATE_JSON_PATH_REQUIRED')
            raw=[p.read_bytes() for p in files]
            operator=read_json(raw[0]);edit=read_json(raw[1]) if args.edit else None
            entries=[{'path':str(p),'sha256':sha256(v).hexdigest()} for p,v in zip(files,raw)]
            verify_json_files(entries,operator,edit)
            result=call({'docx':args.docx,'operator':operator,'slurry':args.slurry,'edit':edit,'json_inputs':entries})
            result['input_file_sha256']={str(i):entry['sha256'] for i,entry in enumerate(entries)}
    except (ValueError,TypeError,KeyError,IndexError,OSError,RuntimeError,ArithmeticError,zipfile.BadZipFile) as error:
        result={'schema':SCHEMA,'status':'INPUT_REJECTED','docx_written':False,'word_modified':False,
            'reason':str(error) if isinstance(error,Refusal) else 'SOURCE_REFERENCE_OR_INPUT_NOT_VERIFIABLE'}
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if result['status']=='PARTIAL_FINDINGS_ONLY' else 2


if __name__=='__main__': raise SystemExit(main())
