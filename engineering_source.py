"""G01 isolated calls to locked App authorities; no engineering formulas here."""
import hashlib
import json
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


def run(payload):
    from tools.provision import verify_candidate
    verify_candidate(ROOT)
    verify_source()
    sys.path.insert(0, str(SNAPSHOT))
    calls = set()

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
        if payload['action'] not in ('fluids', 'render_fluids'):
            raise ValueError('Unsupported source action')
        reference = fluid_reference(payload['operator'])
        if payload['action'] == 'render_fluids':
            destination = Path(payload['docx']).absolute()
            if destination.suffix != '.docx' or not destination.is_relative_to(ROOT / 'tmp') or destination.resolve() != destination or destination.exists():
                raise ValueError('New synthetic DOCX must remain under runtime/tmp without symlinks')
            render_fluid_fixture(reference, destination)
        origins = {}
        for path in SNAPSHOT.glob('*.py'):
            module = sys.modules.get(path.stem)
            if module is not None:
                if Path(module.__file__).resolve() != path.resolve():
                    raise ValueError('Non-snapshot sibling import: ' + path.stem)
                origins[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return {'source_sha': SOURCE_SHA, 'reference': reference, 'source_calls': sorted(calls),
            'source_module_sha256': origins,
            'operator_input_sha256': hashlib.sha256(json.dumps(payload['operator'], sort_keys=True, allow_nan=False).encode()).hexdigest()}
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
