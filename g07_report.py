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

from c10_corrections import ROOT, Refusal, digest, identities, literal, private_path
from docx import Document
from checker_parser import safe_input, parse_docx

sys.path.insert(0, str(ROOT/'c04'))
import c04_runtime

LIMIT = 32 * 1024 * 1024
BLOCKED = {
    'C09': 'NOT_RUN / NOT_VERIFIABLE: optional independent Procedure/NOTES context is not selected or complete.',
    'G06-A/B': 'NOT_RUN in this baseline check. G06-A and G06-B proposals use separate explicit previews. Inferred DV is not a measured heel.',
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

    def folder_check(self):
        if (self.folder.resolve(strict=True) != self.folder or self.folder.parent != ROOT/'c04/tmp'
                or self.folder.is_symlink() or self.folder.stat().st_mode & 0o077):
            raise Refusal('Private session directory unavailable')
        identities()

    def invalidate(self, revision):
        changed = revision != self.revision
        if changed:
            self.result = None
            self.volume_preview = None
            self.volume_request_sha = None
            self.dv_preview = None
            self.dv_request_sha = None
        self.revision = revision
        return changed

    def current(self):
        if self.result is None:
            self.volume_preview = None
            self.dv_preview = None
            return None
        r=self.result;receipt=r['receipt']
        if (receipt['session_id']!=self.session_id or receipt['revision']!=self.revision
                or report_identity(r)!=r['report_id'] or identities()!=r['pins']
                or self.document is None or self.document.resolve()!=self.document
                or sha256(safe_input(self.document)).hexdigest()!=r['document_sha256']):
            self.result=None
            self.volume_preview=None
            self.dv_preview=None
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

    def check(self, path, inputs, revision=None, draft=None):
        self.folder_check(); path = Path(path)
        if path.parent != self.folder or path.resolve(strict=True) != path or path.is_symlink():
            raise Refusal('Input belongs to another session or escapes private storage')
        self.result=None
        self.volume_preview=None
        self.dv_preview=None
        self.dv_request_sha=None
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
                from c09_procedure import compare_document as procedure_compare
                c09_operator_sha = digest(procedure)
                try:
                    result = procedure_compare(path, procedure)
                except (subprocess.TimeoutExpired, ValueError, OSError, KeyError, TypeError):
                    result = {'status': 'PARTIAL_FINDINGS_ONLY', 'findings': [{'field': 'procedure_and_notes',
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
                qualified = source and any(f.get('result') in ('MATCH', 'DISCREPANCY') for f in result.get('findings', []))
                c09_status = 'PARTIAL_FINDINGS_ONLY' if qualified else 'NOT_VERIFIABLE: no source-backed Procedure/NOTES comparison completed.'
                if qualified: completed.append('C09')
        availability['C09'] = c09_status
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
            'C09_operator_sha256':c09_operator_sha, 'C09_status':c09_status,
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
    import placement, well_profile, cement_chart_model
    from narrative_source import summary_reference
    # These validators expose no public enum constants; read their locked literals.
    def choices(function, member):
        return next(list(c) for c in function.__code__.co_consts if isinstance(c, tuple) and member in c)
    print(json.dumps({'jobs': db.JOB_TYPES, 'order': db.HYDRAULIC_EXECUTION_ORDER,
        'cement_roles': db.CEMENT_FORMULATION_FLUIDS, 'cement_names': [name for name in db.CEMENT_SG_REFERENCE],
        'hardware_fields': HARDWARE_FIELDS, 'hardware_descriptions': db.HARDWARE_DESCRIPTIONS,
        'eligible': {job: {mud: project_state.available_fluid_types({'job_type': job, 'mud_type': mud}) for mud in ('WBM', 'OBM')} for job in db.JOB_TYPES},
        'procedure': {'jobs': [job for job, kind in cement_chart_model.CHART_JOBS.items() if kind == 'casing'],
            'roles': db.PLACEMENT_SLURRIES, 'tanks': {job: db.get_available_tanks(job) for job in db.JOB_TYPES},
            'well_types': [v for v in choices(well_profile.validate_well_inputs, 'Vertical') if v is not None],
            'well_version': well_profile.geometry_defaults()['version'], 'summary_version': placement.SUMMARY_VERSION,
            'volume_bases': placement.VOLUME_BASES, 'top_modes': choices(summary_reference, 'Surface'),
            'manual_target': next(c for c in placement.target_depth.__code__.co_consts if c == '__manual__'),
            'excess_modes': choices(cement_chart_model.validate_chart_inputs, 'ignore'),
            'excess_fields': [(key, label) for key, label, _ in placement.EXCESS_FIELDS]}}, allow_nan=False))
