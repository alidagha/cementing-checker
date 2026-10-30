"""G01 isolated calls to locked App authorities; no engineering formulas here."""
import hashlib
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / 'snapshot'
sys.path.insert(0, str(ROOT / 'c02'))
from c02_engine import SOURCE_SHA, read_json, verify_source


def request(action, operator, **kwargs):
    """Execute only in a provisioned private runtime, never a public checkout."""
    if not SNAPSHOT.is_dir() or any((p / '.git').exists() for p in (ROOT, *ROOT.parents)):
        raise ValueError('A separate provisioned, Git-free runtime is required')
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / 'tmp'),
        XDG_CACHE_HOME=str(ROOT / 'cache'), XDG_CONFIG_HOME=str(ROOT / 'cache/config'),
        MPLCONFIGDIR=str(ROOT / 'cache/mpl'))
    try:
        process = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve())],
            input=json.dumps(dict(action=action, operator=operator, **kwargs), allow_nan=False),
            text=True, capture_output=True, cwd=ROOT, env=environment, timeout=90)
    except subprocess.TimeoutExpired as error:
        raise ValueError('Source subprocess time limit') from error
    if process.returncode:
        raise ValueError('Source subprocess failed: ' + process.stderr[-500:])
    result = read_json(process.stdout)
    if 'error' in result:
        raise ValueError(result['error'])
    if result.get('source_sha') != SOURCE_SHA:
        raise ValueError('Source SHA drift')
    return result


def fluid_reference(operator):
    import materials_db as db
    import project_state as state_source
    import standalone_spacer as spacer
    import phase_10_procedure as report
    allowed = {'job_type', 'fluids', 'mud_type', 'standalone_spacer'}
    if not isinstance(operator, dict) or set(operator) - allowed or not {'job_type', 'fluids'} <= set(operator):
        raise ValueError('Expected job_type and independent fluids; optional mud_type/standalone_spacer')
    if operator['job_type'] not in db.JOB_TYPES or not isinstance(operator['fluids'], dict):
        raise ValueError('Unknown source job or invalid fluid inputs')
    fluids = operator['fluids']
    if not fluids or set(fluids) - set(db.HYDRAULIC_EXECUTION_ORDER):
        raise ValueError('Unknown/empty active fluid selection')
    if 'Diesel' in fluids and operator.get('mud_type') not in ('WBM', 'OBM'):
        raise ValueError('Independent mud_type required to establish Diesel applicability')
    for name, values in fluids.items():
        if not isinstance(values, dict) or set(values) - {'volume', 'density', 'pump_rate', 'material_name'} or not {'volume', 'density', 'pump_rate'} <= set(values):
            raise ValueError('Explicit volume/density/pump_rate required for each active fluid')
        # Source accepts ranges for density/rate; booleans are not measurements.
        if any(isinstance(values[k], bool) or values[k] is None for k in ('volume', 'density', 'pump_rate')):
            raise ValueError('Missing/boolean fluid input')
    state = {'job_type': operator['job_type'], 'mud_type': operator.get('mud_type', 'WBM'),
        'fluids_config': {'active': list(fluids), 'params': fluids},
        'mud_density': fluids.get('Displacement Fluid', {}).get('density')}
    state_source.refresh_fluids(state)
    if set(state['fluid_data']) != set(fluids):
        raise ValueError('Source applicability rejected an explicitly active fluid')
    reference = {'fluids': state['fluid_data'], 'order': list(state['fluid_data']),
        'total_pump_time_min': state['total_pump_time_min'], 'spacer': None}
    if 'standalone_spacer' in operator:
        if 'Spacer' not in fluids:
            raise ValueError('No inactive Spacer formulation inputs')
        state['standalone_spacer_config'] = operator['standalone_spacer']
        recipe = spacer.formulation_from_state(state)
        rows = spacer.field_rows(recipe)
        # Exact report-only projection from build_master_context; engine untouched.
        from engineering_tools import round_half_up
        for row, material in zip(rows, recipe['materials']):
            row[spacer.FIELD_COLUMNS[4]] = f"{round_half_up(material['dose'], 1):.1f}" + (' gal/bbl' if material['unit'] == 'gal' else '')
        reference['spacer'] = {'recipe': recipe, 'rows': rows,
            'volume_display': f"{round_half_up(recipe['pumped_volume_bbl'], 1):.1f}",
            'density_display': f"{recipe['density_pcf']:g}",
            'tank': operator['standalone_spacer']['tank_name']}
    spacer_payload = {'note_body': reference['spacer']['recipe']['note']} if reference['spacer'] else None
    notes = report.build_ordered_notes(operator['job_type'], {}, state['total_pump_time_min'], [], False,
        spacer_payload=spacer_payload)
    if spacer_payload:
        reference['spacer']['note_mix'] = spacer_payload['note_mix']
    reference['notes'] = notes
    return reference


def render_fluid_fixture(reference, destination):
    """Pinned-template synthetic projection, NOT a full App export or golden."""
    from docxtpl import DocxTemplate
    import phase_10_procedure as report
    context = {'fluids_train': list(reference['fluids'].values()), **reference['notes'],
        'slurries': [], 'has_spacer': reference['spacer'] is not None,
        'well_data': {}, 'hardware': [], 'has_preflush': False, 'has_scavenger': False,
        'executive_summary': 'SYNTHETIC C05 structural control; not an App golden or measured laboratory report.',
        'procedure_steps': []}
    if reference['spacer']:
        s = reference['spacer']
        from standalone_spacer import lab_sample
        sample = lab_sample(s['recipe'])
        types = {m['name']: m['material_type'] for m in s['recipe']['materials']}
        context['standalone_spacer'] = {'volume': s['volume_display'], 'density': s['density_display'],
            'rows': s['rows'], 'note_mix': s['note_mix'],
            'lab': {'rheology': {}}, 'lab_rows': [dict(row, **{'Code': row['Material'],
                'Material Type': 'Water' if row['Material'] == 'Fresh Water' else types[row['Material']],
                'Lot Number': '', 'Design Unit': row['Unit']}) for row in sample['rows']],
            'lab_mass_g': sample['mass_g']}
    template = DocxTemplate(str(SNAPSHOT / 'master_template.docx'))
    template.render(report._escape_xml_special_chars(report._word_quantity_context(context)))
    template.save(str(destination))


HARDWARE_FIELDS = ('Description', 'MD (m)', 'Size (in)', 'ID (in)', 'Joint (m)',
                   'Weight (ppf)', 'Grade', 'Collapse (psi)', 'Burst (psi)')


def well_reference(operator):
    import pandas as pd
    import materials_db as db
    import installed_geometry as installed
    import placement
    import cement_chart_model as chart
    import well_profile
    allowed = {'job_type', 'hardware', 'placement_config', 'well_geometry', 'geothermal_config', 'fluids', 'mud_type'}
    if not isinstance(operator, dict) or set(operator) - allowed or not {'job_type', 'hardware'} <= set(operator):
        raise ValueError('Expected canonical job and independent hardware; only documented optional geometry/fluid inputs')
    job = operator['job_type']
    if job not in db.JOB_TYPES or not isinstance(operator['hardware'], list) or not operator['hardware']:
        raise ValueError('Unknown job or empty independent Hardware')
    hardware = operator['hardware']
    for row in hardware:
        if not isinstance(row, dict) or set(row) - set(HARDWARE_FIELDS) or not {'Description', 'MD (m)'} <= set(row):
            raise ValueError('Canonical Hardware columns and explicit Description/MD required')
        if row['Description'] not in db.HARDWARE_DESCRIPTIONS and not (job == db.CT_JOB and row['Description'] == 'CT'):
            raise ValueError('Unknown source Hardware description')
        if row['Description'] != 'CT':
            installed.md_bounds(row['MD (m)'])
            if row.get('Size (in)') is not None:
                installed.positive_size(row['Size (in)'])
        for value in row.values():
            if isinstance(value, bool) or isinstance(value, (list, dict)) or isinstance(value, float) and not math.isfinite(value):
                raise ValueError('Finite scalar Hardware properties required; missing is not zero')
    frame = pd.DataFrame(hardware)
    if 'fluids' in operator and not isinstance(operator['fluids'], dict):
        raise ValueError('Independent fluids must be a canonical map; absent does not mean zero')
    display = []
    for original in hardware:
        row = {k: '-' if original.get(k) is None or str(original.get(k)).strip() == '' else original[k] for k in HARDWARE_FIELDS}
        try:
            scalar_md = float(row['MD (m)'])
        except (ValueError, TypeError, OverflowError):
            pass
        else:
            if math.isfinite(scalar_md):
                row['MD (m)'] = f'{scalar_md:.1f}'
        if row['Description'] == 'Open Hole Size':
            for field in ('Joint (m)', 'Weight (ppf)', 'Grade', 'Collapse (psi)', 'Burst (psi)'):
                row[field] = '-'
        display.append(row)
    result = {'hardware': hardware, 'hardware_display': display, 'well': None,
        'job_support_matrix': {j: {'canonical': True, 'hardware': 'UNIQUE_PRINTED_ROWS_ONLY',
            'chart_geometry': chart.chart_job_kind(j) or 'NOT_VERIFIABLE',
            'ct_setting_depth': j == db.CT_JOB, 'golden_parity': 'NOT_RUN'} for j in db.JOB_TYPES},
        'source_hardware_choices': placement.hardware_choices(frame, placement.HOST_DESCRIPTIONS),
        'geometry': {'status': 'NOT_VERIFIABLE', 'reason': 'No independent placement configuration supplied'}}
    if ('well_geometry' in operator) != ('geothermal_config' in operator):
        raise ValueError('Provide both independent well_geometry and geothermal_config; no temperature defaults invented')
    if 'well_geometry' in operator:
        geometry = dict(operator['well_geometry'])
        if not isinstance(geometry.get('survey', []), list) or any(not isinstance(r, dict) or set(r) != set(well_profile.SURVEY_COLUMNS) for r in geometry.get('survey', [])):
            raise ValueError('Survey stations require exactly source MD/Deviation/Azimuth fields')
        geometry['survey'] = pd.DataFrame(geometry.get('survey', []), columns=well_profile.SURVEY_COLUMNS)
        geothermal = operator['geothermal_config']
        if not {'source', 'surface_temp', 'value'} <= set(geothermal):
            raise ValueError('Explicit temperature source, value and surface temperature required')
        projections, _, issues = well_profile.resolve_well_profile(geometry, geothermal)
        if issues:
            raise ValueError(' | '.join(issues))
        result['well'] = {'full_precision': projections, 'display': dict(projections,
            geo_gradient=f"{projections['geo_gradient']:.2f}")}
    if job == db.CT_JOB:
        result['ct_setting_depth_m'] = placement.ct_setting_depth(frame)
    if 'placement_config' in operator:
        config = operator['placement_config']
        allowed_config = {'job_type', 'target_row', 'manual_depth_m', 'chart_excess_mode',
            'excess_csg_oh_pct', 'excess_csg_csg_pct', 'host_row', 'tie_back_liner_lap_m'}
        if not isinstance(config, dict) or set(config) - allowed_config:
            raise ValueError('Unsupported placement configuration fields')
        state = {'job_type': job, 'hardware_table': frame, 'placement_config': config}
        try:
            geometry = chart.resolve_chart_geometry(state)
            if geometry is None:
                result['geometry'] = {'status': 'NOT_VERIFIABLE', 'reason': 'Source chart path excludes Plug/Squeeze/CT; no generic substitution'}
            else:
                total = chart.interval_volume(geometry['capacity_segments'], 0, geometry['shoe_md'])
                result['geometry'] = {'status': 'INFORMATIONAL', 'model': geometry,
                    'full_annular_capacity_bbl': total, 'client_requested_volumes_bbl': {},
                    'client_volume_comparison': 'NOT_VERIFIABLE', 'placement': []}
                if operator.get('fluids'):
                    fluid_op = {k: operator[k] for k in ('job_type', 'fluids', 'mud_type') if k in operator}
                    fluid_ref = fluid_reference(fluid_op)
                    state['fluids_config'] = {'active': fluid_ref['order'], 'params': operator['fluids']}
                    if any(name in db.PLACEMENT_SLURRIES for name in fluid_ref['order']):
                        placed = chart.resolve_cement_placement(state, geometry)
                        result['geometry']['placement'] = placed
                        result['geometry']['client_requested_volumes_bbl'] = {r['fluid']: r['entered_bbl'] for r in placed}
                        result['geometry']['client_volume_comparison'] = 'INFORMATIONAL'
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            result['geometry'] = {'status': 'NOT_VERIFIABLE', 'source_input_error': True, 'reason': str(error)}
    return result


def render_well_fixture(reference, destination):
    from docxtpl import DocxTemplate
    import phase_10_procedure as report
    context = {'well_data': reference['well']['display'] if reference['well'] else {},
        'hardware': reference['hardware_display'], 'fluids_train': [], 'slurries': [],
        'has_preflush': False, 'has_spacer': False, 'has_scavenger': False,
        'executive_summary': 'SYNTHETIC C06 structural control; no program certification.', 'procedure_steps': []}
    template = DocxTemplate(str(SNAPSHOT/'master_template.docx'))
    template.render(report._escape_xml_special_chars(report._word_quantity_context(context)))
    template.save(str(destination))


def lab_reference(operator):
    """Independent observations, genuine source fitting/admission, never predicted measurements."""
    import pandas as pd
    import materials_db as db
    import engineering_tools as eng
    import phase_5_cement as phase5
    import phase_7_lab as phase7
    import phase_10_procedure as report
    import project_state as state_source
    import standalone_spacer as spacer_source
    from c02_engine import reference as cement_reference
    from checker_parser import parse_docx, norm
    from comparison_records import tables
    allowed = {'job_type', 'active_fluids', 'measurements', 'conditions', 'cement_operator', 'spacer_operator', 'confirmed', 'mud_type'}
    if not isinstance(operator, dict) or set(operator) - allowed or not {'job_type', 'active_fluids', 'measurements'} <= set(operator):
        raise ValueError('Expected job_type, explicit active_fluids and independent measurements only')
    job = operator['job_type']; active = operator['active_fluids']
    if job not in db.JOB_TYPES or not isinstance(active, list) or len(active) != len(set(active)) or set(active) - set(db.FLUID_TYPES):
        raise ValueError('Unknown/duplicate source job or fluid')
    if 'Diesel' in active and operator.get('mud_type') != 'OBM':
        raise ValueError('Source Diesel applicability requires independent OBM mud type')
    eligible = state_source.available_fluid_types({'job_type': job, 'mud_type': operator.get('mud_type', 'WBM')})
    if set(active) - set(eligible):
        raise ValueError('Source job/mud applicability rejects an active fluid')
    observations = operator['measurements']
    if not isinstance(observations, dict) or set(observations) - set(active):
        raise ValueError('Measurements must belong only to explicitly active fluids')
    if not isinstance(operator.get('confirmed', False), bool):
        raise ValueError('Reference confirmation must be an explicit boolean')
    conditions = operator.get('conditions', {})
    if not isinstance(conditions, dict) or set(conditions) - {'bhct', 'bhst', 'bhsp'}:
        raise ValueError('Only independent source BHCT/BHST/BHSP conditions are supported')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in conditions.values()):
        raise ValueError('Lab conditions require finite independent numbers')
    temperature_valid = eng.lab_temperature_valid(conditions.get('bhct'), conditions.get('bhst'))
    if {'bhct', 'bhst'} <= set(conditions) and not temperature_valid:
        raise ValueError('Source BHCT/BHST validation failed')
    if 'bhsp' in conditions:
        eng.require_nonnegative_number(conditions['bhsp'], 'BHSP')
    cement = None
    if 'cement_operator' in operator:
        cop = operator['cement_operator']
        if cop.get('job_type') != job or set(cop.get('active_fluids', [])) != set(active):
            raise ValueError('Cement reference job/active identities conflict with lab reference')
        outer = sys.gettrace()
        try:
            cement = cement_reference(cop)
        finally:
            sys.settrace(outer)
    qc_fields = {'rheology', 'compressive', 'free_water', 'free_water_45', 'surface_hardened_hours', 'api_fl',
                 *(f for f, _, _ in eng.THICKENING_TEST_FIELDS)}
    result = {'conditions': conditions, 'temperature_valid': temperature_valid,
        'cement_reference': cement, 'fluids': {}, 'spacer': None,
        'confirmation_scope': 'Independent reference observations only; never Word approval or historical App review'}
    for fluid in active:
        role = ('ordinary_lab' if fluid in db.PLACEMENT_SLURRIES and job != db.CT_JOB else
                'spacer_lab' if fluid == 'Spacer' else 'WORD_MAPPING_NOT_VERIFIABLE')
        item = {'role': role, 'rheology': {}, 'lab': dict(conditions, rheology={}), 'payload_admitted': False,
            'admission_reason': 'No complete independently confirmed recipe/measurement reference'}
        result['fluids'][fluid] = item
        if fluid not in observations:
            continue
        qc = deepcopy(observations[fluid])
        if not isinstance(qc, dict) or set(qc) - qc_fields:
            raise ValueError('Unsupported QC input/cached result; only independent observations accepted')
        numeric_observations = {'free_water', 'free_water_45', 'surface_hardened_hours', 'api_fl', 'thickening_cell'}
        if any(type(qc[k]) not in (int, float) or not math.isfinite(qc[k]) for k in numeric_observations & set(qc)):
            raise ValueError('Independent collection/cell/filtrate observations require finite JSON numbers')
        if fluid not in (*db.PHASE7_LAB_FLUIDS, 'Spacer'):
            item['admission_reason'] = 'No source-applicable Lab role; observations retained unverified'
            continue
        if 'rheology' in qc:
            item['rheology'] = eng.validate_lab_rheology(qc, fluid)
            item['lab']['rheology'] = item['rheology']
        full_lab = fluid in db.PLACEMENT_SLURRIES
        full_fields = {'free_water', 'free_water_45', 'surface_hardened_hours'}
        if full_lab:
            if full_fields & set(qc):
                eng.validate_lab_collection_results(qc)
                item['lab'].update({key: qc[key] for key in full_fields})
            if any(f in qc for f, _, _ in eng.THICKENING_TEST_FIELDS):
                item['lab'].update(eng.validate_thickening_test(qc))
            if 'compressive' in qc:
                item['lab']['compressive'] = eng.validate_compressive_test(qc)
            if 'api_fl' in qc:
                if type(qc['api_fl']) not in (int, float) or not math.isfinite(qc['api_fl']):
                    raise ValueError('Independent filtrate must be a finite measured number')
                # Phase VII's Filtrate number_input has min_value=0.0. Reuse its
                # existing scalar validator; never copy the dependent API formula.
                eng.require_nonnegative_number(qc['api_fl'], 'Filtrate @ 30 min')
                item['lab']['api_fl_collected'] = qc['api_fl']
            required = full_fields | {'rheology', 'compressive', 'api_fl'} | {f for f, _, _ in eng.THICKENING_TEST_FIELDS if f != 'thickening_enter_time'}
            if (operator.get('confirmed') is True and temperature_valid and required <= set(qc)
                    and cement and fluid in cement['slurries']):
                reference = cement['slurries'][fluid]; inputs = operator['cement_operator']['slurries'][fluid]
                frame = pd.DataFrame(inputs['additives'], columns=[*phase5.REQUIRED_ADDITIVE_COLUMNS, 'Density'])
                grid = phase7.build_lab_df_from_phase5(frame, base_cement=inputs['base_cement'],
                    slurry_weight_pcf=inputs['density_pcf'], slurry_volume_bbl=inputs['client_volume_bbl'],
                    cmt_sg=inputs['cement_sg'], recalculate_mass=True)
                params = {'auto_calc': True, 'base_cement': inputs['base_cement'], 'cmt_sg': inputs['cement_sg'], 'cmt_sg_source': 'manual'}
                state = {'job_type': job, 'fluids_config': {'active': [fluid]},
                    'fluid_data': {fluid: {'density': reference['density'], 'effective_density': eng.require_positive_density(reference['density'])}},
                    'cement_params': {fluid: params}, 'cement_additives_dfs': {fluid: frame},
                    'lab_grid_dfs': {fluid: grid}, 'lab_qc_params': {fluid: qc}, 'well_data': conditions}
                # Explicit independent confirmation follows construction/validation of this reference.
                # No live session or prior App approval is read, impersonated or bypassed.
                qc['reviewed'] = True
                qc['review_signature'] = eng.lab_review_signature(qc, grid)
                state['lab_source_signatures'] = {fluid: state_source.lab_source_signature(state, fluid)}
                issues = state_source.refresh_lab_payloads(state)
                if issues:
                    raise ValueError('Original Lab admission failed: ' + ' | '.join(issues))
                payload = state['lab_payload_' + fluid]
                item['lab'].update({key: value for key, value in payload.items() if key != 'grid'})
                item['lab']['fluid_loss'] = payload['api_fl']
                item['payload_admitted'] = True
                item['admission_reason'] = 'Original refresh_lab_payloads accepted explicit confirmed independent reference; no measurement prediction'
        for test, prefix in (('uca', 'uca'), ('crush', 'crush')):
            selected = item['lab'].get('compressive', {}).get(test, {}).get('selected', False)
            item['lab'][prefix + '_temp'] = conditions.get('bhst', '-') if selected else '-'
            item['lab'][prefix + '_pressure'] = conditions.get('bhsp', '-') if selected else '-'
        # Run the original Word presentation over a template-only copy.
        item['display'] = report._word_quantity_context({'slurries': [{'name': fluid, 'lab': item['lab']}]})['slurries'][0]['lab']
    if 'spacer_operator' in operator:
        sop = operator['spacer_operator']
        if 'Spacer' not in active or sop.get('job_type') != job or set(sop.get('fluids', {})) - set(active):
            raise ValueError('Spacer reference belongs to another/inactive job or fluid')
        sref = fluid_reference(sop)
        if sref['spacer'] is None:
            raise ValueError('Explicit configured Standalone Spacer required')
        if cement:
            for fluid in set(sref['fluids']) & set(cement['slurries']):
                if (sref['fluids'][fluid]['volume'] != operator['cement_operator']['slurries'][fluid]['client_volume_bbl']
                        or sref['fluids'][fluid]['effective_density'] != float(cement['slurries'][fluid]['density'])):
                    raise ValueError('Conflicting independent cement/Spacer reference inputs')
        recipe = sref['spacer']['recipe']; sample = spacer_source.lab_sample(recipe)
        state = {'job_type': job, 'fluids_config': {'active': list(sop['fluids']), 'params': sop['fluids']},
            'standalone_spacer_config': sop['standalone_spacer']}
        grid = state_source.spacer_lab_grid(state)
        if operator.get('confirmed') is True and temperature_valid and 'rheology' in observations.get('Spacer', {}):
            qc = deepcopy(observations['Spacer'])
            state.update(well_data=conditions,lab_qc_params={'Spacer':qc})
            grid = state_source.refresh_spacer_lab(state)
            qc['reviewed'] = True
            qc['review_signature'] = eng.lab_review_signature(qc, grid)
            admitted = state_source.spacer_lab_payload(state)
            result['fluids']['Spacer']['lab'].update({k:v for k,v in admitted.items() if k!='grid'})
            result['fluids']['Spacer']['payload_admitted'] = True
            result['fluids']['Spacer']['admission_reason'] = 'Original spacer_lab_payload accepted the explicitly confirmed independent cup and measured rheology'
        kinds = {m['name']: m['material_type'] for m in recipe['materials']}
        lab_rows = [dict(r, **{'Material Type': 'Water' if r['Material'] == 'Fresh Water' else kinds[r['Material']],
            'Code': r['Material'], 'Lot Number': r['Lot No'], 'Design Unit': r['Unit']}) for r in grid.to_dict('records')]
        s = dict(sref['spacer'], lab=result['fluids']['Spacer'].get('lab', {'rheology': {}}),
            lab_rows=lab_rows, lab_mass_g=sample['mass_g'], sample=sample)
        s['lab'].setdefault('rheology', {})
        projected = report._word_quantity_context({'has_spacer': True, 'standalone_spacer': s})['standalone_spacer']
        result['fluids']['Spacer']['display'] = projected['lab']
        result['spacer'] = dict(s, display=projected)
    # Read the actual locked template's expressions, unit literals and physical grids.
    parsed_template = parse_docx(SNAPSHOT/'master_template.docx')
    if parsed_template['status'] == 'REJECTED':
        raise ValueError('Locked Lab template unsupported')
    anchors = {'Test Basic Data', 'Rheology Test', 'Free Water Test | Fluid Loss Test',
               'Thickening Time Test', 'Compressive Strength Test', 'Spacer Rheology'}
    contracts = {}
    mass_headers = {}
    canonical_anchors = {norm(a): a for a in anchors}
    for table in tables(parsed_template):
        anchor = table[0]['table_anchor']
        if anchor in ('Conventional', 'Additives', 'Spacer Lab Results'):
            from comparison_records import rows, regular_columns
            headers = [r for r in rows(table) if regular_columns(r) and norm(r[0]['raw_text']) == 'material type']
            # Conventional and Additives are subgroups of one physical source table.
            if headers and len({tuple(norm(c['raw_text']) for c in r) for r in headers}) == 1:
                mass_headers[anchor] = [r['raw_text'] for r in headers[0]]
        if norm(anchor) in canonical_anchors:
            anchor = canonical_anchors[norm(anchor)]
            if anchor in contracts:
                raise ValueError('Ambiguous locked Lab template anchor')
            contracts[anchor] = [{'row': r['locator']['row'], 'column': r['locator']['column'],
                'span': r['locator']['column_span'], 'text': r['raw_text']} for r in table]
    if set(contracts) != anchors:
        raise ValueError('Missing locked Lab template contract')
    result['template_contracts'] = contracts
    result['mass_headers'] = mass_headers
    result['template_sha256'] = hashlib.sha256((SNAPSHOT/'master_template.docx').read_bytes()).hexdigest()
    return result


def render_lab_fixture(reference, destination):
    from docxtpl import DocxTemplate
    import phase_10_procedure as report
    cement = reference['cement_reference']; slurries = []
    for fluid in report.REPORT_SLURRY_ORDER:
        if fluid not in reference['fluids']:continue
        item = reference['fluids'][fluid]
        if item['role'] != 'ordinary_lab':
            continue
        base = cement['slurries'].get(fluid) if cement else None
        row = {'name': fluid, 'lab': item['lab'], 'lab_conventional': [], 'lab_additives': [], 'blends': [], 'additives': []}
        if base:
            calc = base['calc']
            row.update(density_pcf=base['density'], volume_bbl=cement['operator_inputs']['slurries'][fluid]['client_volume_bbl'],
                yield_cuft_sk=calc['yield_ft3_per_sk'], solution=calc['field_solution_bbl'],
                blends=base['blend'], additives=base['additives'])
            # Original separate_lab_tables and build_master_context projection; no new recipe.
            import pandas as pd
            import phase_5_cement as phase5
            import phase_7_lab as phase7
            op = cement['operator_inputs']['slurries'][fluid]
            frame = pd.DataFrame(op['additives'], columns=[*phase5.REQUIRED_ADDITIVE_COLUMNS, 'Density'])
            grid = phase7.build_lab_df_from_phase5(frame, base_cement=op['base_cement'], slurry_weight_pcf=op['density_pcf'],
                slurry_volume_bbl=op['client_volume_bbl'], cmt_sg=op['cement_sg'], recalculate_mass=True)
            conventional, additives = report.separate_lab_tables(grid, frame)
            row['lab_conventional'] = [dict(r, Name=r['Material Type']) for r in conventional]
            row['lab_additives'] = [dict(r, Name=r['Material Type']) for r in additives]
        slurries.append(row)
    context = {'slurries': slurries, 'well_data': {}, 'hardware': [], 'fluids_train': [],
        'has_preflush': False, 'has_spacer': reference['spacer'] is not None, 'has_scavenger': False,
        'executive_summary': 'SYNTHETIC C07 source-rendered control. Observations independently specified; NOT measured production evidence.',
        'procedure_steps': []}
    if reference['spacer']:
        s = reference['spacer']
        context['standalone_spacer'] = dict(s, volume=s['volume_display'], density=s['density_display'], note_mix=s['note_mix'])
    template = DocxTemplate(str(SNAPSHOT/'master_template.docx'))
    template.render(report._escape_xml_special_chars(report._word_quantity_context(context)))
    template.save(str(destination))


def run(payload):
    from tools.provision import verify_candidate
    verify_candidate(ROOT)
    verify_source()
    sys.path.insert(0, str(SNAPSHOT))
    calls = set()
    before_input = json.dumps(payload['operator'], sort_keys=True, allow_nan=False)

    def trace(frame, event, arg):
        name = frame.f_code.co_filename
        inside = name.startswith(str(SNAPSHOT) + '/')
        if event == 'call' and inside:
            if 'session_state' in frame.f_code.co_names:
                raise RuntimeError('Live Streamlit state prohibited: ' + frame.f_code.co_name)
            calls.add(Path(name).name + ':' + frame.f_code.co_name)
        return trace if inside else None

    sys.settrace(trace)
    try:
        if payload['action'] not in ('fluids', 'render_fluids', 'well', 'render_well', 'lab', 'render_lab'):
            raise ValueError('Unsupported source action')
        function = lab_reference if payload['action'] in ('lab', 'render_lab') else well_reference if payload['action'] in ('well', 'render_well') else fluid_reference
        reference = function(payload['operator'])
        if reference.get('cement_reference'):
            calls.update(reference['cement_reference']['source_calls'])
        if payload['action'].startswith('render_'):
            destination = Path(payload['docx']).absolute()
            if destination.suffix != '.docx' or not destination.is_relative_to(ROOT / 'tmp') or destination.resolve() != destination or destination.exists():
                raise ValueError('New synthetic DOCX must remain under runtime/tmp without symlinks')
            renderer = render_lab_fixture if payload['action'] == 'render_lab' else render_well_fixture if payload['action'] == 'render_well' else render_fluid_fixture
            renderer(reference, destination)
        origins = {}
        for path in SNAPSHOT.glob('*.py'):
            module = sys.modules.get(path.stem)
            if module is not None:
                if Path(module.__file__).resolve() != path.resolve():
                    raise ValueError('Non-snapshot sibling import: ' + path.stem)
                origins[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if json.dumps(payload['operator'], sort_keys=True, allow_nan=False) != before_input:
            raise ValueError('Independent operator reference mutated by source')
        if payload['action'] in ('lab', 'render_lab'):
            def omit_excluded(value):
                if isinstance(value, dict):
                    return {k: omit_excluded(v) for k,v in value.items() if k.casefold() != 'iod'}
                if isinstance(value, list):return [omit_excluded(v) for v in value]
                return value
            reference = omit_excluded(reference)
        return {'source_sha': SOURCE_SHA, 'reference': reference, 'source_calls': sorted(calls),
            'source_module_sha256': origins,
            'operator_input_sha256': hashlib.sha256(before_input.encode()).hexdigest()}
    finally:
        sys.settrace(None)


def install_audit():
    def writable(name):
        if isinstance(name, (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(name)).resolve()
            if not any(path.is_relative_to(ROOT / folder) for folder in ('tmp', 'cache')):
                raise RuntimeError('Source write boundary')

    def audit(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo'):
            raise RuntimeError('Network prohibited during source calculation')
        if event == 'open':
            name, mode, flags = args
            write = isinstance(mode, str) and any(x in mode for x in 'wax+') or isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            if write and isinstance(name, (str, bytes, os.PathLike)):
                writable(name)
        if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.truncate'):
            writable(args[0])
        if event in ('os.rename', 'os.link', 'os.symlink'):
            writable(args[0]); writable(args[1])
    sys.addaudithook(audit)


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    install_audit()
    try:
        output = run(read_json(sys.stdin.read()))
    except (ValueError, TypeError, KeyError, RuntimeError, OSError, OverflowError) as error:
        output = {'error': str(error), 'source_sha': SOURCE_SHA}
    print(json.dumps(output, allow_nan=False))
