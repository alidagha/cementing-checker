"""Small shared structural helpers; raw C01R records are always retained."""
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'c02'))
from c02_compare import assess, number
from checker_parser import parse_docx, norm
from c02_engine import SOURCE_SHA


def tables(parsed):
    groups = defaultdict(list)
    for record in parsed['records']:
        loc = record['locator']
        if loc.get('table') is not None:
            groups[(loc['body_block'], loc['table'], tuple(loc['table_path']))].append(record)
    return list(groups.values())


def rows(table):
    grouped = defaultdict(lambda: defaultdict(list))
    for record in table:
        grouped[record['locator']['row']][record['locator']['column']].append(record)
    # A multi-paragraph cell is ambiguous, never silently concatenated to a scalar.
    return [list(v[0] for _, v in sorted(cells.items()))
            for _, cells in sorted(grouped.items()) if all(len(v) == 1 for v in cells.values())]


def regular_columns(row):
    """A scalar header proves units only on the same unmerged physical grid."""
    return all(c['locator']['column'] == i and c['locator']['column_span'] == 1 for i, c in enumerate(row))


def unique_table(parsed, anchor, section):
    found = [t for t in tables(parsed) if t[0]['table_anchor'] == anchor and t[0]['section'] == section]
    return found[0] if len(found) == 1 else None


def finding(record, field, expected, raw_expected, unit, function, tolerance=0, numeric=True, reason='Exact semantic table/header/row identity'):
    result = {'field': field, 'locator': record['locator'] if record else None,
        'section': record['section'] if record else None, 'slurry': record['association'] if record else None,
        'association_proof': reason, 'raw_reported_text': record['raw_text'] if record else None,
        'unit': unit, 'source_rounded_expected': str(expected), 'full_precision_expected': raw_expected,
        'source_function': function, 'source_sha': SOURCE_SHA, 'tolerance': str(tolerance),
        'result': 'NOT_VERIFIABLE', 'reported_state': 'MISSING', 'delta': None,
        'reason': 'Missing, duplicate, split-cell or ambiguous identity/header'}
    if record is not None:
        if numeric:
            result.update(assess(record['raw_text'], unit, expected, tolerance))
        else:
            raw = record['raw_text']
            _, state = number(raw, '')
            if not raw.strip() or state in ('DASH', 'NA_PRINTED'):
                result.update(reported_state=state)
            else:
                result.update(result='MATCH' if norm(raw) == norm(str(expected)) else 'DISCREPANCY',
                    reported_state=record['value_state'], reason='Source display equivalence; partial finding only')
    return result


def finish(parsed, source, findings, limitations):
    mapped = {str(f['locator']) for f in findings if f['locator'] is not None and f['result'] in ('MATCH', 'DISCREPANCY')}
    for f in findings:
        f.update(source_document_sha256=parsed['source_document_sha256'], parser_schema=parsed['schema_version'], source_sha=SOURCE_SHA)
    return {'status': 'PARTIAL_FINDINGS_ONLY', 'source_document_sha256': parsed['source_document_sha256'],
        'parser_schema': parsed['schema_version'], 'reference': source, 'findings': findings,
        'summary': dict(Counter(f['result'] for f in findings)), 'records': parsed['records'],
        'unverified_record_orders': [r['source_order'] for r in parsed['records'] if str(r['locator']) not in mapped],
        'limitations': limitations}
