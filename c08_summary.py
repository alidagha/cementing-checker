"""C08 exact Executive Summary claims; partial findings, never a program approval."""
import argparse
from hashlib import sha256
from io import BytesIO
import json
import re
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from checker_parser import parse_docx, safe_input, heading, text_of
from comparison_records import finish
from narrative_source import request
from c02_engine import read_json


def equivalent(text):
    # Horizontal whitespace only: paragraph/line breaks, case, units, punctuation stay meaningful.
    return '\n'.join(re.sub(r'[^\S\n]+',' ',line).strip() for line in text.replace('\r\n','\n').split('\n')).strip()


def literal_paragraph(element, document):
    """Raw text cannot prove Word list numbers, fields or hidden-text rendering."""
    unsupported={qn('w:'+tag) for tag in ('numPr','fldSimple','fldChar','instrText','vanish','webHidden')}
    if any(n.tag in unsupported for n in element.iter()):
        raise ValueError('Unproved Word numbering, field or hidden narrative text')
    styles={s.get(qn('w:styleId')):s for s in document.styles.element}
    pending=[n.get(qn('w:val')) for n in element.iter() if n.tag in (qn('w:pStyle'),qn('w:rStyle'))]
    pending.extend(key for key,s in styles.items() if s.get(qn('w:default'))=='1')
    seen=set()
    while pending:
        key=pending.pop()
        if key in seen:continue
        seen.add(key);style=styles.get(key)
        if style is None:continue
        if any(n.tag in unsupported for n in style.iter()):
            raise ValueError('Unproved inherited Word numbering or hidden narrative text')
        base=style.find(qn('w:basedOn'))
        if base is not None:pending.append(base.get(qn('w:val')))


def section_records(path, parsed, section):
    """Prove a single physical section envelope; no heading/table/text flattening."""
    original=safe_input(path)
    if sha256(original).hexdigest()!=parsed['source_document_sha256']:raise ValueError('Document changed during extraction')
    document=Document(BytesIO(original));body=document.element.body
    starts=[i for i,b in enumerate(body) if b.tag==qn('w:p') and heading(text_of(b))==section]
    if len(starts)!=1:raise ValueError('Missing/duplicate semantic section heading')
    start=starts[0];end=len(body)
    excluded_tocs={w['body_block'] for w in parsed.get('excluded_wrappers',[])
        if w['reason']=='TOC gallery, field and paragraph styles'}
    for i in range(start+1,len(body)):
        b=body[i]
        if i in excluded_tocs and b.tag==qn('w:sdt'):continue
        if b.tag==qn('w:p') and heading(text_of(b)) is not None:
            end=i;break
        if b.tag==qn('w:p') and text_of(b).strip():literal_paragraph(b,document)
        style=b.find('./'+qn('w:pPr')+'/'+qn('w:pStyle'))
        if b.tag==qn('w:p') and text_of(b).strip() and style is not None and style.get(qn('w:val'),'').lower().startswith('heading'):
            raise ValueError('Unknown nonblank heading within narrative envelope')
        if text_of(b).strip() and b.tag!=qn('w:p'):
            raise ValueError('Narrative table/wrapper has no proved physical projection')
    records=[r for r in parsed['records'] if start<r['locator']['body_block']<end and r['raw_text'].strip()]
    physical=[i for i in range(start+1,end) if body[i].tag==qn('w:p') and text_of(body[i]).strip()]
    if [r['locator']['body_block'] for r in records]!=physical or any(r['section']!=section or r['locator'].get('table') is not None for r in records):
        raise ValueError('Narrative physical paragraphs are not completely indexed')
    return records



def compare_document(path, operator):
    parsed=parse_docx(path)
    if parsed['status']=='REJECTED':return parsed
    finding={'field':'executive_summary','section':'summary','slurry':None,'locator':None,
        'result':'NOT_VERIFIABLE','reason':'Independent projection unavailable',
        'raw_reported_text':None,'reported_state':'MISSING','source_wording':None,
        'source_function':None,'original_source_orders':[],'association_proof':None}
    source={}
    try:
        source=request(operator)
        expected=source['reference']['text'];finding.update(source_wording=expected,
            independent_reference_sha256=source.get('operator_input_sha256') or source['reference']['text_sha256'],
            reference_kind=source['reference']['kind'],source_function=source['reference']['function'])
        records=section_records(path,parsed,'summary')
        finding['original_source_orders']=[r['source_order'] for r in records]
        if len(records)!=1:
            finding['reason']='Pinned template has one summary paragraph with internal breaks; missing/repeated/split physical paragraphs unverified'
        else:
            record=records[0];raw=record['raw_text']
            finding.update(locator=record['locator'],raw_reported_text=raw,reported_state=record['value_state'],
                association_proof='Unique Executive Summary envelope; one physical source-template paragraph; complete raw record',
                result='MATCH' if equivalent(raw)==equivalent(expected) else 'DISCREPANCY',
                reason='Exact independent/source wording and break order, horizontal whitespace only')
            if record['value_state'] in ('MISSING','DASH','NA_PRINTED'):
                finding.update(result='NOT_VERIFIABLE',reason='Printed absence is not a narrative reference')
    except (ValueError,TypeError,KeyError,OSError) as error:
        finding.update(result='NOT_VERIFIABLE',reason=str(error))
    return finish(parsed,source,[finding],[
        'PARTIAL_FINDINGS_ONLY; C01R claims remain indexed. No overall program PASS.',
        'Only the pinned single-paragraph summary presentation is supported; unknown structure fails closed.',
        'CT automatic admission, complete 15-job goldens and whole-program narrative parity NOT VERIFIED.',
        'Document-control metadata outside the source summary is not compared by C08.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('docx');parser.add_argument('operator_json')
    args=parser.parse_args();operator=read_json(Path(args.operator_json).read_text())
    print(json.dumps(compare_document(args.docx,operator),sort_keys=True,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':main()
