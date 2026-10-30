"""C02 partial findings: original engine vs conservatively mapped DOCX claims."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from checker_parser import parse_docx
from c02_engine import read_json, SOURCE_SHA


def engine(operator):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(HERE/'tmp'),
                       XDG_CACHE_HOME=str(HERE/'cache'), XDG_CONFIG_HOME=str(HERE/'cache/config'),
                       MPLCONFIGDIR=str(HERE/'cache/mpl'))
    process = subprocess.run([sys.executable, '-B', str(HERE/'c02_engine.py')], input=json.dumps(operator, allow_nan=False),
        capture_output=True, text=True, cwd=HERE, env=environment, timeout=60)
    if process.returncode:
        raise ValueError('Isolated source process failed: ' + process.stderr[-500:])
    result = read_json(process.stdout)
    if 'error' in result:
        raise ValueError(result['error'])
    return result


def number(raw, unit):
    text = raw.strip()
    token = text[:-len(unit)].strip() if unit and text.endswith(unit) else text
    if not token: return None, 'MISSING'
    if token in ('-', '–', '—'): return None, 'DASH'
    if token.casefold() in ('n/a', 'not applicable', 'not applicable.'): return None, 'NA_PRINTED'
    match = re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+))' + (r'\s*'+re.escape(unit) if unit else ''), text)
    if not match: return None, 'MALFORMED_OR_UNIT_UNPROVEN'
    value = Decimal(match[1])
    return value, 'ZERO' if value == 0 else 'NUMBER'


def assess(raw, unit, expected, tolerance):
    value, state = number(raw, unit)
    if value is None:
        return {'result': 'NOT_VERIFIABLE', 'reported_state': state, 'delta': None, 'reason': 'Missing/non-numeric or unproven unit; never coerced to zero'}
    delta = value - Decimal(str(expected))
    return {'result': 'MATCH' if abs(delta) <= Decimal(str(tolerance)) else 'DISCREPANCY',
            'reported_state': state, 'delta': str(delta), 'reason': 'Partial comparison against automatic source reference only'}


def compare_document(path, operator):
    parsed = parse_docx(path)
    digest = parsed['source_document_sha256']
    if parsed['status'] == 'REJECTED':
        return {'status':'INPUT_REJECTED','source_document_sha256':digest,'findings':[], 'reason':parsed['error']}
    try:
        ref = engine(operator)
    except (ValueError, TypeError, subprocess.TimeoutExpired) as error:
        return {'status':'REFERENCE_INPUT_ERROR','source_document_sha256':digest,'findings':[], 'reason':str(error)}
    # All raw claims are retained, including unsupported fields and prose.
    findings = []
    for r in parsed['records']:
        findings.append({'source_document_sha256':digest,'parser_schema':parsed['schema_version'],
            'locator':r['locator'],'section':r['section'],'slurry':r['association'],
            'association_state':r['association_state'],'parser_value_state':r['value_state'],
            'mapping_state':'UNIMPLEMENTED',
            'raw_reported_text':r['raw_text'],'reported_state':r['value_state'],
            'result':'UNIMPLEMENTED','reason':'No proven C02 field mapping',
            'field':None,'unit':None,'source_sha':SOURCE_SHA,'source_function':None,
            'source_rounded_expected':None,'full_precision_expected':None,'delta':None,'tolerance':None})
    tables = defaultdict(list)
    for i,r in enumerate(parsed['records']):
        loc = r['locator']
        if loc.get('table') is not None:
            tables[(loc['body_block'],loc['table'],tuple(loc['table_path']))].append((i,r))
    mapped=[]
    for table in tables.values():
        rows=defaultdict(list)
        for i,r in table: rows[r['locator']['row']].append((i,r))
        for row in rows.values():
            # Split paragraphs or repeated physical columns are not a one-value cell.
            cells=defaultdict(list)
            for i,r in row: cells[r['locator']['column']].append((i,r))
            if any(len(v)!=1 for v in cells.values()):
                for i,r in row:findings[i].update(result='NOT_VERIFIABLE',mapping_state='AMBIGUOUS',reason='Multiple paragraphs per cell')
                continue
            ordered=[v[0] for _,v in sorted(cells.items())]
            texts=[r['raw_text'] for _,r in ordered]
            if not ordered:continue
            identities={r['association'] for _,r in ordered}
            fluid=ordered[0][1]['association']
            if len(identities)!=1 or fluid not in ref['slurries'] or any(r['association_state']!='EXPLICIT' for _,r in ordered):
                for i,r in row:findings[i].update(result='NOT_VERIFIABLE',mapping_state='AMBIGUOUS' if r['association_state']=='AMBIGUOUS' else 'NOT_VERIFIABLE',reason='Unproven/ambiguous or inactive slurry identity')
                continue
            s=ref['slurries'][fluid];anchor=ordered[0][1]['table_anchor'];section=ordered[0][1]['section']
            if anchor.startswith(fluid+' Cement Slurry ') and section!=s['program_section']:
                for i,r in row:findings[i].update(result='NOT_VERIFIABLE',reason='Printed program section does not match source report role')
                continue
            def bind(position,field,unit,expected,raw,tolerance,function,identity=''):
                i,r=ordered[position]
                # Duplicate logical claims in the same printed table family fail closed.
                mapped.append((i,(fluid,anchor,field,identity),unit,str(expected),raw,str(tolerance),function))
            if anchor==fluid+' Cement Slurry Data' and section in ('cement','preflush'):
                for position in range(1,len(texts)):
                    label=texts[position-1]
                    if label=='Yield':bind(position,'yield','cuft/sk',s['display']['yield_cuft_sk'],s['calc']['yield_ft3_per_sk'],'.001','phase_10_procedure._word_program_quantities / engineering_tools.calculate_slurry_from_components')
                    elif label=='Slurry Weight':bind(position,'density','pcf',s['density'],s['density'],'0','phase_10_procedure.build_master_context direct density_pcf (no extra rounding)')
            elif anchor==fluid+' Cement Slurry Blend Data' and section=='cement' and len(texts)==5:
                if texts[1].casefold()==s['base_cement'].casefold() and texts[2]=='Cement':
                    if ordered[3][1]['column_label']=='sks or lbs':
                        bind(3,'sacks','sks',s['blend'][0]['sks or lbs'].removesuffix(' sks'),s['calc']['field_sacks'],'1','phase_5_cement.build_cement_tables')
                else:
                    match=[r for r in s['blend'][1:] if r['Name']==texts[1] and r['Material Type']==texts[2]]
                    if len(match)==1 and ordered[3][1]['column_label']=='sks or lbs':
                        raw=s['raw_field'].get(texts[1].casefold())
                        if raw is not None:bind(3,'field_additive','lb',match[0]['sks or lbs'].removesuffix(' lb'),raw,0,'phase_5_cement.build_cement_tables',texts[1])
            elif anchor==fluid+' Cement Slurry Additives Data' and section=='cement' and len(texts)==7:
                match=[r for r in s['additives'] if r['Name']==texts[1] and r['Material Type']==texts[2]]
                if len(match)==1 and ordered[3][1]['column_label']=='lbs or gal':
                    raw=s['raw_field'].get(texts[1].casefold())
                    if raw is not None:
                        display=match[0]['lbs or gal'];unit='gal' if display.endswith(' gal') else ''
                        bind(3,'field_additive',unit,display.removesuffix(' gal'),raw,0,'phase_5_cement.build_cement_tables',texts[1])
            elif anchor=='Conventional' and section=='lab' and s['lab_report_supported'] and len(texts)==6 and ordered[5][1]['column_label']=='Mass (g/600 mL)':
                match=[r for r in s['lab'] if r['Code'].casefold()==texts[1].casefold() and r['Material Type']==texts[0] and r['Code']]
                raw=s['raw_lab'].get(texts[1].casefold())
                inputs=[r for r in s['operator_additives'] if r['Name'].casefold()==texts[1].casefold()]
                if len(match)==1 and raw is not None:
                    if texts[1].casefold() in (s['base_cement'].casefold(),'base water'):
                        tol='1'
                    elif len(inputs)==1:
                        additive=inputs[0]
                        dose=Decimal(str(additive['User Input']))
                        tol='.3' if additive['Physical State']=='Liquid' or Decimal('.01')<=dose<=1 else '1' if dose>1 else '0'
                    else:continue
                    bind(5,'lab_mass','',match[0]['Mass'],raw,tol,'phase_7_lab.build_lab_df_from_phase5 / phase_10_procedure.separate_lab_tables',texts[1].casefold())
    counts=Counter(key for _,key,*_ in mapped)
    for i,key,unit,expected,raw,tolerance,function in mapped:
        f=findings[i]
        f.update(field=key[2],unit='g/600 mL' if key[2]=='lab_mass' else unit or 'lb',
                 source_function=function,source_rounded_expected=expected,full_precision_expected=raw,tolerance=tolerance)
        if counts[key]!=1:
            f.update(result='NOT_VERIFIABLE',mapping_state='AMBIGUOUS',reason='Duplicate field/material/slurry association')
        else:
            f['mapping_state']='IDENTIFIED'
            f.update(assess(f['raw_reported_text'],unit,expected,tolerance))
    # No direct pure-water column is proven in this template. Solution and total
    # preparation notes remain unverified, even for a neat recipe.
    return {'comparison_schema':'c02.1','status':'PARTIAL_FINDINGS_ONLY','source_document_sha256':digest,'parser_schema':parsed['schema_version'],
            'reference':ref,'findings':findings,'summary':dict(Counter(f['result'] for f in findings)),
            'limitations':['Pure Mix Water has no proven printed field; Solution is different',
                           'Dead Volume inference and tanks not implemented; notes unverified',
                           'Job applicability, measured lab, inactive fluids and all other fields unverified']}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('operator_json');ap.add_argument('docx');args=ap.parse_args()
    try:
        p=Path(args.operator_json).resolve(strict=True)
        if not p.is_relative_to(ROOT):raise ValueError('Operator JSON outside scratch')
        result=compare_document(args.docx,read_json(p.read_text()))
    except (ValueError, OSError, TypeError) as error:
        result={'status':'REFERENCE_INPUT_ERROR','findings':[],'reason':str(error)}
    print(json.dumps(result,allow_nan=False,indent=2,sort_keys=True))
    return 2 if result['status']!='PARTIAL_FINDINGS_ONLY' else 0


if __name__=='__main__':raise SystemExit(main())
