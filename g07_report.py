"""Private session intake and presentation of accepted Checker evidence; no formulas."""
from collections import OrderedDict
from contextlib import contextmanager
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from io import BytesIO
import subprocess
import sys
import tempfile
from threading import RLock
import uuid
from zipfile import BadZipFile

from c10_corrections import ROOT, Refusal, digest, identities, literal, private_path
from c10_delivery import locked, revoke
from docx import Document
from checker_parser import safe_input, parse_docx

sys.path.insert(0, str(ROOT/'c04'))
import c04_runtime

LIMIT = 32 * 1024 * 1024
BLOCKED = {
    'C09': 'NOT_RUN / NOT_VERIFIABLE: optional independent Procedure/NOTES context is not selected or complete.',
    'G06-A/B': 'NOT_RUN in this baseline check. G06-A and G06-B proposals use separate explicit previews. Inferred DV is not a measured heel.',
    'C10': 'NOT_RUN in this baseline check. Optional selective-copy transactions have separate receipts; no dependent program correction is credited.',
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


def standalone_spacer_input(inputs, context, source_catalog):
    """Schema/choice admission only; the original C05 source owns the solve."""
    def outcome(status, reason):
        return None, {'status': status, 'reason': reason}
    if type(context) is not dict or type(context.get('selected')) is not bool:
        return outcome('INPUT_REJECTED', 'Explicit configured-Spacer selection required')
    if not context['selected']:
        return outcome('NOT_RUN', 'Configured Standalone Spacer not selected')
    fields = {'mode', 'dead_vol', 'tank_name', 'limestone_available_lb', 'barite_available_lb'}
    if set(context) - fields - {'selected'}:
        return outcome('INPUT_REJECTED', 'Only original Standalone Spacer fields are permitted')
    job = inputs.get('job_type'); mud = inputs.get('mud_type'); active = inputs.get('active_fluids')
    if (job not in source_catalog['jobs'] or mud not in ('WBM', 'OBM') or type(active) is not list
            or 'Spacer' not in active or len(active) != len(set(active))
            or set(active) - set(source_catalog['eligible'][job][mud])):
        return outcome('INPUT_REJECTED', 'Configured Spacer requires a source-eligible active Spacer')
    if any(context.get(k) is None for k in ('mode', 'dead_vol', 'tank_name')):
        return outcome('INPUT_INCOMPLETE', 'Independent mode, Dead Volume and source tank required')
    if (context['mode'] not in source_catalog['standalone_spacer']['modes']
            or context['tank_name'] not in source_catalog['standalone_spacer']['tanks'][job]):
        return outcome('INPUT_REJECTED', 'Source mode or job-specific tank choice rejected')
    numbers = ['dead_vol']
    if context['mode'] == 'Limestone + Barite':
        numbers += ['limestone_available_lb', 'barite_available_lb']
    if any(context.get(k) is None for k in numbers):
        return outcome('INPUT_INCOMPLETE', 'Both independent Mix inventories are required')
    supplied_numbers = [k for k in ('dead_vol', 'limestone_available_lb', 'barite_available_lb') if context.get(k) is not None]
    if any(type(context[k]) not in (int, float) or not math.isfinite(context[k]) for k in supplied_numbers):
        return outcome('INPUT_REJECTED', 'Finite typed independent Spacer numbers required')
    config = {k: v for k, v in context.items() if k != 'selected'}
    return config, {'status': 'STRUCTURALLY_COMPLETE',
                    'reason': 'Original C05 validation runs on explicit Run Check; no formulation credited yet'}


def well_input(inputs, hardware, context, source_catalog, choices=None):
    """Bind optional source schemas; source C06 still owns validation/calculation."""
    status = {}
    if (not inputs.get('job_type') or not hardware or any('Description' not in r or 'MD (m)' not in r for r in hardware)):
        return None, {'hardware':'INPUT_INCOMPLETE'}
    job=inputs['job_type']; hop={'job_type':job,'hardware':hardware}; options=source_catalog['well']
    if context.get('geothermal_selected'):
        geo=context.get('well_geometry',{}); temp=context.get('geothermal_config',{})
        if (set(geo)-{'version','type','td_m'} or set(temp)-{'version','source','surface_temp','value'}
                or geo.get('type') not in (None,*options['types'])):
            status['geothermal']='NOT_VERIFIABLE: only explicit Vertical inputs; Survey excluded'
        elif any(v is None for v in (geo.get('type'),geo.get('td_m'),temp.get('source'),temp.get('surface_temp'),temp.get('value'))):
            status['geothermal']='INPUT_INCOMPLETE'
        elif (geo.get('version')!=options['geometry_version'] or temp.get('version')!=options['geothermal_version']
                or temp['source'] not in options['temperature_sources']
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in (geo['td_m'],temp['surface_temp'],temp['value']))):
            status['geothermal']='INPUT_REJECTED'
        else:
            hop.update(well_geometry=geo,geothermal_config=temp);status['geothermal']='SOURCE_VALIDATION_REQUIRED'
    if context.get('placement_selected'):
        config=context.get('placement_config',{}); target=config.get('target_row'); kind=options['chart_jobs'].get(job)
        candidates=choices['source']['reference']['source_hardware_choices'] if choices else {}
        if kind is None:status['placement']='NOT_VERIFIABLE: source chart excludes this job'
        elif context.get('well_geometry',{}).get('type')!='Vertical' or 'survey' in context.get('well_geometry',{}):
            status['placement']='NOT_VERIFIABLE: explicit independent Vertical designation required; Survey excluded'
        elif config.get('job_type')!=job or set(config)-set(options['placement_fields']):status['placement']='INPUT_REJECTED'
        elif target is None or config.get('chart_excess_mode') is None or target==source_catalog['procedure']['manual_target'] and config.get('manual_depth_m') is None or kind=='tieback' and config.get('host_row') is None:
            status['placement']='INPUT_INCOMPLETE'
        elif (config['chart_excess_mode'] not in source_catalog['procedure']['excess_modes']
                or target!=source_catalog['procedure']['manual_target'] and (target not in candidates or candidates[target]['description'] not in options['target_descriptions'][job])
                or config.get('host_row') is not None and config['host_row'] not in candidates):
            status['placement']='INPUT_REJECTED: current source-issued target/host required'
        else:hop['placement_config']=config;status['placement']='SOURCE_VALIDATION_REQUIRED / INFORMATIONAL ONLY'
    if context.get('fluids_selected'):
        fop=inputs.get('fluids')
        if fop is None:status['fluids']='INPUT_INCOMPLETE'
        else:hop.update(fluids=fop['fluids'],mud_type=inputs['mud_type']);status['fluids']='CURRENT_C05_ADMISSION_REQUIRED'
    return hop,status


def procedure_input(inputs, context, source_catalog):
    """Bind the optional UI subset to existing independent adapter inputs."""
    if not context.get('selected'):
        return None, BLOCKED['C09']
    options = source_catalog['procedure']; job = inputs.get('job_type')
    active = inputs.get('active_fluids', [])
    if job not in options['jobs'] or not active or set(active)-set(options['roles']):
        return None, 'NOT_RUN / NOT_VERIFIABLE: this C09 page supports ordinary casing cement roles only; other job/fluid NOTE contexts are not collected.'
    if context.get('well_type') != 'Vertical':
        return None, 'NOT_RUN / NOT_VERIFIABLE: this C09 page requires an independently selected Vertical well; directional survey context is not collected.'
    cop, fop, hop = (inputs.get(k) for k in ('cement', 'fluids', 'hardware'))
    if not cop or not fop or not hop or not context.get('no_additional_context'):
        return None, 'NOT_RUN / NOT_VERIFIABLE: complete independent cement, fluid rates, hardware and explicit summary-context choice are required.'
    if any(context.get(k) is None for k in ('td_m', 'geo_md', 'target_depth_m', 'target_mode', 'excess_mode')):
        return None, 'NOT_RUN / NOT_VERIFIABLE: independent well/MD/placement/excess inputs are incomplete.'
    if (context['target_mode'] != options['manual_target'] or context['excess_mode'] not in options['excess_modes']
            or set(context.get('roles', {})) != set(cop['slurries'])):
        return None, 'NOT_RUN / NOT_VERIFIABLE: source placement choices or exact active roles are unproved.'
    excess = context.get('excess', {})
    if context['excess_mode'] == 'apply' and any(excess.get(k) is None for k, _ in options['excess_fields']):
        return None, 'NOT_RUN / NOT_VERIFIABLE: explicit source excess percentages are incomplete.'
    tops = {}; preparation = {}; metadata = {}
    for role, item in context['roles'].items():
        if (item.get('top_mode') not in options['top_modes'] or item.get('volume_basis') not in options['volume_bases']
                or item.get('tank_name') not in options['tanks'][job]
                or any(item.get(k) is None for k in ('dead_volume_bbl', 'surface_hardened_hours'))
                or item.get('top_mode') != 'Surface' and item.get('top_depth') is None):
            return None, 'NOT_RUN / NOT_VERIFIABLE: per-role Top/basis/tank/DV/observed hours are incomplete.'
        tops[role] = {'top_job_type': job, 'top_mode': item['top_mode'],
                      'top_depth': 0 if item['top_mode'] == 'Surface' and item.get('top_depth') is None else item['top_depth']}
        metadata[role] = {'volume_basis': item['volume_basis']}
        preparation[role] = {k: item[k] for k in ('tank_name', 'dead_volume_bbl', 'surface_hardened_hours')}
    operator = {'program': {'job_type': job, 'geo_md': context['geo_md'],
        'hardware': hop['hardware'], 'fluids': fop['fluids'], 'cement_operator': cop,
        'placement_config': {'job_type': job, 'target_row': context['target_mode'],
                             'manual_depth_m': context['target_depth_m'], 'chart_excess_mode': context['excess_mode'], **excess},
        'tops': tops, 'executive_summary_config': {'version': options['summary_version'],
            'job_type': job, 'placement_context_rows': [], 'per_slurry': metadata}},
        'preparation': preparation, 'well_geometry': {'version': options['well_version'],
            'type': context['well_type'], 'td_m': context['td_m']}}
    if not procedure_identity(inputs, operator, source_catalog):
        return None, 'NOT_RUN / NOT_VERIFIABLE: independent job/fluid order/roles/quantities do not agree.'
    return operator, 'READY: accepted C09 source validation will run only on Run Check.'


def procedure_identity(inputs, operator, source_catalog):
    """No independently submitted program may cross the selected adapter identities."""
    try:
        p = operator['program']; job = inputs['job_type']; active = inputs['active_fluids']
        return (set(operator) == {'program', 'preparation', 'well_geometry'}
            and job in source_catalog['procedure']['jobs']
            and active == [n for n in source_catalog['order'] if n in active]
            and set(active) <= set(source_catalog['procedure']['roles'])
            and p['job_type'] == job == inputs['fluids']['job_type'] == inputs['hardware']['job_type']
            and p['cement_operator'] == inputs['cement'] and inputs['cement']['active_fluids'] == active
            and set(inputs['cement']['slurries']) == set(active) == set(p['fluids'])
            and p['fluids'] == inputs['fluids']['fluids'] and p['hardware'] == inputs['hardware']['hardware']
            and set(operator['preparation']) == set(active) and operator['well_geometry']['type'] == 'Vertical'
            and all(p['fluids'][n]['volume'] == inputs['cement']['slurries'][n]['client_volume_bbl']
                    and p['fluids'][n]['density'] == inputs['cement']['slurries'][n]['density_pcf'] for n in active))
    except (KeyError, TypeError):
        return False


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
        self._delivery_lock = RLock()
        identities()
        self.folder = Path(tempfile.mkdtemp(prefix='g07-', dir=ROOT/'c04/tmp'))
        self.session_id=uuid.uuid4().hex
        self.source_catalog=catalog()
        self.revision = None
        self.result = None
        self.document = None
        self.volume_preview = None
        self.volume_request_sha = None
        self.dv_preview = None
        self.dv_request_sha = None
        self.well_choices = None
        self._clear_copy()

    @locked
    def _clear_copy(self):
        revoke(self)
        self.copy_proposal = None
        self.copy_output = None
        self.copy_choice_sha = None

    def folder_check(self):
        if (self.folder.resolve(strict=True) != self.folder or self.folder.parent != ROOT/'c04/tmp'
                or self.folder.is_symlink() or self.folder.stat().st_mode & 0o077):
            raise Refusal('Private session directory unavailable')
        identities()

    @locked
    def inspect_hardware_choices(self, job, hardware):
        self.folder_check();self.well_choices=None
        from engineering_source import request
        operator=json.loads(json.dumps({'job_type':job,'hardware':hardware},allow_nan=False))
        pins=identities();source=request('well',operator)
        if (source['source_sha']!=pins['source_sha'] or source['operator_input_sha256']!=digest(operator)
                or digest(source['reference']['hardware'])!=digest(operator['hardware']) or identities()!=pins):
            raise Refusal('Hardware choice source identity rejected')
        value={'session_id':self.session_id,'operator':operator,'pins':pins,'source':source}
        value['choice_id']=digest(value)
        file=self.folder/('well-choices-'+value['choice_id']+'.json')
        if not file.exists():
            fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as out:json.dump(value,out,allow_nan=False)
        self.well_choices=value
        return self.current_hardware_choices(job,hardware)

    @locked
    def current_hardware_choices(self, job, hardware):
        self.folder_check();value=self.well_choices
        if value is None:return None
        key=value.get('choice_id');expected={k:v for k,v in value.items() if k!='choice_id'}
        if (type(key) is not str or len(key)!=64 or any(c not in '0123456789abcdef' for c in key)
                or value['session_id']!=self.session_id or value['pins']!=identities()
                or digest(value['operator'])!=digest({'job_type':job,'hardware':hardware})
                or digest(expected)!=key):
            self.well_choices=None;return None
        file=self.folder/('well-choices-'+key+'.json')
        if file.is_symlink() or file.stat().st_mode&0o077 or json.loads(file.read_text())!=value:
            self.well_choices=None;raise Refusal('Hardware choice receipt rejected')
        return value

    @locked
    def invalidate(self, revision):
        changed = revision != self.revision
        if changed:
            self.result = None
            self.volume_preview = None
            self.volume_request_sha = None
            self.dv_preview = None
            self.dv_request_sha = None
            self._clear_copy()
        self.revision = revision
        return changed

    @locked
    def current(self):
        if self.result is None:
            self.volume_preview = None
            self.dv_preview = None
            self._clear_copy()
            return None
        r=self.result;receipt=r['receipt']
        if (receipt['session_id']!=self.session_id or receipt['revision']!=self.revision
                or report_identity(r)!=r['report_id'] or identities()!=r['pins']
                or self.document is None or self.document.resolve()!=self.document
                or sha256(safe_input(self.document)).hexdigest()!=r['document_sha256']):
            self.result=None
            self.volume_preview=None
            self.dv_preview=None
            self._clear_copy()
            raise Refusal('Run/session/document receipt is stale or forged')
        return r

    def _preview_context(self, slurry):
        self.folder_check(); baseline = self.current()
        if baseline is None or baseline['run_outcome'] != 'PARTIAL_FINDINGS_ONLY':
            raise Refusal('CURRENT_ADMITTED_BASELINE_REQUIRED')
        if self.document.parent != self.folder or self.document.is_symlink() or self.document.stat().st_mode & 0o077:
            raise Refusal('OWNING_PRIVATE_BASELINE_DOCUMENT_REQUIRED')
        receipt = baseline['receipt']; operator = receipt['inputs_snapshot'].get('cement')
        c03 = baseline['results']['C03']; c02 = c03['c02']
        if (receipt['session_id'] != self.session_id or receipt['revision'] != self.revision
                or receipt['report_id'] != baseline['report_id']
                or receipt['document_sha256'] != baseline['document_sha256']
                or receipt['submission_sha256'] != baseline['operator_sha256']
                or digest(receipt['inputs_snapshot']) != receipt['submission_sha256']
                or receipt['cement_admission']['status'] != 'SOURCE_ADMITTED'
                or not {'C02', 'C03'} <= set(baseline['completed_adapters'])
                or receipt['C02_status'] != 'PARTIAL_FINDINGS_ONLY' or receipt['C03_status'] != 'PARTIAL_FINDINGS_ONLY'
                or c03['status'] != 'PARTIAL_FINDINGS_ONLY' or c02['status'] != 'PARTIAL_FINDINGS_ONLY'
                or c03['source_document_sha256'] != baseline['document_sha256']
                or c02['source_document_sha256'] != baseline['document_sha256']
                or c03['source_sha'] != baseline['pins']['source_sha']
                or c02['reference']['operator_input_sha256'] != receipt['cement_operator_sha256']
                or c02['reference']['operator_inputs'] != operator
                or operator is None or digest(operator) != receipt['cement_operator_sha256']):
            raise Refusal('CURRENT_ADMITTED_CEMENT_RECEIPT_REQUIRED')
        if (type(slurry) is not str or slurry not in self.source_catalog['procedure']['roles']
                or slurry not in operator['slurries'] or operator['active_fluids'].count(slurry) != 1):
            raise Refusal('EXACT_ACTIVE_ORDINARY_SLURRY_REQUIRED')
        return baseline, {'baseline_report_id': baseline['report_id'], 'session_id': self.session_id,
            'revision': self.revision, 'original_document_sha256': baseline['document_sha256'],
            'original_operator_sha256': receipt['cement_operator_sha256'], 'source_pins': baseline['pins'],
            'slurry': slurry}

    def _volume_context(self, slurry, volume):
        baseline, request = self._preview_context(slurry)
        if type(volume) not in (int, float) or not math.isfinite(volume) or volume <= 0:
            raise Refusal('FINITE_POSITIVE_PROPOSED_VOLUME_REQUIRED')
        return baseline, dict(request, proposed_client_volume_bbl=volume)

    def _copy_context(self):
        baseline = self.current()
        operator = baseline['receipt']['inputs_snapshot'].get('cement') if baseline else None
        roles = [n for n in self.source_catalog['order'] if n in (operator or {}).get('slurries', {})
            and n in self.source_catalog['procedure']['roles']]
        if not roles: raise Refusal('CURRENT_ADMITTED_ORDINARY_CEMENT_REQUIRED')
        baseline, request = self._preview_context(roles[0])
        # This chooses no correction: every proposal still needs individual consent.
        request.pop('slurry')
        return baseline, dict(request, ordinary_slurries=roles)

    @contextmanager
    def _copy_bridge(self, original):
        folder = Path(tempfile.mkdtemp(prefix='g07-c10-', dir=ROOT/'tmp'))
        identity = (folder.stat().st_dev, folder.stat().st_ino)
        source, output = folder/'input.docx', folder/'selected-copy.docx'
        try:
            if folder.resolve() != folder or folder.is_symlink() or folder.stat().st_mode & 0o077:
                raise Refusal('PRIVATE_C10_DIRECTORY_REQUIRED')
            private_path(source, existing=False)
            descriptor = os.open(source, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'wb') as out: out.write(original)
            if safe_input(private_path(source)) != original: raise Refusal('C10_INPUT_COPY_DRIFT')
            yield source, output
        finally:
            if folder.resolve() != folder or (folder.stat().st_dev, folder.stat().st_ino) != identity:
                raise Refusal('C10_CLEANUP_IDENTITY_DRIFT')
            for path in (source, output):
                if path.exists() or path.is_symlink(): path.unlink()
            folder.rmdir()  # Unexpected leftovers/cleanup faults must prevent download.

    def _copy_proof(self, proposal, baseline, request):
        if (proposal['schema'] != 'c10.1' or proposal['status'] != 'PARTIAL_FINDINGS_ONLY'
                or proposal['transaction_status'] != 'PREVIEW_ONLY'
                or proposal['bindings'] != dict(request['source_pins'],
                    original_document_sha256=request['original_document_sha256'], operator_sha256=request['original_operator_sha256'])
                or proposal['comparison_before'] != baseline['results']['C03']['c02']):
            raise Refusal('C10_SOURCE_COMPARISON_OR_BINDING_DRIFT')
        ids = [p['finding_id'] for p in proposal['proposals']]
        if len(ids) != len(set(ids)) or any(type(i) is not str or not i for i in ids):
            raise Refusal('C10_PROPOSAL_IDENTITY_NOT_PROVED')
        for item in proposal['proposals']:
            if (item['finding_id'] != digest({'bindings': proposal['bindings'],
                    'finding': {k:v for k,v in item.items() if k != 'finding_id'}})
                    or item['action'] == 'SELECTABLE' and (item['field'] not in ('yield','sacks')
                        or item['slurry'] not in request['ordinary_slurries'])):
                raise Refusal('C10_PROPOSAL_DRIFT')

    @locked
    def current_copy_proposals(self):
        try:
            baseline, request = self._copy_context(); value = self.copy_proposal
            if value is not None:
                if (value['receipt']['request'] != request or value['receipt']['request_sha256'] != digest(request)
                        or value['receipt']['proposal_sha256'] != digest(value['proposal'])
                        or value['proposal_id'] != digest({k:v for k,v in value.items() if k != 'proposal_id'})):
                    raise Refusal('C10_PROPOSAL_RECEIPT_DRIFT')
                self._copy_proof(value['proposal'], baseline, request)
            return value
        except (BadZipFile, ValueError, RuntimeError, OSError, KeyError, TypeError, ArithmeticError):
            self._clear_copy()
            raise Refusal('C10_PROPOSAL_NOT_VERIFIABLE') from None

    @locked
    def inspect_copy_proposals(self):
        self._clear_copy()
        try:
            baseline, request = self._copy_context(); before = digest(baseline)
            original = safe_input(self.document)
            operator = json.loads(json.dumps(baseline['receipt']['inputs_snapshot']['cement'], allow_nan=False))
            siblings = digest([self.volume_preview, self.dv_preview])
            from c10_corrections import propose
            with self._copy_bridge(original) as (source, _):
                proposal = propose(source, operator)
                self._copy_proof(proposal, baseline, request)
                if safe_input(private_path(source)) != original: raise Refusal('C10_INPUT_COPY_DRIFT')
            if (self._copy_context()[1] != request or digest(self.current()) != before
                    or safe_input(self.document) != original or digest(operator) != request['original_operator_sha256']
                    or digest([self.volume_preview, self.dv_preview]) != siblings):
                raise Refusal('C10_BASELINE_OR_SIBLING_DRIFT')
            value = {'status':'PARTIAL_FINDINGS_ONLY', 'receipt':{'inspection_run_id':uuid.uuid4().hex,
                'request':request, 'request_sha256':digest(request), 'proposal_sha256':digest(proposal)}, 'proposal':proposal}
            value['proposal_id'] = digest(value)
            receipt_path = self.folder/('c10-proposal-'+value['receipt']['inspection_run_id']+'.json')
            descriptor = os.open(receipt_path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'w') as out: json.dump(value, out, allow_nan=False)
            self.copy_proposal = value
            return self.current_copy_proposals()
        except subprocess.TimeoutExpired:
            self._clear_copy(); raise Refusal('C10_SOURCE_UNAVAILABLE') from None
        except (BadZipFile, ValueError, RuntimeError, OSError, KeyError, TypeError, ArithmeticError):
            self._clear_copy(); raise Refusal('C10_PROPOSAL_NOT_VERIFIABLE') from None

    def _copy_choice(self, selected_ids, confirmed):
        inspection = self.current_copy_proposals()
        if (inspection is None or type(selected_ids) is not list or not selected_ids
                or any(type(i) is not str for i in selected_ids)
                or len(selected_ids) != len(set(selected_ids)) or confirmed is not True):
            raise Refusal('EXPLICIT_C10_SELECTION_AND_CONSENT_REQUIRED')
        offers = inspection['proposal']['proposals']
        selected = [p for i in selected_ids for p in offers if p['finding_id'] == i and p['action'] == 'SELECTABLE']
        if len(selected) != len(selected_ids): raise Refusal('C10_SELECTION_NOT_PROVED')
        choice = {'proposal_id':inspection['proposal_id'], 'selected_ids':selected_ids, 'confirmed':True}
        return inspection, selected, choice

    @locked
    def current_created_copy(self, selected_ids, confirmed):
        try:
            inspection, selected, choice = self._copy_choice(selected_ids, confirmed)
            choice_sha = digest(choice)
            if choice_sha != self.copy_choice_sha:
                revoke(self)
                self.copy_output = None
            self.copy_choice_sha = choice_sha
            value = self.copy_output
            if value is not None and (value['receipt']['request'] != inspection['receipt']['request']
                    or value['receipt']['choice'] != choice
                    or value['receipt']['choice_sha256'] != choice_sha
                    or value['receipt']['output_sha256'] != sha256(value['bytes']).hexdigest()
                    or value['receipt']['transaction_sha256'] != digest(value['transaction'])
                    or value['transaction']['status'] != 'PARTIAL_FINDINGS_ONLY'
                    or value['transaction']['transaction_status'] != 'COPY_CREATED'
                    or value['transaction']['dependency_group_complete'] is not False
                    or value['transaction']['bindings'] != inspection['proposal']['bindings']
                    or value['transaction']['comparison_before'] != inspection['proposal']['comparison_before']
                    or value['transaction']['new_document_sha256'] != value['receipt']['output_sha256']
                    or value['transaction']['comparison_after']['source_document_sha256'] != value['receipt']['output_sha256']
                    or value['transaction']['selected'] != selected
                    or value['copy_id'] != digest({k:v for k,v in value.items() if k not in ('bytes','copy_id')})):
                raise Refusal('C10_COPY_RECEIPT_DRIFT')
            return value
        except (BadZipFile, ValueError, RuntimeError, OSError, KeyError, TypeError, ArithmeticError):
            revoke(self)
            self.copy_output = None; self.copy_choice_sha = None
            raise Refusal('C10_COPY_NOT_VERIFIABLE') from None

    @locked
    def create_selected_copy(self, selected_ids, confirmed):
        revoke(self)
        self.copy_output = None
        try:
            self.current_created_copy(selected_ids, confirmed)
            inspection, selected, choice = self._copy_choice(selected_ids, confirmed)
            baseline, request = self._copy_context(); before = digest(baseline)
            original = safe_input(self.document)
            operator = json.loads(json.dumps(baseline['receipt']['inputs_snapshot']['cement'], allow_nan=False))
            siblings = digest([self.volume_preview, self.dv_preview])
            selection = {'schema':'c10.1', 'bindings':inspection['proposal']['bindings'], 'selected':selected}
            from c10_corrections import apply, key
            with self._copy_bridge(original) as (source, output):
                private_path(output, existing=False)
                result = apply(source, operator, selection, output)
                if (result['status'] != 'PARTIAL_FINDINGS_ONLY' or result['transaction_status'] != 'COPY_CREATED'
                        or result['dependency_group_complete'] is not False or result['unchanged_package_parts'] is not True
                        or result['selected'] != selected or result['output_path'] != str(output)
                        or any(result[k] != v for k,v in inspection['proposal'].items() if k != 'transaction_status')
                        or result['unselected'] != [p for p in result['proposals'] if p not in selected]
                        or result['original_document_sha256'] != request['original_document_sha256']):
                    raise Refusal('C10_TRANSACTION_NOT_PROVED')
                data = safe_input(private_path(output))
                after = result['comparison_after']; old = result['comparison_before']
                if (sha256(data).hexdigest() != result['new_document_sha256']
                        or after['status'] != 'PARTIAL_FINDINGS_ONLY'
                        or after['source_document_sha256'] != result['new_document_sha256']
                        # C10 retains both call traces: the first includes cold imports.
                        # Every source identity/input/value must still be identical.
                        or {k:v for k,v in after['reference'].items() if k != 'source_calls'} != {
                            k:v for k,v in old['reference'].items() if k != 'source_calls'}
                        or not set(after['reference']['source_calls']) <= set(old['reference']['source_calls'])
                        or not {'engineering_tools.py:calculate_slurry_from_components',
                            'phase_5_cement.py:build_cement_tables', 'phase_10_procedure.py:_word_program_quantities',
                            'phase_7_lab.py:build_lab_df_from_phase5'} <= set(after['reference']['source_calls'])
                        or len(after['findings']) != len(old['findings'])):
                    raise Refusal('C10_RECHECK_IDENTITY_DRIFT')
                wanted = {digest(key(p)):p for p in selected}
                for a,b in zip(old['findings'], after['findings']):
                    chosen = wanted.get(digest(key(a)))
                    if (key(a) != key(b) or chosen is not None and (a['result'] != 'DISCREPANCY'
                            or b['result'] != 'MATCH' or b['raw_reported_text'] != chosen['replacement'])
                            or chosen is None and {k:v for k,v in a.items() if k != 'source_document_sha256'} != {
                                k:v for k,v in b.items() if k != 'source_document_sha256'}):
                        raise Refusal('C10_SELECTED_OR_UNSELECTED_RECHECK_FAILED')
                if safe_input(private_path(source)) != original: raise Refusal('C10_INPUT_COPY_DRIFT')
            if (self._copy_context()[1] != request or digest(self.current()) != before
                    or self._copy_choice(selected_ids, confirmed)[2] != choice or safe_input(self.document) != original
                    or digest(operator) != request['original_operator_sha256']
                    or digest([self.volume_preview, self.dv_preview]) != siblings):
                raise Refusal('C10_BASELINE_OR_SIBLING_DRIFT')
            # C10's transient output path is verified above and never disclosed.
            transaction = {k:v for k,v in result.items() if k != 'output_path'}
            value = {'status':'PARTIAL_FINDINGS_ONLY', 'receipt':{'copy_run_id':uuid.uuid4().hex,
                'request':request, 'choice':choice, 'choice_sha256':digest(choice),
                'transaction_sha256':digest(transaction), 'output_sha256':sha256(data).hexdigest()}, 'transaction':transaction}
            value['copy_id'] = digest(value)
            receipt_path = self.folder/('c10-copy-'+value['receipt']['copy_run_id']+'.json')
            descriptor = os.open(receipt_path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'w') as out: json.dump(value, out, allow_nan=False)
            self.copy_output = dict(value, bytes=data)
            return self.current_created_copy(selected_ids, confirmed)
        except subprocess.TimeoutExpired:
            revoke(self)
            self.copy_output = None; self.copy_choice_sha = None
            raise Refusal('C10_SOURCE_UNAVAILABLE') from None
        except (BadZipFile, ValueError, RuntimeError, OSError, KeyError, TypeError, ArithmeticError):
            revoke(self)
            self.copy_output = None; self.copy_choice_sha = None
            raise Refusal('C10_COPY_NOT_VERIFIABLE') from None

    def _dv_context(self, slurry, value):
        baseline, request = self._preview_context(slurry)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise Refusal('FINITE_NONNEGATIVE_EXPLICIT_DV_REQUIRED')
        return baseline, dict(request, corrected_dead_volume_bbl=value)

    def current_dead_volume_preview(self, slurry, value):
        try:
            _, request = self._dv_context(slurry, value)
            request_sha = digest(request)
            if request_sha != self.dv_request_sha:
                self.dv_preview = None
            self.dv_request_sha = request_sha
            preview = self.dv_preview
            if preview is not None and (preview['receipt']['request'] != request
                    or preview['receipt']['request_sha256'] != request_sha
                    or preview['receipt']['impact_sha256'] != digest(preview['impact'])
                    or preview['receipt']['g06b_bindings'] != preview['impact']['bindings']
                    or preview['preview_id'] != digest({k: v for k, v in preview.items() if k != 'preview_id'})):
                raise Refusal('STALE_OR_FORGED_DV_PREVIEW')
            return preview
        except (ValueError, OSError, KeyError, TypeError, ArithmeticError):
            self.dv_preview = None; self.dv_request_sha = None
            raise Refusal('DV_PREVIEW_NOT_VERIFIABLE') from None

    def preview_dead_volume(self, slurry, value):
        """Fresh G06-B proof on the owning original; no copy, formula or Word edit."""
        self.dv_preview = None
        try:
            self.current_dead_volume_preview(slurry, value)
            baseline, request = self._dv_context(slurry, value)
            baseline_sha = digest(baseline)
            operator = json.loads(json.dumps(baseline['receipt']['inputs_snapshot']['cement'], allow_nan=False))
            original = safe_input(self.document); pins = identities()
            volume_sha = digest(self.volume_preview)
            from g06b_dead_volume import inspect_selection, dead_volume_impact, private_path as dv_path
            path = dv_path(self.document, '.docx')
            inspection = inspect_selection(path, operator, slurry)
            if (inspection.get('schema') != 'g06b.1' or inspection.get('status') != 'PARTIAL_FINDINGS_ONLY'
                    or inspection.get('operation') != 'SELECTION_INSPECTION'
                    or inspection['original_c03'] != baseline['results']['C03']
                    or inspection['docx_written'] is not False or inspection['word_modified'] is not False):
                raise Refusal('G06B_SELECTION_NOT_VERIFIABLE')
            bindings = inspection['bindings']
            expected = dict(pins, original_document_sha256=request['original_document_sha256'],
                operator_sha256=request['original_operator_sha256'], selected_slurry=slurry,
                c03_sha256=digest(baseline['results']['C03']), selected_claims_sha256=digest(inspection['selected_claims']))
            if bindings != expected:
                raise Refusal('G06B_SELECTION_BINDING_DRIFT')
            edit = {'schema': 'g06b.1', 'bindings': bindings, 'slurry': slurry, 'corrected_dead_volume_bbl': value}
            impact = dead_volume_impact(path, operator, edit)
            if (impact.get('schema') != 'g06b.1' or impact.get('status') != 'PARTIAL_FINDINGS_ONLY'
                    or impact.get('operation') != 'EXPLICIT_DV_IMPACT' or impact['bindings'] != bindings
                    or impact['original_c03'] != baseline['results']['C03']
                    or impact['selected_claims'] != inspection['selected_claims']
                    or impact['docx_written'] is not False or impact['word_modified'] is not False
                    or impact['unresolved_dependencies'] != inspection['unresolved_dependencies']):
                raise Refusal('G06B_IMPACT_BINDING_DRIFT')
            c04 = impact['c04']; selected = c04['selected_dead_volume_preview']; ledger = impact['impact_ledger']
            if (c04['status'] != 'PARTIAL_FINDINGS_ONLY' or c04['schema'] != 'c04.1'
                    or c04['c03'] != baseline['results']['C03'] or c04['docx_written'] is not False
                    or c04['source_sha'] != pins['source_sha'] or c04['accepted_parent_sha256'] != c04_runtime.PINS
                    or c04['hashes']['original_document_sha256'] != request['original_document_sha256']
                    or c04['hashes']['new_document_sha256'] != request['original_document_sha256']
                    or c04['hashes']['original_operator_sha256'] != digest(operator)
                    or c04['hashes']['new_operator_sha256'] != digest(operator)
                    or c04['hashes']['edit_request_sha256'] != digest({'slurry': slurry, 'corrected_dead_volume_bbl': value})
                    or selected['slurry'] != slurry or selected['proposed_dead_volume_bbl'] != value
                    or selected['unaffected']['source_invariants_preserved'] is not True
                    or selected['unaffected']['base_reference'] != baseline['results']['C03']['c02']['reference']['slurries'][slurry]
                    or selected['unaffected']['unselected_slurry_references'] != {
                        k: v for k, v in baseline['results']['C03']['c02']['reference']['slurries'].items() if k != slurry}
                    or selected['unaffected']['raw_lab_findings_sha256_before'] != selected['unaffected']['raw_lab_findings_sha256_after']
                    or ledger['historical_exact_delta'] is not None or ledger['historical_change'] != 'NOT_VERIFIABLE'
                    or ledger['explicit_dead_volume_bbl'] != value
                    or ledger['before_dv_interval'] != selected['original_inferred_dead_volume']
                    or ledger['pure_mix_water_full_precision_bbl'] != selected['pure_mix_water_full_precision_bbl']
                    or ledger['source_after_total_preparation_water_full_precision_bbl'] != selected['new_preparation_water_full_precision_bbl']
                    or ledger['source_after_NOTE_display_bbl'] != selected['new_preparation_water_note_display_bbl']
                    or ledger['source_after_tables'] != selected['after_source_tables']
                    or ledger['source_invariants_and_unselected_slurries'] != selected['unaffected']
                    or len(ledger['gross_additives']) != len(selected['gross_additive_preview'])
                    or any(row['source_after_full_precision'] is not None or row['historical_exact_delta'] is not None
                        or row['source_after_display'] != source['after_source_display']
                        or row['original_Word_records'] != source['word_records']
                        for row, source in zip(ledger['gross_additives'], selected['gross_additive_preview']))):
                raise Refusal('G06B_SOURCE_OR_UNCERTAINTY_DRIFT')
            if (safe_input(dv_path(path, '.docx')) != original or identities() != pins
                    or digest(operator) != request['original_operator_sha256']
                    or self._dv_context(slurry, value)[1] != request or digest(self.current()) != baseline_sha
                    or digest(self.volume_preview) != volume_sha):
                raise Refusal('DV_PREVIEW_OR_BASELINE_CHANGED')
            preview = {'status': 'PARTIAL_FINDINGS_ONLY', 'receipt': {'preview_run_id': uuid.uuid4().hex,
                'request': request, 'request_sha256': digest(request), 'g06b_bindings': bindings,
                'impact_sha256': digest(impact)}, 'impact': impact}
            preview['preview_id'] = digest(preview)
            receipt_path = self.folder/('dv-preview-'+preview['receipt']['preview_run_id']+'.json')
            descriptor = os.open(receipt_path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'w') as out: json.dump(preview, out, allow_nan=False)
            self.dv_preview = preview
            return self.current_dead_volume_preview(slurry, value)
        except subprocess.TimeoutExpired:
            self.dv_preview = None; self.dv_request_sha = None
            raise Refusal('DV_SOURCE_UNAVAILABLE') from None
        except (ValueError, RuntimeError, OSError, KeyError, TypeError, ArithmeticError):
            self.dv_preview = None; self.dv_request_sha = None
            raise Refusal('DV_PREVIEW_NOT_VERIFIABLE') from None

    def current_volume_preview(self, slurry, volume):
        try:
            _, request = self._volume_context(slurry, volume)
            request_sha = digest(request)
            if request_sha != self.volume_request_sha:
                self.volume_preview = None
            self.volume_request_sha = request_sha
            preview = self.volume_preview
            if preview is not None and (preview['receipt']['request'] != request
                    or preview['receipt']['request_sha256'] != request_sha
                    or preview['receipt']['impact_sha256'] != digest(preview['impact'])
                    or preview['receipt']['g06a_bindings'] != preview['impact']['bindings']
                    or preview['preview_id'] != digest({k: v for k, v in preview.items() if k != 'preview_id'})):
                raise Refusal('STALE_OR_FORGED_VOLUME_PREVIEW')
            return preview
        except (ValueError, OSError, KeyError, TypeError):
            self.volume_preview = None; self.volume_request_sha = None
            raise Refusal('VOLUME_PREVIEW_NOT_VERIFIABLE') from None

    def preview_volume(self, slurry, volume):
        """Fresh G06-A inspection through an identical, short-lived private copy."""
        self.volume_preview = None
        self.current_volume_preview(slurry, volume)
        baseline, request = self._volume_context(slurry, volume)
        baseline_sha = digest(baseline)
        operator = json.loads(json.dumps(baseline['receipt']['inputs_snapshot']['cement'], allow_nan=False))
        original = safe_input(self.document); pins = identities()
        if sha256(original).hexdigest() != request['original_document_sha256']:
            raise Refusal('ORIGINAL_DOCUMENT_IDENTITY_DRIFT')
        folder = Path(tempfile.mkdtemp(prefix='g07-volume-', dir=ROOT/'tmp'))
        folder_identity = (folder.stat().st_dev, folder.stat().st_ino)
        copy_path = folder/'input.docx'
        try:
            if folder.resolve() != folder or folder.stat().st_mode & 0o077:
                raise Refusal('PRIVATE_PREVIEW_DIRECTORY_REQUIRED')
            private_path(copy_path, existing=False)
            descriptor = os.open(copy_path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'wb') as out: out.write(original)
            if safe_input(private_path(copy_path)) != original:
                raise Refusal('PREVIEW_COPY_IDENTITY_DRIFT')
            from g06a_client_volume import inspect_reference, volume_impact
            inspection = inspect_reference(copy_path, operator, slurry)
            if (inspection.get('schema') != 'g06a.1' or inspection.get('status') != 'PARTIAL_FINDINGS_ONLY'
                    or inspection.get('operation') != 'REFERENCE_INSPECTION_ONLY'):
                raise Refusal('G06A_PHYSICAL_REFERENCE_NOT_VERIFIABLE')
            bindings = inspection['bindings']
            if (any(bindings.get(k) != v for k, v in pins.items())
                    or bindings['original_document_sha256'] != request['original_document_sha256']
                    or bindings['original_operator_sha256'] != request['original_operator_sha256']
                    or bindings['original_reference_sha256'] != digest(baseline['results']['C03']['c02']['reference']['slurries'])
                    or bindings['selected_slurry'] != slurry):
                raise Refusal('G06A_INSPECTION_BINDING_DRIFT')
            edit = {'schema': 'g06a.1', 'bindings': bindings, 'slurry': slurry, 'client_volume_bbl': volume}
            impact = volume_impact(copy_path, operator, edit)
            expected = json.loads(json.dumps(operator)); expected['slurries'][slurry]['client_volume_bbl'] = volume
            if (impact.get('schema') != 'g06a.1' or impact.get('status') != 'PARTIAL_FINDINGS_ONLY'
                    or impact.get('operation') != 'CLIENT_VOLUME_REFERENCE_IMPACT'
                    or impact['bindings'] != bindings or impact['edit_request_sha256'] != digest(edit)
                    or impact['edited_operator_reference'] != expected or impact['edited_operator_sha256'] != digest(expected)
                    or impact['edited_comparison']['reference']['operator_input_sha256'] != digest(expected)
                    or impact['original_comparison']['reference']['operator_input_sha256'] != request['original_operator_sha256']
                    or impact['original_document_sha256'] != request['original_document_sha256']
                    or impact['unchanged_document_sha256'] != request['original_document_sha256']
                    or impact['docx_written'] is not False or impact['word_modified'] is not False
                    or impact['invariants'] != {'yield_and_calculated_600ml_recipe': True, 'other_slurries': True, 'measured_results_refreshed': False}):
                raise Refusal('G06A_IMPACT_IDENTITY_OR_INVARIANT_DRIFT')
            if (safe_input(private_path(copy_path)) != original or safe_input(self.document) != original
                    or identities() != pins or digest(operator) != request['original_operator_sha256']
                    or self._volume_context(slurry, volume)[1] != request or digest(self.current()) != baseline_sha):
                raise Refusal('BASELINE_OR_PREVIEW_COPY_CHANGED')
        finally:
            if folder.resolve() != folder or (folder.stat().st_dev, folder.stat().st_ino) != folder_identity:
                raise Refusal('PREVIEW_DIRECTORY_IDENTITY_DRIFT')
            if copy_path.exists() or copy_path.is_symlink(): copy_path.unlink()
            folder.rmdir()
        preview = {'status': 'PARTIAL_FINDINGS_ONLY', 'receipt': {'preview_run_id': uuid.uuid4().hex,
            'request': request, 'request_sha256': digest(request), 'g06a_bindings': bindings,
            'impact_sha256': digest(impact)}, 'impact': impact}
        preview['preview_id'] = digest(preview)
        path = self.folder/('volume-preview-'+preview['receipt']['preview_run_id']+'.json')
        descriptor = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'w') as out: json.dump(preview, out, allow_nan=False)
        self.volume_preview = preview
        return self.current_volume_preview(slurry, volume)

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

    @locked
    def check(self, path, inputs, revision=None, draft=None):
        self.folder_check(); path = Path(path)
        if path.parent != self.folder or path.resolve(strict=True) != path or path.is_symlink():
            raise Refusal('Input belongs to another session or escapes private storage')
        self.result=None
        self.volume_preview=None
        self.dv_preview=None
        self.dv_request_sha=None
        self._clear_copy()
        if revision is not None and revision!=self.revision: raise Refusal('Submission revision is stale')
        original = safe_input(path); pins = identities(); input_sha = digest(inputs)
        submitted=json.loads(json.dumps(inputs,sort_keys=True,allow_nan=False))
        widget_snapshot=json.loads(json.dumps(draft,sort_keys=True,allow_nan=False)) if draft is not None else None
        spacer_admission = None
        fop = submitted.get('fluids')
        spacer_context = widget_snapshot.get('standalone_spacer') if widget_snapshot is not None else None
        if spacer_context is None and type(fop) is dict and type(fop.get('standalone_spacer')) is dict:
            spacer_context = dict(fop['standalone_spacer'], selected=True)
        if spacer_context is not None:
            config, spacer_admission = standalone_spacer_input(submitted, spacer_context, self.source_catalog)
            if fop is not None and type(fop) is not dict:
                raise Refusal('C05 requires an independent fluid operator')
            if fop is not None and digest(fop.get('standalone_spacer')) != digest(config):
                raise Refusal('C05 configuration does not match the committed independent draft')
            if spacer_context.get('selected') and fop is not None:
                if (fop['job_type'] != submitted['job_type'] or fop.get('mud_type', submitted['mud_type']) != submitted['mud_type']
                        or set(fop['fluids']) != set(submitted['active_fluids'])
                        or widget_snapshot is not None and 'fluid_inputs' in widget_snapshot
                        and digest(fop['fluids']) != digest(widget_snapshot['fluid_inputs'])):
                    raise Refusal('C05 fluid identities do not match the independent selection/draft')
            if config is not None and fop is None:
                spacer_admission = {'status': 'INPUT_INCOMPLETE', 'reason': 'Independent general fluid inputs are incomplete'}
            if spacer_admission['status'] == 'NOT_RUN': spacer_admission = None
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
            lab_reason = None
            if name == 'C06':
                hop=submitted[key]
                if type(hop) is not dict or hop.get('job_type')!=submitted['job_type']:
                    lab_reason='C06 job must match the current independent selection'
                elif 'well_geometry' in hop and (hop['well_geometry'].get('type')!='Vertical' or 'survey' in hop['well_geometry']):
                    lab_reason='C06 intake is Vertical only; Survey and directional geometry are excluded'
                elif 'placement_config' in hop and self.source_catalog['well']['chart_jobs'].get(submitted['job_type']) is None:
                    lab_reason='No source chart mapping for this job; no casing substitution'
                elif 'placement_config' in hop and (hop.get('well_geometry',{}).get('type')!='Vertical'
                        and (widget_snapshot or {}).get('well_context',{}).get('well_geometry',{}).get('type')!='Vertical'):
                    lab_reason='Explicit independent Vertical designation required for placement; no directional assumption'
                elif 'fluids' in hop:
                    c05=results.get('C05',{});ref=c05.get('reference',{})
                    if (c05.get('status')!='PARTIAL_FINDINGS_ONLY' or type(fop) is not dict
                            or fop.get('job_type')!=submitted['job_type'] or fop.get('mud_type','WBM')!=submitted['mud_type']
                            or hop.get('mud_type','WBM')!=submitted['mud_type'] or set(fop['fluids'])!=set(submitted['active_fluids'])
                            or digest(hop['fluids'])!=digest(fop['fluids']) or ref.get('source_sha')!=pins['source_sha']
                            or ref.get('operator_input_sha256')!=digest(fop)):
                        lab_reason='C06 volume projection requires the exact current source-admitted C05 fluids'
                if not lab_reason and type(hop) is dict and 'placement_config' in hop:
                    config=hop['placement_config'];token=config.get('target_row');host=config.get('host_row')
                    if token not in (None,self.source_catalog['procedure']['manual_target']) or host is not None:
                        choice=self.current_hardware_choices(submitted['job_type'],hop['hardware'])
                        allowed=choice['source']['reference']['source_hardware_choices'] if choice else {}
                        if (token!=self.source_catalog['procedure']['manual_target'] and token not in allowed or host is not None and host not in allowed):
                            lab_reason='Current source-issued Hardware target/host inspection required'
                if not lab_reason and widget_snapshot is not None and 'well_context' in widget_snapshot:
                    rows=widget_snapshot.get('hardware',[]);choice=self.current_hardware_choices(submitted['job_type'],rows)
                    expected,_=well_input(submitted,rows,widget_snapshot['well_context'],self.source_catalog,choice)
                    if widget_snapshot.get('hardware_on') is not True or digest(hop)!=digest(expected):
                        lab_reason='C06 operator must match the complete committed Hardware/Well draft'
            if name == 'C07':
                lop = submitted[key]
                if (type(lop) is not dict or lop.get('job_type') != submitted['job_type']
                        or lop.get('mud_type', 'WBM') != submitted['mud_type']
                        or lop.get('active_fluids') != submitted['active_fluids']):
                    lab_reason = 'Lab job, mud and active identities must match this run'
                elif 'cement_operator' in lop and (admission['status'] != 'SOURCE_ADMITTED'
                        or digest(lop['cement_operator']) != digest(cop)):
                    lab_reason = 'Lab recipe requires the exact current source-admitted C02 operator'
                elif 'spacer_operator' in lop and (not spacer_admission
                        or spacer_admission['status'] != 'SOURCE_ADMITTED'
                        or digest(lop['spacer_operator']) != digest(fop)):
                    lab_reason = 'Spacer sample requires the exact current source-admitted configured C05 operator'
                elif widget_snapshot is not None and 'lab_confirmed' in widget_snapshot:
                    if (widget_snapshot.get('lab_on') is not True
                            or digest(lop.get('measurements')) != digest(widget_snapshot.get('measurements'))
                            or digest(lop.get('conditions', {})) != digest(widget_snapshot.get('conditions'))
                            or type(lop.get('confirmed', False)) is not bool
                            or lop.get('confirmed', False) != widget_snapshot['lab_confirmed']
                            or set(lop.get('measurements', {})) != set(widget_snapshot.get('measured_fluids', []))):
                        lab_reason = 'Lab observations and confirmation must match the committed independent draft'
            result = ({'status':'INPUT_REJECTED','reason':lab_reason,'findings':[]} if lab_reason
                      else compare(path, submitted[key]))
            results[name] = result
            if name == 'C06' and result['status']=='PARTIAL_FINDINGS_ONLY':
                source=result['reference'];geometry=source['reference']['geometry']
                claims=[f for f in result['findings'] if f['field']=='geometry.reference']
                if (source['source_sha']!=pins['source_sha'] or source['operator_input_sha256']!=digest(submitted[key])
                        or digest(source['reference']['hardware'])!=digest(submitted[key]['hardware'])
                        or len(claims)!=1 or claims[0]['result']!=geometry['status']
                        or geometry['status'] not in ('INFORMATIONAL','NOT_VERIFIABLE')):
                    raise Refusal('C06 source/input identity or informational geometry is unproved')
            if name == 'C07' and result['status'] == 'PARTIAL_FINDINGS_ONLY':
                source = result['reference']
                if (source['source_sha'] != pins['source_sha'] or source['operator_input_sha256'] != digest(submitted[key])
                        or source['reference']['template_sha256'] != pins['template_sha256']):
                    raise Refusal('C07 source/operator/template identity is unproved')
            if name == 'C05' and type(fop) is dict and fop.get('standalone_spacer') is not None:
                if result['status'] == 'PARTIAL_FINDINGS_ONLY':
                    source = result['reference']
                    if (source['source_sha'] != pins['source_sha'] or source['operator_input_sha256'] != digest(fop)
                            or source['reference']['spacer'] is None):
                        raise Refusal('C05 configured source identity is unproved')
                    spacer_admission = {'status': 'SOURCE_ADMITTED', 'reason': 'Original C05 Standalone Spacer source accepted the submitted configuration',
                                        'operator_sha256': digest(fop)}
                else:
                    spacer_admission = {'status': 'INPUT_REJECTED', 'reason': 'Original C05 source rejected the configured formulation'}
            if result.get('source_document_sha256', sha256(original).hexdigest()) != sha256(original).hexdigest():
                raise Refusal('Adapter returned stale document evidence')
            availability[name] = result['status']
            if result['status']=='PARTIAL_FINDINGS_ONLY':completed.append(name)
        procedure = submitted.get('procedure')
        c09_status = BLOCKED['C09']; c09_operator_sha = None
        if widget_snapshot is not None and 'procedure' in widget_snapshot:
            expected, c09_status = procedure_input(submitted, widget_snapshot['procedure'], self.source_catalog)
            if expected != procedure:
                raise Refusal('C09 submitted operator does not match the committed independent draft')
        if procedure is not None:
            if admission['status'] != 'SOURCE_ADMITTED' or not procedure_identity(submitted, procedure, self.source_catalog):
                c09_status = 'NOT_RUN / NOT_VERIFIABLE: C09 requires matching, source-admitted independent cement/fluid/hardware inputs.'
            else:
                from c09_procedure import compare_document as procedure_compare, stage_availability
                c09_operator_sha = digest(procedure)
                try:
                    result = procedure_compare(path, procedure)
                except (subprocess.TimeoutExpired, ValueError, OSError, KeyError, TypeError):
                    result = {'status': 'NOT_VERIFIABLE', 'availability':stage_availability(procedure,{},[]),
                        'findings': [{'field': 'procedure_and_notes',
                        'locator': None, 'result': 'NOT_VERIFIABLE',
                        'reason': 'C09 source reference timed out, was unavailable or rejected; no Procedure/NOTES comparison is credited.'}]}
                for finding in result.get('findings', []):
                    if finding.get('field') == 'procedure_and_notes' and not finding.get('source_function'):
                        finding['reason'] = 'C09 source reference or physical narrative association is unproved; manual review required.'
                source = result.get('reference', {})
                if source and (source.get('source_sha') != pins['source_sha'] or source.get('operator_input_sha256') != c09_operator_sha):
                    raise Refusal('C09 source/operator identity drift')
                if result.get('source_document_sha256', sha256(original).hexdigest()) != sha256(original).hexdigest():
                    raise Refusal('C09 document identity drift')
                results['C09'] = result
                qualified = source and result['status']=='PARTIAL_FINDINGS_ONLY' and any(
                    f.get('locator') is not None and f.get('result') in ('MATCH', 'DISCREPANCY') for f in result.get('findings', []))
                c09_status = 'PARTIAL_FINDINGS_ONLY' if qualified else 'NOT_VERIFIABLE: no source-backed Procedure/NOTES comparison completed.'
                if qualified: completed.append('C09')
        availability['C09'] = c09_status
        if spacer_admission is not None:
            availability['Configured Standalone Spacer'] = spacer_admission['status'] + ': ' + spacer_admission['reason']
        if identities() != pins or safe_input(path) != original or digest(inputs) != input_sha:
            raise Refusal('Document, independent inputs or source changed during checking')
        # Optional unverified C09 does not erase independently valid adapters.
        rejected=any(r['status']!='PARTIAL_FINDINGS_ONLY' for name,r in results.items()
            if not(name=='C09' and r['status']=='NOT_VERIFIABLE'))
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
            'C09_operator_sha256':c09_operator_sha, 'C09_status':c09_status,
            'C09_stage_availability':results.get('C09',{}).get('availability'),
            'sacks_findings':[f for f in results.get('C03',{}).get('c02',{}).get('findings',[]) if f['field']=='sacks']}
        if spacer_admission is not None:
            report['receipt']['standalone_spacer_admission'] = spacer_admission
        if 'C07' in results:
            lab_result = results['C07']
            report['receipt']['lab_admission'] = {
                'status': 'SOURCE_ADMITTED_PARTIAL_REFERENCE' if lab_result['status'] == 'PARTIAL_FINDINGS_ONLY' else 'INPUT_REJECTED',
                'operator_sha256': digest(submitted['lab']),
                'payload_admitted_by_fluid': {fluid: item['payload_admitted'] for fluid, item in
                    lab_result.get('reference', {}).get('reference', {}).get('fluids', {}).items()}}
        if 'C06' in results:
            result=results['C06']
            report['receipt']['well_admission']={'status':'SOURCE_ADMITTED_PARTIAL_REFERENCE' if result['status']=='PARTIAL_FINDINGS_ONLY' else 'INPUT_REJECTED',
                'operator_sha256':digest(submitted['hardware']),
                'geometry_status':result.get('reference',{}).get('reference',{}).get('geometry',{}).get('status','NOT_RUN')}
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
    import standalone_spacer
    import engineering_tools, rheology
    import placement, well_profile, cement_chart_model
    from narrative_source import summary_reference
    # These validators expose no public enum constants; read their locked literals.
    def choices(function, member):
        return next(list(c) for c in function.__code__.co_consts if isinstance(c, tuple) and member in c)
    print(json.dumps({'jobs': db.JOB_TYPES, 'order': db.HYDRAULIC_EXECUTION_ORDER,
        'cement_roles': db.CEMENT_FORMULATION_FLUIDS, 'cement_names': [name for name in db.CEMENT_SG_REFERENCE],
        'hardware_fields': HARDWARE_FIELDS, 'hardware_descriptions': db.HARDWARE_DESCRIPTIONS,
        'well': {'types':[v for v in choices(well_profile.validate_well_inputs,'Vertical') if v=='Vertical'],
            'geometry_version':well_profile.geometry_defaults()['version'], 'geothermal_version':well_profile.geothermal_defaults()['version'],
            'temperature_sources':[v for v in choices(well_profile.validate_well_inputs,'BHST') if v is not None],
            'chart_jobs':cement_chart_model.CHART_JOBS,
            'target_descriptions':{job:sorted(placement.target_descriptions(job)) for job in db.JOB_TYPES},
            'descriptions_by_job':{job:list(db.HARDWARE_DESCRIPTIONS)+sorted(placement.target_descriptions(job)-set(db.HARDWARE_DESCRIPTIONS)) if job==db.CT_JOB else list(db.HARDWARE_DESCRIPTIONS) for job in db.JOB_TYPES},
            'placement_fields':['job_type','target_row','manual_depth_m','chart_excess_mode',*(f for f,_,_ in placement.EXCESS_FIELDS),'host_row','tie_back_liner_lap_m']},
        'eligible': {job: {mud: project_state.available_fluid_types({'job_type': job, 'mud_type': mud}) for mud in ('WBM', 'OBM')} for job in db.JOB_TYPES},
        'standalone_spacer': {'modes': list(standalone_spacer.MODES),
            'tanks': {job: db.get_available_tanks(job) for job in db.JOB_TYPES}},
        'lab': {'roles': [*db.PHASE7_LAB_FLUIDS, 'Spacer'], 'ordinary_roles': list(db.PLACEMENT_SLURRIES),
            'datasets': list(rheology.RHEOLOGY_DATASETS), 'rpm_order': list(rheology.RPM_ORDER),
            'thickening_fields': list(engineering_tools.THICKENING_TEST_FIELDS),
            'compressive_fields': engineering_tools.COMPRESSIVE_TEST_FIELDS},
        'procedure': {'jobs': [job for job, kind in cement_chart_model.CHART_JOBS.items() if kind == 'casing'],
            'roles': db.PLACEMENT_SLURRIES, 'tanks': {job: db.get_available_tanks(job) for job in db.JOB_TYPES},
            'well_types': [v for v in choices(well_profile.validate_well_inputs, 'Vertical') if v is not None],
            'well_version': well_profile.geometry_defaults()['version'], 'summary_version': placement.SUMMARY_VERSION,
            'volume_bases': placement.VOLUME_BASES, 'top_modes': choices(summary_reference, 'Surface'),
            'manual_target': next(c for c in placement.target_depth.__code__.co_consts if c == '__manual__'),
            'excess_modes': choices(cement_chart_model.validate_chart_inputs, 'ignore'),
            'excess_fields': [(key, label) for key, label, _ in placement.EXCESS_FIELDS]}}, allow_nan=False))
