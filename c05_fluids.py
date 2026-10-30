"""C05 partial fluid-train and configured Standalone Spacer comparisons."""
import argparse
import json
from pathlib import Path
import re

from checker_parser import parse_docx, norm, FLUIDS
from comparison_records import ROOT, unique_table, rows, finding, finish
from engineering_source import request
from c02_engine import read_json

FLUID_HEADERS = ['Type', 'Name', 'Density (lb/ft3)', 'Volume (bbl)', 'Pump Rate (bbl/min)',
                 'Duration (hr:mn)', 'Cumulated Time (hr:mn)']
SPACER_HEADERS = ['Item', 'Name', 'Material Type', 'lbs or gal', 'lbs / bbl or gal / bbl', 'lbs or gal (with dead Vol.)']


def compare_document(docx, operator):
    parsed = parse_docx(docx)
    if parsed['status'] == 'REJECTED':
        return {'status': 'INPUT_REJECTED', 'reason': parsed['error'], 'findings': []}
    try:
        source = request('fluids', operator)
    except (ValueError, TypeError) as error:
        return {'status': 'REFERENCE_INPUT_ERROR', 'reason': str(error), 'findings': [], 'records': parsed['records']}
    ref = source['reference']
    findings = []
    table = unique_table(parsed, 'Fluids', 'fluids')
    candidates = rows(table) if table else []
    headers = [r for r in candidates if [norm(c['raw_text']) for c in r] == [norm(x) for x in FLUID_HEADERS]]
    valid = candidates if len(headers) == 1 else []
    seen = []
    for name, values in ref['fluids'].items():
        matches = [r for r in valid if len(r) == 7 and r[0]['raw_text'] == name]
        row = matches[0] if len(matches) == 1 and all(c['association'] == name and c['association_state'] == 'EXPLICIT' for c in matches[0]) else None
        if row:
            seen.append((row[0]['locator']['row'], name))
        for col, key in ((1, 'material_name'), (2, 'density'), (3, 'volume'), (4, 'pump_rate'), (5, 'duration_str'), (6, 'cumul_time_str')):
            numeric = key == 'volume'
            record = row[col] if row and norm(row[col]['column_label'] or '') == norm(FLUID_HEADERS[col]) else None
            f = finding(record, 'fluid.' + key, values[key], values[key], '',
                'project_state.refresh_fluids / engineering_tools.format_to_hr_mm', numeric=numeric)
            f.update(fluid=name, unit={'density': 'lb/ft3', 'volume': 'bbl', 'pump_rate': 'bbl/min', 'duration_str': 'hr:mn', 'cumul_time_str': 'hr:mn'}.get(key, 'text'))
            findings.append(f)
    printed = [r[0]['raw_text'] for r in valid if len(r) == 7 and r[0]['raw_text'] in FLUIDS]
    for name in set(printed) - set(ref['order']):
        record = next(r[0] for r in valid if r[0]['raw_text'] == name)
        f = finding(record, 'fluid.active_selection', 'inactive', 'inactive', 'identity', 'project_state.refresh_fluids', numeric=False)
        f.update(fluid=name, result='DISCREPANCY', reason='Printed canonical fluid is independently inactive')
        findings.append(f)
    order = [name for _, name in sorted(seen)]
    findings.append({'field': 'fluid.execution_order', 'locator': table[0]['locator'] if table else None,
        'section': 'fluids', 'slurry': None, 'raw_reported_text': printed,
        'source_rounded_expected': ref['order'], 'full_precision_expected': ref['order'], 'unit': 'ordered identities',
        'source_function': 'materials_db.HYDRAULIC_EXECUTION_ORDER / project_state.refresh_fluids',
        'result': 'MATCH' if order == ref['order'] and printed == order else 'NOT_VERIFIABLE',
        'reason': 'Complete unique active-fluid rows required; not a program PASS', 'association_proof': 'One labeled Fluids table', 'delta': None, 'tolerance': None})
    if ref['spacer']:
        s = ref['spacer']
        table = unique_table(parsed, 'Spacer Additives Data', 'preflush')
        candidates = rows(table) if table else []
        headers = [r for r in candidates if [norm(c['raw_text']) for c in r] == [norm(x) for x in SPACER_HEADERS]]
        valid = candidates if len(headers) == 1 else []
        for material, display in zip(s['recipe']['materials'], s['rows']):
            matches = [r for r in valid if len(r) == 6 and r[1]['raw_text'] == material['name'] and r[2]['raw_text'] == material['material_type']]
            row = matches[0] if len(matches) == 1 and all(c['association'] == 'Spacer' and c['association_state'] == 'EXPLICIT' for c in matches[0]) else None
            for col, key in ((3, 'base'), (5, 'gross')):
                expected = display[SPACER_HEADERS[col] if col == 3 else 'lbs or gal\n(with dead Vol.)']
                record = row[col] if row and norm(row[col]['column_label'] or '') == norm(SPACER_HEADERS[col]) else None
                f = finding(record, 'spacer.' + key, expected.removesuffix(' ' + material['unit']), material[key], material['unit'],
                    'standalone_spacer.formulation_from_state / calculate_spacer / field_rows')
                f['material'] = material['name']
                findings.append(f)
        # Only a directly adjacent, unique source-pattern NOTE belongs to this table.
        notes = []
        if table and len(headers) == 1:
            end = max(r['source_order'] for r in table)
            following = [r for r in parsed['records'] if r['source_order'] > end and r['raw_text'].strip()]
            for r in following:
                if r['locator'].get('table') is not None:
                    break
                if re.fullmatch(r'NOTE \d+: Mix above Additives in .+ bbl Fresh Water at .+\.', r['raw_text']):
                    notes.append(r)
                else:
                    break
        note = notes[0] if len(notes) == 1 and notes[0]['section'] == 'preflush' else None
        match = re.fullmatch(r'NOTE \d+: Mix above Additives in (.+) bbl Fresh Water at (.+)\.', note['raw_text']) if note else None
        expected = re.fullmatch(r'Mix above Additives in (.+) bbl Fresh Water at (.+)\.', s['recipe']['note'])
        for field, raw, value, full, unit, numeric in (
            ('spacer.preparation_water', match[1] if match else None, expected[1], s['recipe']['water_total_bbl'], 'bbl', True),
            ('spacer.tank', match[2] if match else None, s['tank'], s['tank'], 'text', False)):
            record = dict(note, raw_text=raw) if match else None
            f = finding(record, field, value, full, '', 'standalone_spacer.formulation_from_state / phase_10_procedure.build_ordered_notes',
                tolerance=1 if numeric else 0, numeric=numeric, reason='Unique immediately following Spacer NOTE; independent source-validated tank')
            f.update(unit=unit, raw_reported_text=note['raw_text'] if note else None)
            findings.append(f)
    return finish(parsed, source, findings, [
        'PARTIAL only: optional fluids follow source applicability; no mandatory Pre Flush/Spacer/Diesel',
        'Pre Flush chemistry, operational Spacer Ahead/Behind preparation, CT stage allocation and free Procedure prose remain UNIMPLEMENTED',
        'Spacer dosage and measured Lab rows remain unverified; no inverse solve or Word editing'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('operator_json'); ap.add_argument('docx')
    args = ap.parse_args()
    try:
        path = Path(args.operator_json).resolve(strict=True)
        if not path.is_relative_to(ROOT):
            raise ValueError('Operator input outside runtime')
        result = compare_document(args.docx, read_json(path.read_text()))
    except (ValueError, OSError, TypeError) as error:
        result = {'status': 'REFERENCE_INPUT_ERROR', 'reason': str(error), 'findings': []}
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result['status'] == 'PARTIAL_FINDINGS_ONLY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
