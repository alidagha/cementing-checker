"""Private session intake and presentation of accepted Checker evidence; no formulas."""
from collections import OrderedDict
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from io import BytesIO
import subprocess
import sys
import tempfile
import uuid

from c10_corrections import ROOT, Refusal, digest, identities, literal
from docx import Document
from checker_parser import safe_input, parse_docx

sys.path.insert(0, str(ROOT/'c04'))
import c04_runtime

LIMIT = 32 * 1024 * 1024
BLOCKED = {
    'C09': 'NOT_RUN / NOT_VERIFIABLE: complete independent placement/program/preparation context is not supplied by this page.',
    'G06-A/B': 'NOT_RUN: no bound what-if request selected; inferred DV is not a measured heel.',
    'C10': 'NOT_RUN: no correction or DOCX-copy transaction selected.',
    'Advanced domains': 'NOT_VERIFIABLE: automatic Summary/Procedure, placement/excess/geothermal, complete measured Lab/rheology, Spacer formulation and CT stage cascades require further independent context.'}


def cement_admission(inputs, source_catalog):
    """Submission/schema admission only; accepted C02 still owns numeric validation."""
    job=inputs.get('job_type');mud=inputs.get('mud_type');active=inputs.get('active_fluids')
    if job not in source_catalog['jobs'] or mud not in ('WBM','OBM') or not isinstance(active,list) or not active:
        return {'status':'INPUT_INCOMPLETE','reason':'Explicit source job, mud and active selection required','roles':[]}
    if len(active)!=len(set(active)) or set(active)-set(source_catalog['eligible'][job][mud]):
        return {'status':'INPUT_REJECTED','reason':'Source eligibility rejects the active selection','roles':[]}
    roles=[f for f in active if f in source_catalog['cement_roles']]
    if not roles:
        return {'status':'NOT_APPLICABLE','reason':'No independently active cement formulation','roles':[]}
    cop=inputs.get('cement')
    if cop is None:
        return {'status':'INPUT_INCOMPLETE','reason':'Active cement formulation has not been completely submitted','roles':roles}
    if (type(cop) is not dict or set(cop)!={'job_type','active_fluids','slurries'} or cop['job_type']!=job
            or cop['active_fluids']!=active or type(cop['slurries']) is not dict or set(cop['slurries'])!=set(roles)):
        return {'status':'INPUT_REJECTED','reason':'C02 schema or selected job/fluid identity mismatch','roles':roles}
    for name in roles:
        item=cop['slurries'][name]
        if type(item) is not dict or set(item)!={'client_volume_bbl','density_pcf','base_cement','cement_sg','additives'}:
            return {'status':'INPUT_INCOMPLETE','reason':'Complete C02 formulation fields required for '+name,'roles':roles}
        if any(item[k] is None for k in item) or not item['base_cement'] or not isinstance(item['additives'],list):
            return {'status':'INPUT_INCOMPLETE','reason':'Missing independent C02 value for '+name,'roles':roles}
        if any(type(item[k]) not in (int,float) or not math.isfinite(item[k]) for k in ('client_volume_bbl','density_pcf','cement_sg')):
            return {'status':'INPUT_REJECTED','reason':'Finite typed independent C02 numbers required for '+name,'roles':roles}
    return {'status':'STRUCTURALLY_COMPLETE','reason':'Accepted source validation will run on explicit submission','roles':roles}


def report_identity(report):
    value=json.loads(json.dumps(report,allow_nan=False))
    value.pop('report_id',None);value['receipt'].pop('report_id',None)
    return digest(value)


def submission_revision(raw,name,inputs,draft):
    return digest({'document_sha256':sha256(raw).hexdigest(),'name':name,'inputs':inputs,'draft':draft})


def ascii_text(value):
    if value is None: return ''
    if isinstance(value, str): return value.encode('ascii', 'backslashreplace').decode()
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)


def clean_rows(rows):
    """UI empty cells remain absent, including pandas' empty numeric representation."""
    result = []
    for row in rows:
        item = {k: v for k, v in row.items() if v is not None and not
            (isinstance(v, float) and math.isnan(v)) and not (isinstance(v, str) and not v.strip())}
        if item: result.append(item)
    return result


def catalog():
    identities()
    process = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--catalog'],
        capture_output=True, text=True, cwd=ROOT, timeout=60,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT/'tmp'),
            XDG_CACHE_HOME=str(ROOT/'cache'), XDG_CONFIG_HOME=str(ROOT/'cache/config'), MPLCONFIGDIR=str(ROOT/'cache/mpl')))
    if process.returncode: raise Refusal('Pinned source catalog unavailable')
    return json.loads(process.stdout)


class PrivateSession:
    def __init__(self):
        identities()
        self.folder = Path(tempfile.mkdtemp(prefix='g07-', dir=ROOT/'c04/tmp'))
        self.session_id=uuid.uuid4().hex
        self.source_catalog=catalog()
        self.revision = None
        self.result = None
        self.document = None

    def folder_check(self):
        if (self.folder.resolve(strict=True) != self.folder or self.folder.parent != ROOT/'c04/tmp'
                or self.folder.is_symlink() or self.folder.stat().st_mode & 0o077):
            raise Refusal('Private session directory unavailable')
        identities()

    def invalidate(self, revision):
        changed = revision != self.revision
        if changed: self.result = None
        self.revision = revision
        return changed

    def current(self):
        if self.result is None: return None
        r=self.result;receipt=r['receipt']
        if (receipt['session_id']!=self.session_id or receipt['revision']!=self.revision
                or report_identity(r)!=r['report_id'] or identities()!=r['pins']
                or self.document is None or self.document.resolve()!=self.document
                or sha256(safe_input(self.document)).hexdigest()!=r['document_sha256']):
            self.result=None
            raise Refusal('Run/session/document receipt is stale or forged')
        return r

    def store(self, name, raw):
        self.folder_check()
        if (not isinstance(name, str) or '/' in name or '\\' in name or '\x00' in name
                or Path(name).suffix.lower() != '.docx' or not isinstance(raw, bytes)
                or not raw or len(raw) > LIMIT):
            raise Refusal('A regular DOCX of at most 32 MiB is required')
        path = self.folder/(sha256(raw).hexdigest()+'.docx')
        if path.is_symlink(): raise Refusal('Symlink input refused')
        if not path.exists():
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'wb') as out: out.write(raw)
        if path.resolve() != path or safe_input(path) != raw:
            raise Refusal('Original DOCX identity changed')
        parsed = parse_docx(path)
        if parsed['status'] != 'EXTRACTED_UNVERIFIED': raise Refusal('Malformed or unsupported DOCX structure')
        return path

    def check(self, path, inputs, revision=None, draft=None):
        self.folder_check(); path = Path(path)
        if path.parent != self.folder or path.resolve(strict=True) != path or path.is_symlink():
            raise Refusal('Input belongs to another session or escapes private storage')
        self.result=None
        if revision is not None and revision!=self.revision: raise Refusal('Submission revision is stale')
        original = safe_input(path); pins = identities(); input_sha = digest(inputs)
        submitted=json.loads(json.dumps(inputs,sort_keys=True,allow_nan=False))
        widget_snapshot=json.loads(json.dumps(draft,sort_keys=True,allow_nan=False)) if draft is not None else None
        admission=cement_admission(submitted,self.source_catalog)
        parsed = parse_docx(path)
        if parsed['status'] != 'EXTRACTED_UNVERIFIED': raise Refusal('DOCX structure rejected')
        results = {}; availability = dict(BLOCKED)
        cop = submitted.get('cement');completed=[];source_attempted=False
        if admission['status']=='STRUCTURALLY_COMPLETE':
            source_attempted=True
            try:
                baseline = c04_runtime.call({'action': 'baseline', 'docx': str(path), 'operator': cop})
            except ValueError:
                admission=dict(admission,status='INPUT_REJECTED',reason='Accepted C02/C03 source validation rejected the submitted formulation')
                availability['C02/C03']='INPUT_REJECTED'
            else:
                from c04_preview import bind
                bind(baseline,cop,sha256(original).hexdigest())
                results['C03'] = baseline
                availability['C02/C03'] = baseline['status']
                completed.extend(['C02','C03']);admission=dict(admission,status='SOURCE_ADMITTED')
        else: availability['C02/C03'] = admission['status']+': '+admission['reason']
        from c05_fluids import compare_document as fluids
        from c06_well import compare_document as well
        from c07_lab import compare_document as lab
        from c08_summary import compare_document as summary
        for name, key, compare in (('C05', 'fluids', fluids), ('C06', 'hardware', well),
                ('C07', 'lab', lab), ('C08', 'summary', summary)):
            if submitted.get(key) is None:
                availability[name] = 'NOT_RUN / NOT_VERIFIABLE: independent section inputs incomplete or not selected.'
                continue
            result = compare(path, submitted[key]); results[name] = result
            if result.get('source_document_sha256', sha256(original).hexdigest()) != sha256(original).hexdigest():
                raise Refusal('Adapter returned stale document evidence')
            availability[name] = result['status']
            if result['status']=='PARTIAL_FINDINGS_ONLY':completed.append(name)
        if identities() != pins or safe_input(path) != original or digest(inputs) != input_sha:
            raise Refusal('Document, independent inputs or source changed during checking')
        rejected=any(r['status']!='PARTIAL_FINDINGS_ONLY' for r in results.values())
        outcome=admission['status'] if admission['status'] in ('INPUT_INCOMPLETE','INPUT_REJECTED') else 'INPUT_REJECTED' if rejected else 'PARTIAL_FINDINGS_ONLY' if completed else 'CHECK_NOT_RUN'
        report = {'status': 'PARTIAL_FINDINGS_ONLY', 'run_outcome':outcome,'completed_adapters':completed,'document_sha256': sha256(original).hexdigest(),
            'operator_sha256': input_sha, 'pins': pins, 'results': results, 'availability': availability,
            'original_records': parsed['records'], 'docx_written': False, 'word_modified': False}
        report['rows'] = findings_table(results, parsed['records'])
        document = Document(BytesIO(original))
        for row in report['rows']:
            row['Message eligible'] = False
            loc = row['Judgments'][0]['finding'].get('locator')
            if loc is not None:
                try:
                    literal(document.element.body[loc['body_block']], document)
                except (ValueError, KeyError, IndexError):
                    row['Status'] += ' | UI: NOT_VERIFIABLE'
                    row['Reason/locator'] += ' Physical visibility is unproved; manual review required.'
                else: row['Message eligible'] = True
        report['receipt']={'run_id':uuid.uuid4().hex,'session_id':self.session_id,'revision':self.revision,
            'document_sha256':report['document_sha256'],'submission_sha256':input_sha,
            'inputs_snapshot':submitted,'widget_snapshot':widget_snapshot,
            'cement_operator_sha256':digest(cop) if cop is not None else None,
            'source_sha':pins['source_sha'],'cement_admission':admission,'cement_source_attempted':source_attempted,
            'C02_status':results.get('C03',{}).get('c02',{}).get('status','INPUT_REJECTED' if source_attempted else 'NOT_RUN'),
            'C03_status':results.get('C03',{}).get('status','INPUT_REJECTED' if source_attempted else 'NOT_RUN'),
            'sacks_findings':[f for f in results.get('C03',{}).get('c02',{}).get('findings',[]) if f['field']=='sacks']}
        report['message']=engineer_message(report)
        report['report_id']=report_identity(report);report['receipt']['report_id']=report['report_id']
        receipt_path=self.folder/('run-'+report['receipt']['run_id']+'.json')
        descriptor=os.open(receipt_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'w') as out:json.dump(report,out,allow_nan=False)
        self.document=path
        self.result = report
        return report


def findings_table(results, records=()):
    """One physical claim row; retain all overlapping judgments and full originals."""
    findings = []
    for adapter, result in results.items():
        if adapter == 'C03':
            findings.extend(('C02', f) for f in result['c02']['findings'])
            for f in result['water_findings']:
                findings.append(('C03', dict(f, field='preparation_water_and_inferred_DV', result=f['status'],
                    raw_reported_text=f.get('raw_text'), source_rounded_expected={k: f.get(k) for k in
                        ('Pure Mix Water Required', 'Total Preparation Water Reported in Word', 'Dead Volume Included by Engineer')})))
            for f in result['gross_additive_findings']:
                findings.append(('C03', dict(f, field='gross_additive.'+f['material'], result=f['status'],
                    raw_reported_text=f.get('raw_text'), source_rounded_expected=f.get('conservative_source_display_range'))))
        else: findings.extend((adapter, f) for f in result.get('findings', []))
        if result.get('status') != 'PARTIAL_FINDINGS_ONLY':
            findings.append((adapter, {'field': 'adapter_admission', 'result': result.get('status', 'NOT_VERIFIABLE'),
                'reason': result.get('reason', 'Adapter did not produce supported findings')}))
    groups = OrderedDict(); signatures = set()
    def excluded(f):
        return f.get('section') == 'excluded' or str(f.get('reported_state', '')).startswith('EXCLUDED') or 'iod' in str(f.get('field', '')).lower().split('.')
    for adapter, f in findings:
        if excluded(f): continue
        signature = digest([adapter, f])
        if signature in signatures: continue
        signatures.add(signature)
        loc = f.get('locator')
        # The enclosing report is bound to one immutable document. Some accepted
        # findings carry the document SHA only on their parent result.
        key = digest(loc) if loc is not None else digest([adapter, f.get('field'), signature])
        groups.setdefault(key, []).append({'adapter': adapter, 'finding': f})
    mapped = {digest(j['finding'].get('locator')) for judgments in groups.values() for j in judgments if j['finding'].get('locator') is not None}
    for record in records:
        if record.get('section') == 'excluded' or digest(record['locator']) in mapped: continue
        groups['raw:'+str(record['source_order'])] = [{'adapter': 'C01R', 'finding': dict(record,
            field=record.get('printed_label') or 'unmapped_claim', result='UNIMPLEMENTED',
            raw_reported_text=record['raw_text'], reason='Unmapped original structural claim; no executed adapter verified it')}]
    rows = []
    for judgments in groups.values():
        def values(key): return ' | '.join(dict.fromkeys(ascii_text(j['finding'].get(key)) for j in judgments))
        first = judgments[0]['finding']
        rows.append({'Section': values('section'), 'Fluid/Slurry': ' | '.join(dict.fromkeys(ascii_text(j['finding'].get('fluid') or j['finding'].get('slurry') or j['finding'].get('association')) for j in judgments)),
            'Field': values('field'), 'Word value': values('raw_reported_text'),
            'Expected/source value': ' | '.join(dict.fromkeys(ascii_text(j['finding'].get('source_rounded_expected', j['finding'].get('source_wording'))) for j in judgments)),
            'Delta/tolerance': ' | '.join(dict.fromkeys(ascii_text({'delta': j['finding'].get('delta'), 'tolerance': j['finding'].get('tolerance')}) for j in judgments)),
            'Status': ' | '.join(j['adapter']+': '+str(j['finding'].get('result', 'NOT_VERIFIABLE')) for j in judgments),
            'Reason/locator': values('reason')+' '+ascii_text(first.get('locator')), 'Judgments': judgments})
    return rows


def engineer_message(report):
    if not isinstance(report,dict):
        return 'NOT_VERIFIABLE: a run-bound report is required; review unverified/manual findings.'
    rows=report['rows'];outcome=report['run_outcome']
    if outcome=='CHECK_NOT_RUN':
        return 'CHECK_NOT_RUN: no comparison adapter completed. Supply independent inputs and run the check. Unverified items remain.'
    if outcome=='INPUT_INCOMPLETE':
        return 'INPUT_INCOMPLETE: active cement was not checked. Complete the independent formulation and resubmit. Findings from any unrelated completed checks remain partial.'
    if outcome=='INPUT_REJECTED':
        return 'INPUT_REJECTED: one or more submitted references were rejected. Correct independent inputs and resubmit. Any completed findings remain partial.'
    completed=set(report.get('completed_adapters',[]))
    if not completed:
        return 'CHECK_NOT_RUN: no comparison adapter completed. Supply independent inputs and run the check. Unverified items remain.'
    flagged=[row for row in rows if any(j['adapter'] in completed and
        j['finding'].get('result')=='DISCREPANCY' for j in row['Judgments'])]
    proven = []
    for row in flagged:
        if not row.get('Message eligible', False): continue
        judgments = row['Judgments']; findings = [j['finding'] for j in judgments]
        if not all(f.get('result') == 'DISCREPANCY' and f.get('locator') is not None
                and f.get('source_rounded_expected') is not None for f in findings): continue
        expected = {ascii_text(f['source_rounded_expected']) for f in findings}
        if len(expected) != 1 or any(j['adapter'] in ('C03', 'C01R') for j in judgments): continue
        value = next(iter(expected)); unit = ascii_text(findings[0].get('unit'))
        proven.append(f"- {row['Fluid/Slurry']} {row['Field']}: expected {value} {unit}.".strip())
    if not proven:
        if flagged:
            return 'The findings table flags discrepancies requiring manual review.\nNo exact replacement is suggested; confirm physical visibility, source evidence and overlapping judgments in the table. Unverified items remain. This is a partial check.'
        return 'No discrepancies detected in checks completed.\nUnverified and manual-review items remain; review the findings table. This is a partial check.'
    return 'Your program contains the following discrepancies:\n'+'\n'.join(proven[:5])+(
        '\nAdditional discrepancies are listed in the findings table.' if len(proven) > 5 else '')+(
        '\nAdditional table-flagged discrepancies require manual review; no exact replacements are suggested for those items.' if len(flagged)>len(proven) else '')+'\nUnverified and manual-review items are listed separately in the table. This is a partial check.'


if __name__ == '__main__' and sys.argv[1:] == ['--catalog']:
    identities()
    from engineering_source import install_audit, HARDWARE_FIELDS
    from c02_engine import verify_source, SNAPSHOT
    install_audit(); verify_source(); sys.path.insert(0, str(SNAPSHOT))
    import materials_db as db
    import project_state
    print(json.dumps({'jobs': db.JOB_TYPES, 'order': db.HYDRAULIC_EXECUTION_ORDER,
        'cement_roles': db.CEMENT_FORMULATION_FLUIDS, 'cement_names': [name for name in db.CEMENT_SG_REFERENCE],
        'hardware_fields': HARDWARE_FIELDS, 'hardware_descriptions': db.HARDWARE_DESCRIPTIONS,
        'eligible': {job: {mud: project_state.available_fluid_types({'job_type': job, 'mud_type': mud}) for mud in ('WBM', 'OBM')} for job in db.JOB_TYPES}}, allow_nan=False))
