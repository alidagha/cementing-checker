"""C07 partial independent-observation, original-fit and source-recipe comparisons."""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import re

from checker_parser import parse_docx, norm
from comparison_records import ROOT, tables, rows, regular_columns, finding, finish, assess, number
from engineering_source import request
from c02_engine import read_json


def fluid_table(parsed, anchor, fluid):
    found = [t for t in tables(parsed) if norm(t[0]['table_anchor']) == norm(anchor) and t[0]['section'] == 'lab'
        and all(r['association'] == fluid and r['association_state'] == 'EXPLICIT' for r in t)]
    return found[0] if len(found) == 1 else None


def expression_key(text):
    return re.sub(r'\s+', '', text)


def template_bindings(table, contract):
    """Prove source static labels/units/grid, then bind only known source expressions.

    Rows are identified by their static source labels, not rendered row/table indices.
    The candidate is never evaluated as Jinja. Unknown/duplicate/split structures fail closed.
    """
    if table is None:
        return {}
    source_rows = defaultdict(list); candidate_rows = defaultdict(list)
    for cell in contract:
        source_rows[cell['row']].append(cell)
    for record in table:
        candidate_rows[record['locator']['row']].append(record)
    if len(source_rows) != len(candidate_rows):
        return {}
    source_rows = [sorted(r, key=lambda c:c['column']) for r in source_rows.values()]
    candidate_rows = [sorted(r, key=lambda c:c['locator']['column']) for r in candidate_rows.values()]
    def shape(source, candidate):
        return [(c['column'],c['span']) for c in source] == [(c['locator']['column'],c['locator']['column_span']) for c in candidate]
    def pattern(text):
        parts = re.split(r'(\{\{.*?\}\})', ' '.join(text.split()))
        pieces=[]
        for i,p in enumerate(parts):
            if p.startswith('{{'):
                pieces.append('(.*?)');continue
            # A source placeholder may be empty. Preserve the unit literal while
            # allowing its boundary space to disappear under Word whitespace folding.
            left=i>0 and parts[i-1].startswith('{{') and p.startswith(' ')
            right=i+1<len(parts) and parts[i+1].startswith('{{') and p.endswith(' ')
            pieces.append(('\\s*' if left else '')+re.escape(p.strip() if left and right else p.lstrip() if left else p.rstrip() if right else p)+('\\s*' if right else ''))
        return '^'+''.join(pieces)+'$'
    def literal_weight(row):
        return sum(len(re.sub(r'\{\{.*?\}\}', '', c['text']).strip()) for c in row)
    used = set(); bindings = defaultdict(list)
    for source in sorted(source_rows, key=literal_weight, reverse=True):
        matches = []
        for index, candidate in enumerate(candidate_rows):
            if index in used or not shape(source,candidate):
                continue
            matched = [re.fullmatch(pattern(s['text']), ' '.join(c['raw_text'].split()), re.I|re.S) for s,c in zip(source,candidate)]
            if all(matched):matches.append((index,candidate,matched))
        if len(matches) != 1:
            return {}
        index, candidate, matched = matches[0]; used.add(index)
        for s,c,m in zip(source,candidate,matched):
            expressions = re.findall(r'\{\{(.*?)\}\}',s['text'])
            if len(expressions) == 1:
                bindings[expression_key(expressions[0])].append((c,m[1],s['text']))
    return dict(bindings)


def compare_document(docx, operator):
    parsed = parse_docx(docx)
    if parsed['status'] == 'REJECTED':
        return {'status':'INPUT_REJECTED','reason':parsed['error'],'findings':[]}
    try:
        source = request('lab',operator)
    except (ValueError, TypeError) as error:
        return {'status':'REFERENCE_INPUT_ERROR','reason':str(error),'findings':[],'records':parsed['records']}
    ref = source['reference']; findings = []
    for fluid,item in ref['fluids'].items():
        if item['role'] == 'WORD_MAPPING_NOT_VERIFIABLE':
            f=finding(None,'lab.applicability',None,None,'','materials_db.PHASE7_LAB_FLUIDS / pinned Word role',numeric=False)
            f.update(slurry=fluid,reason='No proven pinned-template Lab/stage mapping for this active role; no legacy alias')
            findings.append(f);continue
        bindings = {}
        for anchor,contract in ref['template_contracts'].items():
            bindings[anchor] = template_bindings(fluid_table(parsed,anchor,fluid),contract)
        prefix = 'standalone_spacer.lab.' if fluid=='Spacer' else 's.lab.'
        def one(anchor,expr):
            values=bindings.get(anchor,{}).get(expression_key(expr),[])
            return values[0] if len(values)==1 else None
        def matches(anchor,expr,expected):
            binding=one(anchor,expr)
            return binding is not None and expected is not None and assess(binding[1],'',expected,0)['result']=='MATCH'
        def bind(anchor,expr,field,expected,full,unit,function,numeric=True,permitted=True,kind='INDEPENDENT_MEASUREMENT'):
            binding=one(anchor,expr);record=binding[0] if binding else None
            available=expected not in (None,'','-') and permitted
            f=finding(dict(record,raw_text=binding[1]) if record is not None and available else None,
                field,expected,full,'',function,numeric=numeric,
                reason='STRUCTURE_PROVEN: unique explicit fluid, source expression, labels, units and grid' if binding else 'NOT_PROVEN: no unique source-compatible fluid/table/expression binding')
            if record is not None:
                f.update(locator=record['locator'],section=record['section'],raw_reported_text=record['raw_text'],
                    raw_reported_value=binding[1],source_template_pattern=binding[2])
                if not available:f['reported_state']=record['value_state']
            f.update(slurry=fluid,unit=unit,source_projection_expression=expr,
                source_template_sha256=ref['template_sha256'],reference_state='AVAILABLE' if available else 'UNAVAILABLE_OR_CONDITIONS_UNPROVEN',reference_kind=kind)
            if available and f['result'] in ('MATCH','DISCREPANCY'):
                f['reason']='Partial comparison at original source display; '+kind.lower().replace('_',' ')+'; no whole-program approval'
            if binding and not permitted:f['association_proof']='STRUCTURE_PROVEN; independent test-condition association NOT_PROVEN'
            if not available:f['reason']='Unselected/missing independent reference, unmeasured value, or test conditions not proved; never a match'
            findings.append(f);return f
        display=item.get('display',{});lab=item['lab']
        for key,unit in (('bhct','degF'),('bhst','degF'),('bhsp','psi')):
            if fluid!='Spacer':
                bind('Test Basic Data','s.lab.'+key,'lab.condition.'+key,display.get(key),ref['conditions'].get(key),unit,
                    'phase_10_procedure._word_quantity_context / independent source-context condition',kind='INDEPENDENT_SOURCE_CONTEXT')
        anchor='Spacer Rheology' if fluid=='Spacer' else 'Rheology Test'
        for dataset,data in item['rheology'].items():
            if not data.get('selected'):
                continue
            for key,unit in [(str(r),'Fann dial degrees') for r in (300,200,100,60,30,6,3)]+[
                ('pv_cp','cP'),('ty_lbf_100ft2','lbf/100ft2'),('gel_10_sec','Fann dial degrees'),('gel_10_min','Fann dial degrees')]:
                expr=prefix+f"rheology.get('{dataset}', {{}}).get('{key}', '-')"
                value=data.get('readings',{}).get(key) if key.isdigit() else data.get(key)
                expected=display.get('rheology',{}).get(dataset,{}).get(key)
                permitted=True
                if dataset!='surface_down':
                    b=one(anchor,expr)
                    temperatures=bindings[anchor].get(expression_key(prefix+'bhct'),[])
                    permitted=ref['temperature_valid'] and b is not None and any(
                        t[0]['locator']['column']==b[0]['locator']['column'] and assess(t[1],'',ref['conditions']['bhct'],0)['result']=='MATCH' for t in temperatures)
                    if item['role']=='ordinary_lab':
                        permitted=permitted and matches('Test Basic Data','s.lab.bhct',display.get('bhct'))
                bind(anchor,expr,'lab.rheology.'+dataset+'.'+key,expected,value,unit,
                    'engineering_tools.validate_lab_rheology / rheology.calculate_cemcade_bingham / phase_10_procedure._word_rheology',permitted=permitted,
                    kind='SOURCE_DERIVED_FROM_INDEPENDENT_MEASUREMENTS' if key in ('pv_cp','ty_lbf_100ft2') else 'INDEPENDENT_MEASUREMENT')
        if item['role']!='ordinary_lab':continue
        free='Free Water Test | Fluid Loss Test'
        for key in ('free_water','free_water_45'):
            bind(free,'s.lab.'+key,'lab.'+key,display.get(key),lab.get(key),'mL in 250 mL @ 2hr',
                'engineering_tools.validate_lab_collection_results / source Word Free Water Test')
        fluid_loss_condition=ref['temperature_valid'] and matches(free,'s.lab.bhct',ref['conditions'].get('bhct'))
        bind(free,"s.lab.get('api_fl_collected', '-')",'lab.filtrate_30min',display.get('api_fl_collected'),lab.get('api_fl_collected'),'mL',
            'project_state.refresh_lab_payloads (collected input) / independent measured filtrate',permitted=fluid_loss_condition)
        bind(free,'s.lab.fluid_loss','lab.api_fluid_loss',display.get('fluid_loss'),lab.get('fluid_loss'),'mL',
            'project_state.refresh_lab_payloads (original admitted derivation)',permitted=fluid_loss_condition and item['payload_admitted'],kind='SOURCE_DERIVED_FROM_INDEPENDENT_MEASUREMENTS')
        basic=ref['temperature_valid'] and matches('Test Basic Data','s.lab.bhct',display.get('bhct')) and matches('Test Basic Data','s.lab.bhsp',display.get('bhsp'))
        thick='Thickening Time Test'
        thick_condition=basic and matches(thick,'s.lab.bhct',display.get('bhct')) and matches(thick,'s.lab.bhsp',display.get('bhsp'))
        for key in ('thickening_test_start','thickening_cell','thickening_30_bc','thickening_50_bc','thickening_time'):
            bind(thick,'s.lab.'+key,'lab.'+key,display.get(key),lab.get(key),'cell' if key=='thickening_cell' else 'HH:MM',
                'engineering_tools.validate_thickening_test / phase_10_procedure._word_quantity_context',numeric=key=='thickening_cell',permitted=thick_condition)
        comp='Compressive Strength Test';conditions=[]
        for test,fields in (('uca',('cs_8','cs_12','cs_24')),('crush',tuple('force_'+str(n) for n in range(1,5)))):
            values=lab.get('compressive',{}).get(test,{})
            selected=values.get('selected',False)
            if not selected:continue
            permitted=basic and matches('Test Basic Data','s.lab.bhst',display.get('bhst')) and matches(comp,'s.lab.'+test+'_temp',display.get(test+'_temp')) and matches(comp,'s.lab.'+test+'_pressure',display.get(test+'_pressure'))
            conditions.append(permitted)
            for key in fields:
                bind(comp,'s.lab.'+test+'_'+key,'lab.'+test+'.'+key,display.get(test+'_'+key),values.get(key),'psi' if test=='uca' else 'lbf',
                    'engineering_tools.validate_compressive_test / phase_10_procedure._word_quantity_context',permitted=permitted)
        bind(comp,'s.lab.compressive_result','lab.compressive_result',display.get('compressive_result'),lab.get('compressive'),'psi (source summary)',
            'engineering_tools.validate_compressive_test / phase_10_procedure._word_quantity_context',numeric=False,permitted=bool(conditions) and all(conditions),kind='SOURCE_DERIVED_STRENGTH_SUMMARY')
    # Original automatic recipe quantities; no printed Yield is fed back to the engine.
    cement=ref['cement_reference']
    if cement:
        for fluid,s in cement['slurries'].items():
            if ref['fluids'][fluid]['role']!='ordinary_lab':continue
            for material in s['lab']:
                name=material['Code']
                if not name:continue
                same=[m for m in s['lab'] if m['Code'].casefold()==name.casefold()]
                locations=[]
                for anchor in ('Conventional',):
                    table=fluid_table(parsed,anchor,fluid);headers=ref['mass_headers'].get(anchor)
                    candidates=[r for r in rows(table) if regular_columns(r)] if table and headers else []
                    header=[r for r in candidates if [norm(c['raw_text']) for c in r]==[norm(x) for x in headers]]
                    all_headers=[r for r in candidates if r and norm(r[0]['raw_text'])=='material type']
                    if header and len(header)==len(all_headers):
                        locations += [r[5] for r in candidates if len(r)==6 and r[1]['raw_text'].casefold()==name.casefold() and r[0]['raw_text']==material['Material Type']
                            and all(norm(c['column_label'] or '')==norm(h) for c,h in zip(r,headers))]
                inputs=[a for a in s['operator_additives'] if a['Name'].casefold()==name.casefold()]
                if name.casefold() in (s['base_cement'].casefold(),'base water'):tolerance=Decimal(1)
                elif len(inputs)==1:
                    dose=Decimal(str(inputs[0]['User Input']))
                    tolerance=Decimal('.3') if inputs[0]['Physical State']=='Liquid' or Decimal('.01')<=dose<=1 else Decimal(1) if dose>1 else Decimal(0)
                else:tolerance=None
                record=locations[0] if len(locations)==len(same)==1 and tolerance is not None and s['raw_lab'].get(name.casefold()) is not None else None
                f=finding(record,'lab.recipe_mass',material['Mass'],s['raw_lab'].get(name.casefold()),'',
                    'c02_engine.reference / phase_7_lab.build_lab_df_from_phase5 / phase_10_procedure.separate_lab_tables',tolerance=tolerance or 0)
                f.update(slurry=fluid,material=name,unit='g/600 mL',reference_kind='AUTOMATIC_SOURCE_FORMULATION',
                    tolerance_rule='Owner C02 lab-mass thresholds; original source-displayed expected value')
                if f['result'] in ('MATCH','DISCREPANCY'):f['reason']='Original automatic source recipe comparison; no measured Lab prediction'
                findings.append(f)
    spacer=ref['spacer']
    if spacer:
        table=fluid_table(parsed,'Spacer Lab Results','Spacer');headers=ref['mass_headers'].get('Spacer Lab Results')
        candidates=[r for r in rows(table) if regular_columns(r)] if table and headers else []
        valid=len([r for r in candidates if [norm(c['raw_text']) for c in r]==[norm(x) for x in headers]])==1
        for sample,display in zip(spacer['sample']['rows'],spacer['display']['lab_rows']):
            matches_=[r for r in candidates if len(r)==6 and r[1]['raw_text']==sample['Material'] and r[0]['raw_text']==display['Material Type']
                and all(norm(c['column_label'] or '')==norm(h) for c,h in zip(r,headers))] if valid else []
            record=matches_[0][5] if len(matches_)==1 else None
            tolerance=1 if sample['Material']=='Fresh Water' else Decimal('.3') if sample['Unit'].startswith('gal/') else 0
            f=finding(record,'lab.recipe_mass',display['Mass'],sample['Mass'],'',
                'standalone_spacer.lab_sample / project_state.spacer_lab_grid / phase_10_procedure._word_quantity_context',tolerance=tolerance)
            f.update(slurry='Spacer',material=sample['Material'],unit='g/600 mL',reference_kind='AUTOMATIC_SOURCE_FORMULATION',
                tolerance_rule='Water ±1g; liquid ±0.3g; other Spacer masses source-display equivalence (no guessed percent basis)')
            if f['result'] in ('MATCH','DISCREPANCY'):f['reason']='Original automatic Spacer sample comparison; no measured Lab prediction'
            findings.append(f)
    if not findings:
        findings.append(finding(None,'lab.reference',None,None,'','Independent active Lab reference unavailable',numeric=False))
    return finish(parsed,source,findings,[
        'PARTIAL only. Every measured observation is independently supplied; automatic recipes never predict Lab measurements',
        'API derivation requires original complete-source admission and explicit independent reference confirmation; absence is not zero',
        'CT stage Lab equivalence, Scavenger/Diesel/Pre Flush Word Lab reports, unknown layouts, IOD, lots and unimplemented concentrations remain unverified',
        'No Word output/correction, UI, full Formula/Procedure/Lab parity or fifteen-job golden certification'])


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('operator_json');ap.add_argument('docx');args=ap.parse_args()
    try:
        p=Path(args.operator_json).resolve(strict=True)
        if not p.is_relative_to(ROOT):raise ValueError('Operator input outside runtime')
        result=compare_document(args.docx,read_json(p.read_text()))
    except (ValueError,OSError,TypeError) as error:
        result={'status':'REFERENCE_INPUT_ERROR','reason':str(error),'findings':[]}
    print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))
    return 0 if result['status']=='PARTIAL_FINDINGS_ONLY' else 2


if __name__=='__main__':raise SystemExit(main())
