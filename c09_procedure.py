"""Official procedure/NOTE text and order only; every result remains partial."""
import argparse
import ast
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


def density_condition_atom(parsed, source, findings, document, operator):
    """One source-owned literal argument, not numerical decomposition or editing."""
    atom={'field':'ordered_notes.density_conditions.atom','section':None,'slurry':None,'locator':None,
        'result':'NOT_VERIFIABLE','reason':'Source expression or unique literal Word span is unproved; whole NOTE evidence retained.',
        'source_function':None,'source_wording':None,'raw_reported_text':None,'reported_state':'MISSING',
        'unit':None,'full_precision_expected':None,'read_only':True,'correction_eligible':False,'atom_proof':None}
    try:
        from c02_engine import verify_source
        from checker_parser import text_of
        from docx import Document
        from docx.oxml.ns import qn
        from io import BytesIO
        verify_source()
        path=SNAPSHOT/'phase_10_procedure.py';source_bytes=path.read_bytes();file_sha=hashlib.sha256(source_bytes).hexdigest()
        identity=hashlib.sha256(json.dumps(operator,sort_keys=True,allow_nan=False).encode()).hexdigest()
        if (source.get('source_sha')!=SOURCE_SHA or source.get('operator_input_sha256')!=identity or
                source.get('source_module_sha256',{}).get(path.name)!=file_sha):return atom
        tree=ast.parse(source_bytes.decode('utf-8'))
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_ordered_notes')
        def assignment(key):
            matches=[n for n in function.body if isinstance(n,ast.Assign) and len(n.targets)==1 and
                isinstance(n.targets[0],ast.Subscript) and isinstance(n.targets[0].value,ast.Name) and
                n.targets[0].value.id=='notes' and isinstance(n.targets[0].slice,ast.Constant) and n.targets[0].slice.value==key]
            if len(matches)!=1:raise ValueError('Source expression assignment is not unique')
            return matches[0]
        expression=assignment('note_densities');call=expression.value
        if (not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute) or call.func.attr!='next' or
                not isinstance(call.func.value,ast.Name) or call.func.value.id!='counter' or len(call.args)!=1 or call.keywords or
                not isinstance(call.args[0],ast.Constant) or not isinstance(call.args[0].value,str)):return atom
        literal=call.args[0].value
        # Follow the original all_notes construction, not a guessed NOTE number.
        first=assignment('all_notes').value
        while isinstance(first,ast.BinOp) and isinstance(first.op,ast.Add):first=first.left
        if not isinstance(first,ast.List):return atom
        keys=[n.slice.value for n in first.elts if isinstance(n,ast.Subscript) and isinstance(n.value,ast.Name) and
            n.value.id=='notes' and isinstance(n.slice,ast.Constant)]
        if len(keys)!=len(first.elts) or keys.count('note_densities')!=1:return atom
        reference=source['reference'];full=reference['all_source_notes'][keys.index('note_densities')]
        if not literal or not full.endswith(literal) or full.count(literal)!=1:return atom
        template_bytes=(SNAPSHOT/'master_template.docx').read_bytes();template_sha=hashlib.sha256(template_bytes).hexdigest()
        locked_template=next(item['sha256'] for item in json.loads((ROOT/'upstream.lock.json').read_text())['files']
            if item['path']=='master_template.docx')
        if template_sha!=locked_template:return atom
        template=Document(BytesIO(template_bytes));token='{{ note_densities }}'
        slots=[p for p in template.element.body if p.tag==qn('w:p') and token in text_of(p)]
        if len(slots)!=1 or text_of(slots[0]).count(token)!=1:return atom
        prefix,suffix=text_of(slots[0]).split(token)
        if suffix:return atom
        parents=[f for f in findings if f['field']=='ordered_notes' and f.get('source_wording')==prefix+full]
        if len(parents)!=1:return atom
        parent=parents[0]
        if parent['result']!='MATCH' or parent.get('slurry') is not None or parent.get('raw_reported_text')!=prefix+full:return atom
        paragraph=document.element.body[parent['locator']['body_block']];literal_paragraph(paragraph,document)
        if any(child.tag not in (qn('w:pPr'),qn('w:r'),qn('w:proofErr')) for child in paragraph):return atom
        if any(child.tag not in (qn('w:rPr'),qn('w:br'),qn('w:cr'),qn('w:t'))
                for run in paragraph.findall(qn('w:r')) for child in run):return atom
        texts=list(paragraph.iter(qn('w:t')))
        if (len(texts)!=1 or texts[0].text!=full or texts[0].getparent().tag!=qn('w:r') or
                texts[0].getparent().getparent()!=paragraph or text_of(texts[0].getparent())!=full or
                text_of(paragraph)!=prefix+full):return atom
        if sum(literal in r['raw_text'] for r in parsed['records'] if r['section']!='excluded')!=1:return atom
        raw=parent['raw_reported_text'];start=len(raw)-len(literal);run=texts[0].getparent()
        atom.update(section=parent['section'],locator=parent['locator'],original_source_order=parent['original_source_order'],
            result='MATCH',reason='Read-only fixed source expression, named template field and one literal text node; no scalar or measurement credit.',
            source_function='phase_10_procedure.py:build_ordered_notes.notes.note_densities',source_wording=literal,
            raw_reported_text=raw[start:],reported_state='TEXT',independent_reference_sha256=identity,
            job_type=operator['program']['job_type'],association_scope='GLOBAL_DENSITY_DISPLAY_CONVENTION_NOT_A_SLURRY',
            atom_proof={'source_path':path.name,'source_symbol':'build_ordered_notes','source_line':expression.lineno,
                'source_file_sha256':file_sha,'source_expression_sha256':hashlib.sha256(literal.encode()).hexdigest(),
                'template_field':'note_densities','template_sha256':template_sha,
                'template_xml_path':slots[0].getroottree().getpath(slots[0]),'character_span':[start,len(raw)],
                'utf8_byte_span':[len(raw[:start].encode()),len(raw.encode())],
                'run_index':list(paragraph.iter(qn('w:r'))).index(run),'run_character_span':[len(full)-len(literal),len(full)],
                'text_node_xml_path':texts[0].getroottree().getpath(texts[0]),'measurement':False})
    except (ValueError,KeyError,TypeError,OSError,StopIteration,IndexError):
        pass
    return atom


def compare_document(path, operator):
    parsed=parse_docx(path)
    if parsed['status']=='REJECTED':return parsed
    source={};findings=[];document=None
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
        document=Document(BytesIO(original))
        notes=attributed_notes(parsed,reference['preparation'],document)
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
    if source:
        findings.append(density_condition_atom(parsed,source,findings,document,operator))
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
