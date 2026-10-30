"""C06 unique hardware/temperature claims and informational original-source geometry."""
import argparse
from collections import Counter
import json
from pathlib import Path

from checker_parser import parse_docx, norm
from comparison_records import ROOT, unique_table, rows, regular_columns, number, finding, finish
from engineering_source import request, HARDWARE_FIELDS
from c02_engine import read_json

HW_HEADERS = ['Description', 'MD', 'Size', 'ID', 'Joint', 'Weight', 'Grade', 'Collapse', 'Burst']
HW_UNITS = ['', 'm', 'in', 'in', 'm', 'lb/ft', '-', 'psi', 'psi']
TEMP_HEADERS = ['MD (m)', 'TVD (m)', 'BHST (degF)', 'Gradient (degF/100ft)']


def compare_document(docx, operator):
    parsed = parse_docx(docx)
    if parsed['status'] == 'REJECTED':
        return {'status': 'INPUT_REJECTED', 'reason': parsed['error'], 'findings': []}
    try:
        source = request('well', operator)
    except (ValueError, TypeError) as error:
        return {'status': 'REFERENCE_INPUT_ERROR', 'reason': str(error), 'findings': [], 'records': parsed['records']}
    ref = source['reference']; findings = []
    table = unique_table(parsed, 'Tubular and Casing Hardware', 'hardware')
    candidates = [r for r in rows(table) if regular_columns(r)] if table else []
    headers = [r for r in candidates if [norm(c['raw_text']) for c in r] == [norm(x) for x in HW_HEADERS]]
    units = [r for r in candidates if [norm(c['raw_text']) for c in r] == [norm(x) for x in HW_UNITS]]
    counts = Counter(r['Description'] for r in ref['hardware'])
    valid = candidates if len(headers) == len(units) == 1 and units[0][0]['locator']['row'] == headers[0][0]['locator']['row'] + 1 else []
    for original, display in zip(ref['hardware'], ref['hardware_display']):
        name = original['Description']
        matches = [r for r in valid if len(r) == 9 and r[0]['raw_text'] == name]
        row = matches[0] if len(matches) == counts[name] == 1 else None
        for col, key in enumerate(HARDWARE_FIELDS[1:], 1):
            raw_expected = original.get(key)
            expected = display[key]
            proven = raw_expected is not None and str(raw_expected).strip() != '' and expected != '-' and not ref['geometry'].get('source_input_error')
            if key not in ('MD (m)', 'Size (in)', 'Grade') and type(raw_expected) not in (int, float):
                proven = False  # no malformed/textual engineering reference becomes a match
            if key == 'Grade' and not isinstance(raw_expected, str):
                proven = False
            if name == 'CT' and key not in ('MD (m)', 'Grade') and number(str(raw_expected), '')[0] == 0:
                proven = False  # source ct_setting_depth treats optional zero as unmeasured
            record = row[col] if row and norm(row[col]['column_label'] or '') == norm(HW_HEADERS[col]) else None
            numeric = number(str(expected), '')[0] is not None
            f = finding(record if proven else None, 'hardware.' + key, expected, raw_expected, '',
                'installed_geometry.md_bounds / positive_size; phase_10_procedure.build_master_context Hardware projection',
                numeric=numeric, reason='Unique independent and printed Description; exact physical header and unit grid')
            if not proven and record is not None:
                f.update(locator=record['locator'], section=record['section'], slurry=record['association'],
                    raw_reported_text=record['raw_text'], reported_state=record['value_state'],
                    reason='Reference missing/untyped, source-masked, CT zero unmeasured, or supplied geometry rejected; no comparison')
            f.update(hardware=name, unit=HW_UNITS[col])
            findings.append(f)
    if ref['well']:
        table = unique_table(parsed, 'Temperature', 'geothermal')
        candidates = [r for r in rows(table) if regular_columns(r)] if table else []
        headers = [r for r in candidates if [norm(c['raw_text']) for c in r] == [norm(x) for x in TEMP_HEADERS]]
        data = [r for r in candidates if len(r) == 4 and len(headers) == 1 and r[0]['locator']['row'] > headers[0][0]['locator']['row']]
        row = data[0] if len(data) == 1 else None
        for col, key in enumerate(('geo_md', 'geo_tvd', 'bhst', 'geo_gradient')):
            f = finding(row[col] if row else None, 'well.' + key, ref['well']['display'][key], ref['well']['full_precision'][key], '',
                'well_profile.resolve_well_profile; phase_10_procedure.build_master_context temperature projection')
            f['unit'] = ('m', 'm', 'degF', 'degF/100ft')[col]
            findings.append(f)
    geometry = ref['geometry']
    findings.append({'field': 'geometry.reference', 'locator': None, 'section': 'hardware', 'slurry': None,
        'raw_reported_text': None, 'reported_state': 'NO_DIRECT_WORD_MAPPING', 'unit': 'source model units',
        'source_function': 'cement_chart_model.resolve_chart_geometry / interval_volume / resolve_cement_placement',
        'source_rounded_expected': None, 'full_precision_expected': geometry, 'delta': None, 'tolerance': None,
        'result': geometry['status'], 'association_proof': 'Independent job, explicit Hardware/target/excess and client volume only',
        'reason': geometry.get('reason', 'Full annular capacity is informational, not required client volume; client volumes control source placement, never geometry-based automatic FAIL')})
    findings.append({'field': 'job.word_identity', 'locator': None, 'section': None, 'slurry': None,
        'raw_reported_text': None, 'reported_state': 'EXCLUDED_COVER', 'unit': 'canonical job identity',
        'source_function': 'materials_db.JOB_TYPES / cement_chart_model.CHART_JOBS',
        'source_rounded_expected': operator['job_type'], 'full_precision_expected': operator['job_type'],
        'delta': None, 'tolerance': None, 'result': 'NOT_VERIFIABLE', 'association_proof': 'Independent job only',
        'reason': 'C01R excludes the cover job label; support matrix is not a Word job-match or fifteen-job UAT'})
    return finish(parsed, source, findings, [
        'Repeated Hardware descriptions, missing inputs and source-masked/CT-unmeasured fields remain NOT_VERIFIABLE',
        'Geometry, capacity and placement are independent informational projections; no client-volume replacement or inverse formulation',
        'Plug/Squeeze/CT chart paths unsupported; CT setting depth uses its separate source authority',
        'Placement prose/overrides, running instructions, excluded surveys/centralizers/charts and full 15-job goldens remain unverified'])


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('operator_json');ap.add_argument('docx');args=ap.parse_args()
    try:
        p=Path(args.operator_json).resolve(strict=True)
        if not p.is_relative_to(ROOT):raise ValueError('Operator input outside runtime')
        result=compare_document(args.docx,read_json(p.read_text()))
    except (ValueError, OSError, TypeError) as error:
        result={'status':'REFERENCE_INPUT_ERROR','reason':str(error),'findings':[]}
    print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))
    return 0 if result['status']=='PARTIAL_FINDINGS_ONLY' else 2


if __name__=='__main__':raise SystemExit(main())
