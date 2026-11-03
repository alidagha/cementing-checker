"""Independent identity/evidence invariants; inventory is never Golden admission."""
import ast
import copy
import hashlib
import json
import re
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JOBS = ['CSG 30"', 'CSG 24"', 'CSG 20"', 'CSG 18 5/8"', 'CSG 13 3/8"', 'CSG 9 5/8"', 'CSG 7"', 'LNR 7"', 'LNR 5"', 'LNR 4 1/2"', 'CMT PLUG', 'CMT PLUG WITH CT', 'CMT SQUEEZE', 'TIE BACK LNR 7"', 'TIE BACK LNR 5"']
JIDS = [f'J{i:02}' for i in range(1, 16)]
XIDS = [f'X{i:02}' for i in range(1, 23)]
PIN = '60dffefb8c941ad90cb7caba0992126a35803717'
TEMPLATE = 'a1128b0e9352e1dd7c8768eecc9335c50858356cee80ed33c0ec275e26c4d08b'


def ledger():
    return json.loads((ROOT / 'docs/coverage/claim-coverage-ledger.v1.json').read_text())


def unique(values):
    assert len(values) == len(set(values)), 'duplicate identity'


def validate(d, check_files=False):
    assert [j['case_id'] for j in d['jobs']] == JIDS
    assert [j['job_type'] for j in d['jobs']] == JOBS
    assert [x['case_id'] for x in d['cross_cases']] == XIDS
    b = d['baseline']
    assert b['source_commit'] == PIN and b['template_sha256'] == TEMPLATE
    assert b['template_blob'] == '1d77ebb7140e1bf0fa3d7cbd092f215290a187c0'
    assert (b['source_files'], b['accepted_files'], b['dependency_pins']) == (143, 11, 51)
    cs = d['claims']; ids = [c['claim_id'] for c in cs]; unique(ids); ids = set(ids)
    for j in d['jobs']:
        assert j['golden_status'] == 'NOT_RUN'
        assert set(j['acceptance_A_H']) == set('ABCDEFGH')
        assert set(j['acceptance_A_H'].values()) == {'NOT_RUN'}
        assert set(j['claim_ids']) == ids
    for x in d['cross_cases']:
        assert x['authentic_golden_status'] == 'NOT_RUN'
        assert set(x['claim_ids']) <= ids and x['claim_ids']
    cells = d['job_cross_case_matrix']
    pairs = [(c['job_id'], c['case_id']) for c in cells]; unique(pairs)
    assert set(pairs) == {(j, x) for j in JIDS for x in XIDS}
    for c in cells:
        assert c['applicability'] in ('APPLICABLE', 'EXCLUDED', 'UNKNOWN_WITH_REASON')
        assert c['reason'] and c['owner'] and c['next_proof']
        assert c['golden_status'] == 'NOT_RUN' and c['verified_claim_credit'] == 0
        assert set(c['claim_ids']) <= ids
    for c in cs:
        assert c['claim_evaluation'] == 'NOT_RUN' and c['golden_status'] == 'NOT_RUN'
        assert c['verified_claim_credit'] == 0 and c['word']['instance_physical_proof'] is False
        assert c['ambiguity_or_exclusion_reason'] and all(c['blocker'].values())
        assert c['applicability']['jobs'] == JIDS and c['applicability']['reason']
        assert c['cross_cases'] and set(c['cross_cases']) <= set(XIDS)
        assert set(c['dependencies']) <= ids and c['claim_id'] not in c['dependencies']
        assert c['evidence_maturity'] in ('COMPONENT_VERIFIED', 'PARTIAL', 'BLOCKED', 'NOT_RUN')
        if c['evidence_maturity'] == 'COMPONENT_VERIFIED':
            assert c['source'] and c['checker'] and c['component_tests']
            assert c['kind'] == 'SEMANTIC_PATTERN'
        if c['kind'] in ('TEMPLATE_SLOT', 'STATIC_TEMPLATE_CANDIDATE'):
            assert c['evidence_maturity'] == 'NOT_RUN' and c['source'] is None
        if check_files:
            for ref in [c['source'], c['checker'], c['ui_report']['route']]:
                if not ref:
                    continue
                base = ROOT / 'snapshot' if ref['origin'] == 'pinned_source' else ROOT
                p = base / ref['path']; assert p.is_file() and not p.is_symlink()
                assert p.resolve().is_relative_to(base.resolve())
                assert hashlib.sha256(p.read_bytes()).hexdigest() == ref['sha256']
                nodes = ast.parse(p.read_text()).body
                for name in ref['symbol'].split('.'):
                    node = next(n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name)
                    nodes = node.body
                assert node.lineno == ref['line']
            for ref in c['component_tests']:
                path, name = ref.split('::'); tree = ast.parse((ROOT / path).read_text())
                assert any(isinstance(n, ast.FunctionDef) and n.name == name for n in tree.body)
    a = d['accounting']
    assert a['patterns'] == len(cs)
    assert a['component_mapped_patterns'] == sum(c['evidence_maturity'] == 'COMPONENT_VERIFIED' for c in cs)
    assert a['template_slots'] == sum(c['kind'] == 'TEMPLATE_SLOT' for c in cs)
    assert a['verified_claim_instances'] == a['golden_jobs_passed'] == a['physical_instance_locators_proved'] == 0
    assert a['inventory_exhaustiveness'] == 'UNVERIFIED'


def test_inventory_identities_references_and_credit():
    d = ledger()
    validate(d, check_files=True)
    template = ROOT / 'snapshot/master_template.docx'
    assert hashlib.sha256(template.read_bytes()).hexdigest() == TEMPLATE
    with ZipFile(template) as package:
        xml = ET.fromstring(package.read('word/document.xml'))
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    expressions = []
    for paragraph in xml.findall('.//w:p', ns):
        text = ''.join(paragraph.itertext())
        expressions.extend(re.findall(r'{{(.*?)}}', text))
    # Compare the inventory to immutable template presence, never to a rendered value.
    actual = [hashlib.sha256(x.strip().encode()).hexdigest() for x in expressions]
    recorded = [c['word']['template_expression_sha256'] for c in d['claims'] if c['kind'] == 'TEMPLATE_SLOT']
    assert actual == recorded
    canonical = json.loads((ROOT / 'docs/uat/job-manifest.json').read_text())
    assert [j['job_type'] for j in canonical['jobs']] == JOBS
    source = ast.parse((ROOT / 'snapshot/materials_db.py').read_text())
    assignment = next(n for n in source.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'JOB_TYPES' for t in n.targets))
    assert len(assignment.value.elts) == 15


@pytest.mark.parametrize('mutation', ['missing_job', 'duplicate_job', 'missing_case', 'duplicate_case', 'missing_cell', 'duplicate_claim', 'bad_reference', 'bad_crosscase', 'bad_pin', 'bad_template', 'unproved_verified', 'golden', 'no_reason', 'no_exclusion_reason', 'false_numerator', 'physical', 'stale_count'])
def test_inventory_rejects_false_evidence(mutation):
    d = copy.deepcopy(ledger())
    if mutation == 'missing_job': d['jobs'].pop()
    elif mutation == 'duplicate_job': d['jobs'][1] = copy.deepcopy(d['jobs'][0])
    elif mutation == 'missing_case': d['cross_cases'].pop()
    elif mutation == 'duplicate_case': d['cross_cases'][1] = copy.deepcopy(d['cross_cases'][0])
    elif mutation == 'missing_cell': d['job_cross_case_matrix'].pop()
    elif mutation == 'duplicate_claim': d['claims'].append(copy.deepcopy(d['claims'][0]))
    elif mutation == 'bad_reference': d['claims'][0]['dependencies'] = ['NONEXISTENT']
    elif mutation == 'bad_crosscase': d['claims'][0]['cross_cases'] = ['X23']
    elif mutation == 'bad_pin': d['baseline']['source_commit'] = '0' * 40
    elif mutation == 'bad_template': d['baseline']['template_sha256'] = '0' * 64
    elif mutation == 'unproved_verified': next(c for c in d['claims'] if c['kind'] == 'TEMPLATE_SLOT')['evidence_maturity'] = 'COMPONENT_VERIFIED'
    elif mutation == 'golden': d['jobs'][0]['golden_status'] = 'PASS'
    elif mutation == 'no_reason': d['job_cross_case_matrix'][0]['reason'] = ''
    elif mutation == 'no_exclusion_reason': d['claims'][0]['ambiguity_or_exclusion_reason'] = ''
    elif mutation == 'false_numerator': d['accounting']['verified_claim_instances'] = 1
    elif mutation == 'physical': d['claims'][0]['word']['instance_physical_proof'] = True
    elif mutation == 'stale_count': d['accounting']['patterns'] += 1
    with pytest.raises(AssertionError): validate(d)
