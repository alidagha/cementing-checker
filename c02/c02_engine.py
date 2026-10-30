"""Isolated original-source calls. No copied mass balance or live App state."""
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'snapshot'
SOURCE_SHA = '60dffefb8c941ad90cb7caba0992126a35803717'
MANIFEST_SHA = '89e2a97d8932c0f965be8ffc640c235d9583b5172ad8a589d7000247e5f541b5'


def verify_source():
    manifest = ROOT / 'evidence/snapshot.sha256'
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA:
        raise ValueError('Source inventory identity mismatch')
    for line in manifest.read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = ROOT / name
        if not path.resolve().is_relative_to(SNAPSHOT.resolve()) or path.is_symlink():
            raise ValueError('Source snapshot path escape')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Source snapshot mismatch: ' + name)


def reference(operator):
    verify_source()
    # Sibling imports must resolve only in the immutable snapshot, never checkout.
    sys.path.insert(0, str(SNAPSHOT))
    calls = set()

    def trace(frame, event, arg):
        inside = str(frame.f_code.co_filename).startswith(str(SNAPSHOT) + '/')
        if event == 'call' and inside:
            if 'session_state' in frame.f_code.co_names:
                raise RuntimeError('Stateful source call prohibited: ' + frame.f_code.co_name)
            calls.add(Path(frame.f_code.co_filename).name + ':' + frame.f_code.co_name)
        return trace if inside else None

    sys.settrace(trace)
    try:
        import pandas as pd
        import materials_db as db
        import engineering_tools as eng
        import phase_5_cement as phase5
        import phase_7_lab as phase7
        import phase_10_procedure as report
        for mod in (db, eng, phase5, phase7, report):
            if not Path(mod.__file__).resolve().is_relative_to(SNAPSHOT):
                raise ValueError('Non-snapshot source import')
        origins = {}
        for path in SNAPSHOT.glob('*.py'):
            module = sys.modules.get(path.stem)
            if module is not None:
                origin = Path(module.__file__).resolve()
                if not origin.is_relative_to(SNAPSHOT):
                    raise ValueError('Non-snapshot sibling import: ' + path.stem)
                origins[path.stem] = hashlib.sha256(origin.read_bytes()).hexdigest()
        if set(operator) != {'job_type', 'active_fluids', 'slurries'}:
            raise ValueError('Expected job_type, active_fluids, slurries only; automatic mode only')
        if operator['job_type'] not in db.JOB_TYPES:
            raise ValueError('Unknown source job type')
        active = operator['active_fluids']
        if not isinstance(active, list) or len(active) != len(set(active)) or any(x not in db.FLUID_TYPES for x in active):
            raise ValueError('Unknown/duplicate active fluid')
        cement = [x for x in active if x in db.CEMENT_FORMULATION_FLUIDS]
        if not cement or set(operator['slurries']) != set(cement):
            raise ValueError('Provide exactly the active cement formulations; no inactive inputs')
        output = {}
        for fluid in cement:
            item = operator['slurries'][fluid]
            if set(item) != {'client_volume_bbl', 'density_pcf', 'base_cement', 'cement_sg', 'additives'}:
                raise ValueError('Explicit volume, density, base identity, SG and additives required')
            for key in ('client_volume_bbl', 'density_pcf', 'cement_sg'):
                if type(item[key]) not in (int, float) or not math.isfinite(item[key]):
                    raise ValueError(key + ': finite JSON number required')
            volume = eng.clean_number(item['client_volume_bbl'])
            density = eng.require_positive_density(item['density_pcf'])
            if volume <= 0 or not math.isfinite(volume):
                raise ValueError('Client Requested Volume must be positive and finite')
            base = item['base_cement']
            match = db.resolve_known_material(base)
            if not match or match[1] != 'Cement':
                raise ValueError('Unverified base cement identity')
            # Zero is internal base-quantity bookkeeping, not the engineer's Dead Volume.
            params = {'cmt_sg': eng.clean_number(item['cement_sg']), 'cmt_sg_source': 'manual',
                      'base_cement': base, 'auto_calc': True, 'dead_vol': 0.0,
                      'tank_name': '<NOT COMPARED>'}
            eng.validate_cement_parameters(params)
            rows = item['additives']
            if not isinstance(rows, list):
                raise ValueError('Additives must be an explicit list')
            for row in rows:
                required = {'Material Type', 'Name', 'Physical State', 'Mix Method', 'User Input'}
                if not required <= set(row) or set(row) - required - {'Density'}:
                    raise ValueError('Incomplete or unsupported additive properties')
                eng.require_additive_identity(row)
                if type(row['User Input']) not in (int, float) or not math.isfinite(row['User Input']):
                    raise ValueError('Additive dosage: finite JSON number required')
                known = db.resolve_known_material(row['Name'])
                if known and row['Material Type'] != known[1]:
                    raise ValueError('Material type contradicts exact source catalog identity')
                if row['Physical State'] not in ('Powder', 'Liquid') or row['Mix Method'] not in ('Dry Blend', 'In Mix Water'):
                    raise ValueError('Explicit supported state/mix method required')
            frame = pd.DataFrame(rows, columns=[*phase5.REQUIRED_ADDITIVE_COLUMNS, 'Density'])
            components = phase5.build_components(frame)
            calc = phase5.calculate_base_results(params, volume, density, *components)
            blend, additives, _ = phase5.build_cement_tables(params, frame, calc)
            lab = phase7.build_lab_df_from_phase5(frame, base_cement=base,
                slurry_weight_pcf=density, slurry_volume_bbl=volume, cmt_sg=params['cmt_sg'], recalculate_mass=True)
            conventional, lab_additives = report.separate_lab_tables(lab, frame)
            display = report._word_program_quantities({'yield_cuft_sk': calc['yield_ft3_per_sk'],
                'mix_water_bbl': calc['field_water_bbl'], 'total_sacks': calc['field_sacks']})
            raw_lab = {base.casefold(): calc['lab_cmt_gr'], 'base water': calc['lab_water_gr']}
            raw_field = {}
            for row in calc['lab_powders'] + calc['lab_liquids']:
                raw_lab[row['name'].casefold()] = row['lab_gr']
            for row in calc['field_powders']:
                raw_field[row['name'].casefold()] = row['field_lb']
            for row in calc['field_liquids']:
                raw_field[row['name'].casefold()] = row['field_gal']
            salt_rows = [r for r in rows if eng.is_salt_additive(r['Material Type'], r['Name'])]
            if len(salt_rows) == 1:
                raw_lab[salt_rows[0]['Name'].casefold()] = calc['salt_lab_gr']
                raw_field[salt_rows[0]['Name'].casefold()] = calc['salt_field_lb']
            output[fluid] = {'calc': calc, 'display': display, 'density': str(density),
                'program_section': 'cement' if fluid in db.PLACEMENT_SLURRIES else 'preflush',
                'lab_report_supported': fluid in db.PLACEMENT_SLURRIES,
                'base_cement': base, 'blend': blend.to_dict('records'),
                'additives': additives.to_dict('records'), 'lab': conventional + lab_additives,
                'raw_lab': raw_lab, 'raw_field': raw_field, 'operator_additives': rows}
        return {'source_sha': SOURCE_SHA, 'slurries': output, 'source_calls': sorted(calls), 'source_module_sha256': origins,
                'operator_input_sha256': hashlib.sha256(json.dumps(operator,sort_keys=True,allow_nan=False).encode()).hexdigest(),
                'operator_inputs': operator,
                'job_applicability': 'NOT_VERIFIED', 'unimplemented_fluids': [x for x in active if x not in cement]}
    finally:
        sys.settrace(None)


def strict_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('Duplicate JSON key: ' + key)
        out[key] = value
    return out


def read_json(text):
    return json.loads(text, object_pairs_hook=strict_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON constant')))


if __name__ == '__main__':
    # Isolated process: prohibit network; all supported operations are local.
    sys.dont_write_bytecode = True
    sys.addaudithook(lambda event, args: (_ for _ in ()).throw(RuntimeError('Network prohibited'))
                    if event in ('socket.connect', 'socket.getaddrinfo') else None)
    try:
        result = reference(read_json(sys.stdin.read()))
    except (ValueError, TypeError, KeyError, RuntimeError, OverflowError) as error:
        result = {'error': str(error), 'source_sha': SOURCE_SHA}
    print(json.dumps(result, allow_nan=False))
