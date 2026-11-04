"""Official procedure/NOTE text and order only; every result remains partial."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from checker_parser import parse_docx
from comparison_records import ROOT, SOURCE_SHA, finish
from c08_summary import section_records, equivalent, literal_paragraph
from narrative_source import request, SNAPSHOT
from c02_engine import read_json


def render_reference(reference, destination):
    """Private pinned-template projection, not a certified full App export."""
    from docxtpl import DocxTemplate
    import phase_10_procedure as report
    destination=Path(destination).absolute()
    if destination.suffix!='.docx' or not destination.is_relative_to(ROOT/'tmp') or destination.resolve()!=destination or destination.exists():
        raise ValueError('New synthetic reference must remain in runtime/tmp')
    template=DocxTemplate(str(SNAPSHOT/'master_template.docx'))
    template.render(report._escape_xml_special_chars(report._word_quantity_context(reference.pop('context'))))
    template.save(str(destination))
    parsed=parse_docx(destination)
    if parsed['status']=='REJECTED':raise ValueError('Source-rendered structural reference rejected')
    reference['expected_procedure_records']=section_records(destination,parsed,'procedure')
    reference['expected_note_records']=attributed_notes(parsed,reference['preparation'])
    for record in reference['expected_procedure_records']+reference['expected_note_records']:
        record.pop('source_document_sha256',None)
    reference['fixture_classification']='SYNTHETIC PINNED-SOURCE PROJECTION; NOT FULL APP GOLDEN'


def attributed_notes(parsed, active, document=None):
    # Reuse C03's proved Data -> Blend -> Additives -> adjacent NOTE boundary.
    # Original records stay unchanged; this layer adds only an association proof.
    import sys
    sys.path.insert(0,str(ROOT/'c03'))
    from c03_water import attributed_groups
    groups,unassigned=attributed_groups(parsed['records'],set(active))
    proved={}
    for name in active:
        candidates=groups.get(name,[])
        if len(candidates)==1 and candidates[0]['complete'] and len(candidates[0]['notes'])==1 and not unassigned:
            record=candidates[0]['notes'][0]
            proved[record['source_order']]=name
    result=[]
    for r in parsed['records']:
        if r['note'] is None:continue
        if document is not None:
            loc=r['locator']
            if loc.get('table') is not None:raise ValueError('NOTE in a table has no proved paragraph projection')
            literal_paragraph(document.element.body[loc['body_block']],document)
        copy=dict(r)
        if 'Mix above Additives in' in r['raw_text'] and r['section']=='cement':
            copy['narrative_slurry_identity']=proved.get(r['source_order'])
            copy['narrative_identity_proved']=r['source_order'] in proved
        else:
            copy['narrative_slurry_identity']=r['association']
            copy['narrative_identity_proved']=r['association_state']!='AMBIGUOUS'
        result.append(copy)
    return result


def sequence_findings(actual, expected, field, reference):
    findings=[]
    kind=reference['kind'] if field=='procedure' else 'LOCKED_SOURCE_FROM_INDEPENDENT_INPUTS'
    compatible=bool(expected) and len(actual)==len(expected) and all(a['section']==e['section'] and
        a['association']==e['association'] and a['association_state']==e['association_state'] and
        a.get('narrative_slurry_identity')==e.get('narrative_slurry_identity') and
        a.get('narrative_identity_proved',True) and e.get('narrative_identity_proved',True) and
        (a['locator'].get('table') is None)==(e['locator'].get('table') is None)
        for a,e in zip(actual,expected))
    for i in range(max(len(actual),len(expected),1)):
        a=actual[i] if i<len(actual) else None;e=expected[i] if i<len(expected) else None
        finding={'field':field,'sequence_index':i,'section':a['section'] if a else None,
            'slurry':a.get('narrative_slurry_identity',a['association']) if a else None,'locator':a['locator'] if a else None,
            'original_source_order':a['source_order'] if a else None,
            'raw_reported_text':a['raw_text'] if a else None,'reported_state':a['value_state'] if a else 'MISSING',
            'expected_step':e['step'] if e else None,'reported_step':a['step'] if a else None,
            'expected_note':e['note'] if e else None,'reported_note':a['note'] if a else None,
            'source_wording':e['raw_text'] if e else None,'source_function':reference['function'],
            'reference_kind':kind,'result':'NOT_VERIFIABLE',
            'association_proof':'Complete physical paragraph sequence, semantic section and explicit slurry group, compared to independent pinned-template source projection',
            'reason':'Missing/repeated/cross-section or ambiguous sequence; no positional recovery'}
        if compatible and a is not None and e is not None:
            if a['association_state']=='AMBIGUOUS':
                finding['reason']='Ambiguous source/document slurry identity'
            elif a['value_state'] in ('MISSING','DASH','NA_PRINTED'):
                finding['reason']='Printed absence is not a source narrative'
            elif re.search(r'\.{3,}|…',e['raw_text']) and kind!='INDEPENDENT_APPROVED_MANUAL_TEXT':
                finding['reason']='Source retains rig-site/unfinished placeholders; no independent value is supplied'
            else:
                finding.update(result='MATCH' if equivalent(a['raw_text'])==equivalent(e['raw_text']) else 'DISCREPANCY',
                    reason='Exact independent/source wording, numbering and physical sequence; horizontal whitespace only')
        findings.append(finding)
    # An explicit sequence finding distinguishes a missing/duplicated sequence from
    # unproved per-record alignment. No individual claim is falsely mapped.
    identical=compatible and all(equivalent(a['raw_text'])==equivalent(e['raw_text']) for a,e in zip(actual,expected))
    complete=identical and all(f['result']=='MATCH' for f in findings)
    findings.append({'field':field+'.sequence','section':'procedure' if field=='procedure' else None,
        'slurry':None,'locator':None,'result':'MATCH' if complete else 'NOT_VERIFIABLE' if identical else 'DISCREPANCY',
        'reason':'Complete ordered independent source sequence; no whole-document approval' if complete else
            'Unresolved individual source/physical claims cannot complete this sequence' if identical else
            'Missing, changed or reordered independent source sequence; no positional recovery',
        'expected_count':len(expected),'reported_count':len(actual),
        'source_function':reference['function'],'source_wording':[e['raw_text'] for e in expected],
        'raw_reported_text':[a['raw_text'] for a in actual]})
    return findings


def stage_availability(operator, source, findings):
    """Current adapter evidence only, never full-engine/job applicability credit."""
    program=operator.get('program',{}) if isinstance(operator,dict) else {}
    if not isinstance(program,dict):program={}
    fluids=program.get('fluids',{});roles=list(fluids) if isinstance(fluids,dict) else []
    reason='Current source/physical reference is partial; only individually bound findings have credit.'
    if not source:
        reason='Current C09 independent source reference/projection was not admitted; no stage or role is credited.'
        if program.get('job_type')=='CMT PLUG WITH CT':
            reason='Original CT stages/report paths exist, but the current Checker narrative input schema does not admit a complete CT project.'
        elif any(n in roles for n in ('Spacer','Scavenger','Pre Flush','Diesel')):
            reason='Current C09 has no complete independently admitted NOTE context for the selected special fluid; no whole-reference fallback.'
    stages=[];role_stages=[]
    for stage,function in (('procedure','phase_10_procedure.generate_official_procedure; synchronize_report_texts'),
                           ('ordered_notes','phase_10_procedure.build_ordered_notes')):
        records=[f for f in findings if f['field']==stage]
        proved=[f for f in records if f.get('locator') is not None and f['result'] in ('MATCH','DISCREPANCY')]
        state='SOURCE_BLOCKED' if not source else 'SOURCE_PROVEN' if proved else 'PHYSICAL_ASSOCIATION_UNPROVEN'
        stages.append({'stage':stage,'state':state,'source_function':function,'reason':reason,
            'reference_kind':source.get('reference',{}).get('kind') if stage=='procedure' else
                'LOCKED_SOURCE_FROM_INDEPENDENT_INPUTS' if source else None,
            'claim_scope':'LITERAL_WORDING_AND_ORDER_ONLY',
            'physical_findings':len(proved),'unverified_findings':sum(f['result']=='NOT_VERIFIABLE' for f in records),
            'sequence_complete':any(f['field']==stage+'.sequence' and f['result']=='MATCH' for f in findings)})
        for role in roles:
            own=[f for f in proved if f.get('slurry')==role]
            role_stages.append({'stage':stage,'fluid':role,'state':'SOURCE_BLOCKED' if not source else
                'SOURCE_PROVEN' if own else 'PHYSICAL_ASSOCIATION_UNPROVEN',
                'physical_findings':len(own),'reason':reason if own or not source else
                    'No unique physical narrative association for this role; another role/global paragraph cannot supply it.'})
    return {'schema_version':1,'scope':'CURRENT_C09_ADAPTER_BOUNDARY_ONLY','job_type':program.get('job_type'),
        'source_sha':SOURCE_SHA,'source_reference_admitted':bool(source),'operator_input_sha256':source.get('operator_input_sha256'),
        'stages':stages,'role_stages':role_stages,'verified_production_claim_instances':0,'authentic_golden_status':'NOT_RUN'}


def compare_document(path, operator):
    parsed=parse_docx(path)
    if parsed['status']=='REJECTED':return parsed
    source={};findings=[]
    try:
        candidate=request(operator,'procedure')
        if (candidate.get('source_sha')!=SOURCE_SHA or candidate.get('operator_input_sha256')!=
                hashlib.sha256(json.dumps(operator,sort_keys=True,allow_nan=False).encode()).hexdigest()):
            raise ValueError('C09 independent source/operator identity is unproved')
        source=candidate;reference=source['reference']
        procedures=section_records(path,parsed,'procedure')
        from docx import Document
        from checker_parser import safe_input
        from io import BytesIO
        original=safe_input(path)
        if hashlib.sha256(original).hexdigest()!=parsed['source_document_sha256']:raise ValueError('Document drift')
        notes=attributed_notes(parsed,reference['preparation'],Document(BytesIO(original)))
        findings=sequence_findings(procedures,reference['expected_procedure_records'],'procedure',reference)
        findings+=sequence_findings(notes,reference['expected_note_records'],'ordered_notes',reference)
        for f in findings:f['independent_reference_sha256']=source['operator_input_sha256']
    except (ValueError,KeyError,TypeError,OSError):
        # Raw records are retained without pretending their physical association
        # or a failed source projection has been proved.
        findings=[{'field':'ordered_notes' if r['note'] is not None else 'procedure',
            'section':r['section'],'slurry':r['association'],'locator':r['locator'],
            'original_source_order':r['source_order'],'result':'NOT_VERIFIABLE',
            'reason':'C09 independent source reference or physical narrative association is unproved; no stage completion.',
            'source_function':None,'source_wording':None,'raw_reported_text':r['raw_text'],'reported_state':r['value_state']}
            for r in parsed['records'] if r['section']!='excluded' and (r['section']=='procedure' or r['note'] is not None)]
        if not findings:findings=[{'field':'procedure_and_notes','section':'procedure','slurry':None,'locator':None,
            'result':'NOT_VERIFIABLE','reason':'C09 independent reference/physical narrative is unavailable.',
            'source_function':None,'source_wording':None,'raw_reported_text':None}]
    result=finish(parsed,source,findings,[
        'PARTIAL_FINDINGS_ONLY; original C01R claims and all unresolved records remain indexed.',
        'Text/order equivalence is not engineering or full App export-readiness certification.',
        'CT, Scavenger, Pre Flush, Diesel and Standalone Spacer NOTE contexts are NOT VERIFIED in C09.',
        'Source rig-site blanks remain NOT_VERIFIABLE; no unknown numeric value is reconstructed.',
        'Notes excluded by C01R (Pore/Frac, Centralizer) remain outside scope; all source notes are retained in reference.',
        'No measured Lab result is synthesized; surface hardening hours must be independently supplied.'])
    result['availability']=stage_availability(operator,source,findings)
    if not source or not any(f.get('locator') is not None and f['result'] in ('MATCH','DISCREPANCY') for f in findings):
        result['status']='NOT_VERIFIABLE'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('docx');parser.add_argument('operator_json')
    args=parser.parse_args();operator=read_json(Path(args.operator_json).read_text())
    print(json.dumps(compare_document(args.docx,operator),sort_keys=True,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':main()
