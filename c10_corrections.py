"""Explicit, source-proved Yield/Sacks edits to a new private DOCX; never approval."""
import argparse
from copy import copy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import xml.parsers.expat
import zipfile

from docx import Document
from docx.oxml.ns import qn
from c08_summary import literal_paragraph
from checker_parser import safe_input, text_of, heading
from comparison_records import ROOT
from c02_engine import SOURCE_SHA, read_json
from tools.ci import source_proof
from tools.provision import verify_candidate

TEMPLATE_SHA = 'a1128b0e9352e1dd7c8768eecc9335c50858356cee80ed33c0ec275e26c4d08b'
SCHEMA = 'c10.1'
ORDINARY = {'Main', 'Lead', 'Lead #1', 'Lead #2', 'Tail'}


class Refusal(ValueError):
    """A rejected transaction publishes no corrected file."""


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def private_path(value, existing=True):
    p = Path(value).absolute()
    if p.suffix != '.docx' or p.resolve(strict=existing) != p or not p.is_relative_to(ROOT/'tmp'):
        raise Refusal('PRIVATE_DOCX_PATH_REQUIRED')
    if any((parent/'.git').exists() for parent in (p.parent, *p.parents)):
        raise Refusal('GIT_WORKTREE_PROHIBITED')
    if existing and (not p.is_file() or p.is_symlink()):
        raise Refusal('REGULAR_ORIGINAL_REQUIRED')
    if not existing and (p.exists() or p.is_symlink() or not p.parent.is_dir()):
        raise Refusal('NEW_OUTPUT_WITH_EXISTING_PRIVATE_PARENT_REQUIRED')
    return p


def identities():
    if ROOT.resolve() != ROOT or any((p/'.git').exists() for p in (ROOT, *ROOT.parents)):
        raise Refusal('GIT_FREE_RUNTIME_REQUIRED')
    verify_candidate(ROOT)
    proof = source_proof(ROOT)
    lock = read_json((ROOT/'upstream.lock.json').read_text())
    actual = sha256((ROOT/'snapshot/master_template.docx').read_bytes()).hexdigest()
    if proof['upstream_commit'] != SOURCE_SHA or actual != TEMPLATE_SHA:
        raise Refusal('SOURCE_TEMPLATE_DRIFT')
    return {'source_sha': SOURCE_SHA, 'template_sha256': actual, 'template_blob': lock['template_blob'],
        'source_lock_sha256': proof['source_lock'], 'snapshot_manifest_sha256': proof['manifest'],
        'accepted_lock_sha256': sha256((ROOT/'accepted.lock.json').read_bytes()).hexdigest()}


def key(finding):
    return {'locator': finding['locator'], 'field': finding['field'], 'slurry': finding['slurry']}


def literal(element, document):
    literal_paragraph(element, document)
    bad = {qn('w:'+n) for n in ('sdt','hyperlink','customXml','smartTag','ins','del','moveFrom','moveTo',
        'rPrChange','pPrChange','tcPrChange','tblPrChange','drawing','pict','sym','object','altChunk')}
    if any(n.tag in bad for n in element.iter()):
        raise Refusal('DYNAMIC_OR_NONLITERAL_XML')
    # Table styles and docDefaults also affect scalar visibility/numbering.
    forbidden = {qn('w:'+n) for n in ('numPr','vanish','webHidden','fldSimple','fldChar','instrText')}
    styles = {s.get(qn('w:styleId')): s for s in document.styles.element}
    pending = [n.get(qn('w:val')) for n in element.iter()
        if n.tag in {qn('w:'+tag) for tag in ('tblStyle','pStyle','rStyle')}]
    defaults = document.styles.element.find(qn('w:docDefaults'))
    if defaults is not None and any(n.tag in forbidden for n in defaults.iter()):
        raise Refusal('NONLITERAL_DOCUMENT_DEFAULTS')
    seen = set()
    while pending:
        name = pending.pop()
        if name in seen: continue
        seen.add(name)
        style = styles.get(name)
        if style is None: raise Refusal('UNRESOLVED_FORMATTING_STYLE')
        if any(n.tag in forbidden for n in style.iter()): raise Refusal('NONLITERAL_TABLE_STYLE')
        base = style.find(qn('w:basedOn'))
        if base is not None: pending.append(base.get(qn('w:val')))


def target(document, finding):
    loc = finding['locator']
    if loc['table_path'] or loc['column_span'] != 1:
        raise Refusal('NESTED_OR_MERGED_TARGET')
    body = document.element.body
    table = body[loc['body_block']]
    if table.tag != qn('w:tbl'): raise Refusal('PHYSICAL_TABLE_REQUIRED')
    literal(table, document)
    # Prove the physical Cementing Program heading as well as the table identity.
    boundaries = [p for p in list(body)[:loc['body_block']] if p.tag == qn('w:p') and heading(text_of(p)) is not None]
    if not boundaries or heading(text_of(boundaries[-1])) != 'cement':
        raise Refusal('CEMENT_SECTION_NOT_PROVED')
    literal(boundaries[-1], document)
    row = table.findall(qn('w:tr'))[loc['row']]
    cells = row.findall(qn('w:tc'))
    if any(n.tag in {qn('w:'+x) for x in ('gridSpan','vMerge','hMerge','gridBefore','gridAfter')} for n in row.iter()):
        raise Refusal('MERGED_OR_IRREGULAR_TARGET_ROW')
    grid = table.find(qn('w:tblGrid'))
    if grid is None or len(grid) != len(cells): raise Refusal('IRREGULAR_PHYSICAL_GRID')
    title = table.findall(qn('w:tr'))[0].findall(qn('w:tc'))
    suffix = 'Data' if finding.get('field')=='yield' else 'Blend Data'
    # The source title is one physical cell, never duplicate title cells deduplicated by text.
    if (len(title)!=1 or text_of(title[0])!=finding.get('slurry','')+' Cement Slurry '+suffix):
        raise Refusal('AMBIGUOUS_PHYSICAL_TABLE_TITLE')
    cell = cells[loc['column']]
    paragraphs = cell.findall(qn('w:p'))
    if len(paragraphs) != 1 or any(n.tag not in (qn('w:tcPr'),qn('w:p')) for n in cell):
        raise Refusal('SINGLE_PLAIN_PARAGRAPH_REQUIRED')
    p = paragraphs[0]
    if list(cell).index(p) != loc['paragraph']: raise Refusal('PARAGRAPH_LOCATOR_DRIFT')
    if any(n.tag not in (qn('w:pPr'),qn('w:r')) for n in p): raise Refusal('PLAIN_RUN_REQUIRED')
    runs = p.findall(qn('w:r'))
    if len(runs) != 1 or any(n.tag not in (qn('w:rPr'),qn('w:t')) for n in runs[0]):
        raise Refusal('SPLIT_OR_COMPLEX_RUN_REQUIRES_MANUAL_CORRECTION')
    texts = runs[0].findall(qn('w:t'))
    if len(texts) != 1 or texts[0].text != finding['raw_reported_text']:
        raise Refusal('EXACT_PHYSICAL_TEXT_NOT_PROVED')
    if set(texts[0].attrib) - {'{http://www.w3.org/XML/1998/namespace}space'}:
        raise Refusal('UNSUPPORTED_TEXT_ATTRIBUTES')
    settings = document.settings.element
    if any(settings.find(qn('w:'+name)) is not None for name in ('documentProtection','trackRevisions')):
        raise Refusal('PROTECTED_OR_TRACKED_DOCUMENT')
    path = []
    node = texts[0]
    while node.getparent() is not None:
        parent = node.getparent(); path.append(list(parent).index(node)); node = parent
    return tuple(reversed(path))


def spans(raw):
    """XML parser byte offsets, not string search or whole-XML serialization."""
    parser = xml.parsers.expat.ParserCreate()
    stack = []; found = {}
    def start(name, attributes):
        if stack:
            path = stack[-1][0] + (stack[-1][1],); stack[-1][1] += 1
        else: path = ()
        stack.append([path,0,raw.index(b'>',parser.CurrentByteIndex)+1])
    def end(name):
        path, _, begin = stack.pop(); found[path] = (begin,parser.CurrentByteIndex)
    def unsupported(*args): raise Refusal('COMMENT_PI_OR_ENTITY_XML_UNSUPPORTED')
    parser.StartElementHandler = start; parser.EndElementHandler = end
    parser.CommentHandler = unsupported; parser.ProcessingInstructionHandler = unsupported
    parser.StartDoctypeDeclHandler = unsupported; parser.EntityDeclHandler = unsupported
    parser.Parse(raw, True)
    return found


def proposals(path, operator):
    import c02_compare as cc
    pins = identities(); original = safe_input(path); operator_sha = digest(operator)
    comparison = cc.compare_document(path, operator)
    if comparison['status'] != 'PARTIAL_FINDINGS_ONLY': raise Refusal('SOURCE_COMPARISON_UNAVAILABLE')
    if digest(operator)!=operator_sha: raise Refusal('SOURCE_MUTATED_INDEPENDENT_OPERATOR')
    bindings = dict(pins, original_document_sha256=sha256(original).hexdigest(), operator_sha256=operator_sha)
    if (comparison['source_document_sha256'] != bindings['original_document_sha256']
            or comparison['reference']['operator_input_sha256'] != bindings['operator_sha256']):
        raise Refusal('SOURCE_DOCUMENT_OR_OPERATOR_DRIFT')
    document = Document(BytesIO(original)); offers = []
    for f in comparison['findings']:
        if f['result'] != 'DISCREPANCY': continue
        item = dict(key(f), original_raw_text=f['raw_reported_text'], replacement=None,
            action='MANUAL_CORRECTION_REQUIRED', reason='Unsupported field/role; no automatic dependency selection',
            dependency_group=str(f['slurry'])+':automatic-cement', source_function=f['source_function'])
        if (f['field'] in ('yield','sacks') and f['mapping_state']=='IDENTIFIED' and f['section']=='cement'
                and f['slurry'] in ORDINARY and operator['job_type'] not in ('CMT PLUG WITH CT','CMT SQUEEZE')):
            try:
                path_key = target(document, f)
                with zipfile.ZipFile(BytesIO(original)) as z: xml = z.read('word/document.xml')
                start, end = spans(xml)[path_key]
                if xml[start:end] != f['raw_reported_text'].encode(): raise Refusal('NONLITERAL_TEXT_ENCODING')
                source = comparison['reference']['slurries'][f['slurry']]
                replacement = (source['display']['yield_cuft_sk']+' cuft/sk' if f['field']=='yield'
                    else source['blend'][0]['sks or lbs'])
                if replacement != f['source_rounded_expected']+' '+f['unit']:
                    raise Refusal('SOURCE_DISPLAY_NOT_PROVED')
                item.update(action='SELECTABLE', replacement=replacement, reason='Fresh original engine + unique literal cell')
            except (ValueError, KeyError, IndexError) as error:
                item['reason'] = str(error)
        item['finding_id'] = digest({'bindings': bindings, 'finding': item})
        offers.append(item)
    return {'schema': SCHEMA, 'status':'PARTIAL_FINDINGS_ONLY', 'transaction_status':'PREVIEW_ONLY',
        'bindings':bindings, 'proposals':offers, 'comparison_before':comparison,
        'recheck_scope':{'C01R':'FRESH_PARSE', 'C02':'FRESH_SOURCE_COMPARISON',
            'C03_C09':'NOT_VERIFIABLE: independent adapter-specific references/rechecks not supplied'},
        'manual_correction_classes':['C04 dependency locations and gross quantities','NOTE/procedure/narrative',
            'Laboratory/observed measurements','CT/special fluids/solver changes','Split/merged/dynamic text'],
        'limitations':['Only ordinary cement Yield/Sacks literal cells are editable; no whole-program PASS',
            'C04 gross/NOTE/procedure, measured Lab, special fluids, CT and full cascades require manual correction or later scope',
            'Every original C02 finding is retained; other adapters/coverage remain unverified, not repaired']}


def package_copy(original, changes):
    with zipfile.ZipFile(BytesIO(original)) as src:
        xml = src.read('word/document.xml'); offsets = spans(xml); edits = []
        for path, old, new in changes:
            start, end = offsets[path]
            if xml[start:end] != old.encode(): raise Refusal('XML_TEXT_DRIFT')
            edits.append((start,end,new.encode()))
        for start,end,new in sorted(edits, reverse=True): xml = xml[:start]+new+xml[end:]
        data = BytesIO()
        with zipfile.ZipFile(data,'w') as dst:
            dst.comment = src.comment
            for info in src.infolist():
                dst.writestr(copy(info), xml if info.filename=='word/document.xml' else src.read(info))
        candidate = data.getvalue()
        with zipfile.ZipFile(BytesIO(candidate)) as dst:
            if src.namelist()!=dst.namelist() or src.comment!=dst.comment or dst.testzip() is not None:
                raise Refusal('PACKAGE_STRUCTURE_DRIFT')
            for old,new in zip(src.infolist(),dst.infolist()):
                ignore = {'header_offset','_end_offset','CRC','file_size','compress_size'}
                attributes = set(zipfile.ZipInfo.__slots__)-ignore
                if any(getattr(old,k,None)!=getattr(new,k,None) for k in attributes):
                    raise Refusal('ZIP_METADATA_CANNOT_BE_PRESERVED')
                if old.filename!='word/document.xml' and src.read(old)!=dst.read(new):
                    raise Refusal('UNSELECTED_PACKAGE_PART_CHANGED')
                if old.filename!='word/document.xml' and old.compress_size!=new.compress_size:
                    raise Refusal('UNSELECTED_ZIP_METADATA_CANNOT_BE_PRESERVED')
    return candidate


def recheck(path, before, selected):
    import c02_compare as cc
    after = cc.compare_document(path, before['comparison_before']['reference']['operator_inputs'])
    if after['status']!='PARTIAL_FINDINGS_ONLY': raise Refusal('RECHECK_UNAVAILABLE_NOT_VERIFIABLE')
    old = before['comparison_before']['findings']; new = after['findings']
    if len(old)!=len(new): raise Refusal('RECHECK_CLAIM_LOSS')
    wanted = {digest(key(x)):x for x in selected}
    for a,b in zip(old,new):
        k = digest(key(a))
        if key(a)!=key(b): raise Refusal('RECHECK_LOCATOR_DRIFT')
        if k in wanted:
            if b['result']!='MATCH' or b['raw_reported_text']!=wanted[k]['replacement']:
                raise Refusal('SELECTED_CLAIM_NOT_RECHECKED')
        elif {k:v for k,v in a.items() if k!='source_document_sha256'}!={k:v for k,v in b.items() if k!='source_document_sha256'}:
            raise Refusal('UNSELECTED_FINDING_CHANGED')
    if before['comparison_before']['reference']['slurries']!=after['reference']['slurries']:
        raise Refusal('SOURCE_REFERENCE_CHANGED')
    return after


def verify_json_files(files, operator, selection):
    if files is None: return
    if not isinstance(files,list) or len(files)!=(2 if selection is not None else 1):
        raise Refusal('INVALID_JSON_INPUT_BINDINGS')
    for item,value in zip(files, [operator,selection]):
        p = Path(item['path']).absolute()
        if p.resolve()!=p or not p.is_file() or not p.is_relative_to(ROOT/'tmp'):
            raise Refusal('PRIVATE_JSON_PATH_REQUIRED')
        if any((parent/'.git').exists() for parent in (p.parent,*p.parents)):
            raise Refusal('GIT_WORKTREE_PROHIBITED')
        raw = p.read_bytes()
        if sha256(raw).hexdigest()!=item['sha256'] or read_json(raw)!=value:
            raise Refusal('INPUT_JSON_DRIFT')


def execute(docx, operator, selection=None, output=None, json_inputs=None):
    verify_json_files(json_inputs,operator,selection)
    path = private_path(docx); before = proposals(path, operator)
    if selection is None and output is None: return before
    if (type(selection) is not dict or set(selection)!={'schema','bindings','selected'}
            or selection['schema']!=SCHEMA or selection['bindings']!=before['bindings']):
        raise Refusal('STALE_OR_FORGED_BINDINGS')
    selected = selection['selected']
    if not isinstance(selected,list) or not selected or any(type(x) is not dict for x in selected):
        raise Refusal('EXPLICIT_ENUMERATED_SELECTION_REQUIRED')
    ids = [x.get('finding_id') for x in selected]
    if len(ids)!=len(set(ids)): raise Refusal('DUPLICATE_SELECTION')
    for item in selected:
        if item not in before['proposals']: raise Refusal('STALE_OR_FORGED_FINDING_LOCATOR_REPLACEMENT')
        if item['action']!='SELECTABLE': raise Refusal('MANUAL_CORRECTION_REQUIRED')
    output = private_path(output,False)
    original = safe_input(path)
    if sha256(original).hexdigest()!=before['bindings']['original_document_sha256']: raise Refusal('ORIGINAL_DRIFT')
    document = Document(BytesIO(original))
    changes = [(target(document,dict(locator=x['locator'],raw_reported_text=x['original_raw_text'],field=x['field'],slurry=x['slurry'])),
        x['original_raw_text'],x['replacement']) for x in selected]
    candidate = package_copy(original, changes)
    # Directory descriptors prevent symlink-parent substitution; hard-link is atomic/no-clobber.
    fd = os.open(ROOT/'tmp', os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    temporary = '.c10-'+uuid.uuid4().hex+'.docx'
    staged = None
    try:
        for part in output.parent.relative_to(ROOT/'tmp').parts:
            child = os.open('/proc/self/fd/'+str(fd)+'/'+part, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            os.close(fd); fd = child
        base = '/proc/self/fd/'+str(fd)+'/'
        staged = base+temporary
        with open(staged,'xb') as handle:
            handle.write(candidate); handle.flush(); os.fsync(handle.fileno())
        after = recheck(Path(staged),before,selected)
        current = identities()
        if current!= {k:before['bindings'][k] for k in current}:
            raise Refusal('SOURCE_IDENTITY_DRIFT')
        if sha256(safe_input(private_path(path))).hexdigest()!=before['bindings']['original_document_sha256'] or digest(operator)!=before['bindings']['operator_sha256']:
            raise Refusal('ORIGINAL_OR_OPERATOR_CHANGED_BEFORE_PUBLICATION')
        if Path(base).resolve()!=output.parent: raise Refusal('OUTPUT_PARENT_MOVED')
        verify_json_files(json_inputs,operator,selection)
        result = dict(before,transaction_status='COPY_CREATED', comparison_after=after,
            selected=selected, unselected=[x for x in before['proposals'] if x not in selected],
            original_document_sha256=before['bindings']['original_document_sha256'],
            new_document_sha256=sha256(candidate).hexdigest(), output_path=str(output),
            unchanged_package_parts=True, dependency_group_complete=False)
        os.link(staged,base+output.name,follow_symlinks=False)
        return result
    finally:
        if staged is not None and Path(staged).exists(): os.unlink(staged)
        os.close(fd)


def call(payload):
    environment = dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp'),
        XDG_CACHE_HOME=str(ROOT/'cache'),XDG_CONFIG_HOME=str(ROOT/'cache/config'),MPLCONFIGDIR=str(ROOT/'cache/mpl'))
    p = subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--worker'],
        input=json.dumps(payload,allow_nan=False),text=True,capture_output=True,cwd=ROOT,env=environment,timeout=120)
    if p.returncode not in (0,2): raise Refusal('ISOLATED_TRANSACTION_FAILED')
    result = read_json(p.stdout)
    if (p.returncode==0)!=(result.get('status')=='PARTIAL_FINDINGS_ONLY'):
        raise Refusal('ISOLATED_TRANSACTION_STATUS_MISMATCH')
    return result


def propose(docx, operator):
    return call({'docx':str(docx),'operator':operator})


def apply(docx, operator, selection, output):
    return call({'docx':str(docx),'operator':operator,'selection':selection,'output':str(output)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',action='store_true'); parser.add_argument('operator_json',nargs='?')
    parser.add_argument('docx',nargs='?'); parser.add_argument('--selection'); parser.add_argument('--output')
    args = parser.parse_args()
    try:
        if args.worker:
            from engineering_source import install_audit
            install_audit()
            # Same pure original-source bridge used by accepted C03; no live state or formulas replaced.
            import c02_compare as cc
            from c02_engine import reference
            cc.engine = reference
            result = execute(**read_json(sys.stdin.read()))
        else:
            if not args.operator_json or not args.docx or bool(args.selection)!=bool(args.output):
                raise Refusal('OPERATOR_DOCX_AND_EXPLICIT_SELECTION_OUTPUT_PAIR_REQUIRED')
            files = [Path(args.operator_json).absolute()]+([Path(args.selection).absolute()] if args.selection else [])
            for p in files:
                if p.resolve()!=p or not p.is_file() or not p.is_relative_to(ROOT/'tmp'): raise Refusal('PRIVATE_JSON_PATH_REQUIRED')
            raw = [p.read_bytes() for p in files]
            payload = {'docx':args.docx,'operator':read_json(raw[0])}
            if args.selection: payload.update(selection=read_json(raw[1]),output=args.output)
            payload['json_inputs'] = [{'path':str(p),'sha256':sha256(v).hexdigest()} for p,v in zip(files,raw)]
            # Recheck these byte bindings in the worker immediately before publication.
            result = call(payload)
    except (ValueError,TypeError,KeyError,IndexError,OSError,RuntimeError,zipfile.BadZipFile,xml.parsers.expat.ExpatError) as error:
        result = {'schema':SCHEMA,'status':'INPUT_REJECTED','transaction_status':'NO_COPY_CREATED',
            'reason':str(error) if isinstance(error,Refusal) else 'UNSAFE_OR_UNVERIFIABLE_CORRECTION',
            'required_action':'MANUAL_CORRECTION_REQUIRED; no repaired claim or copy is certified'}
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if result['status']=='PARTIAL_FINDINGS_ONLY' else 2


if __name__=='__main__': raise SystemExit(main())
