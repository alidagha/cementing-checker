"""G07 explicit-DV receipts consume unchanged G06-B/C04, never a second engine."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
import g07_report as g
import g06b_dead_volume as b
from test_g07 import controls, procedure_control, ready_boundary_page, submitted, ui_boundary


@pytest.fixture(scope='module')
def dv_session():
    op = json.loads((g.ROOT/'c04/fixtures/operator-main.json').read_text())
    s = g.PrivateSession(); path = s.store('source.docx', (g.ROOT/'c04/fixtures/synthetic-main.docx').read_bytes())
    baseline = s.check(path, submitted(op))
    return s, path, deepcopy(baseline)


@pytest.fixture
def checked(dv_session):
    s, path, baseline = dv_session
    s.result = deepcopy(baseline); s.document = path; s.revision = baseline['receipt']['revision']
    s.volume_preview = None; s.volume_request_sha = None
    s.dv_preview = None; s.dv_request_sha = None
    return s, path, deepcopy(baseline)


@pytest.mark.parametrize('value', [0, 10])
def test_explicit_dv_uses_original_C04_oracle_without_changing_baseline(checked, value):
    s, path, baseline = checked; original = path.read_bytes()
    preview = s.preview_dead_volume('Main', value)
    oracle = b.preview_source.preview(path, baseline['receipt']['inputs_snapshot']['cement'],
        {'slurry': 'Main', 'corrected_dead_volume_bbl': value})
    impact = preview['impact']; ledger = impact['impact_ledger']
    assert impact['c04'] == oracle and impact['original_c03'] == baseline['results']['C03']
    assert ledger['source_after_tables'] == oracle['selected_dead_volume_preview']['after_source_tables']
    assert len(ledger['gross_additives']) == 3
    assert ledger['historical_exact_delta'] is None and ledger['historical_change'] == 'NOT_VERIFIABLE'
    assert all(row['source_after_full_precision'] is row['historical_exact_delta'] is None for row in ledger['gross_additives'])
    assert all(row['original_Word_records'][0]['locator'] for row in ledger['gross_additives'])
    assert s.current() == baseline and path.read_bytes() == original
    assert preview['receipt']['request']['baseline_report_id'] == baseline['report_id']
    assert preview['receipt']['request']['corrected_dead_volume_bbl'] == value
    assert s.current_dead_volume_preview('Main', value) == preview
    assert b.private_path(path, '.docx') == path
    assert impact['docx_written'] is impact['word_modified'] is False
    assert {r['classification'] for r in impact['unresolved_dependencies']} == {'MANUAL_REVIEW_REQUIRED', 'NOT_VERIFIABLE'}
    assert ledger['source_invariants_and_unselected_slurries']['source_invariants_preserved'] is True
    if value == 0:
        assert ledger['source_after_total_preparation_water_full_precision_bbl'] == ledger['pure_mix_water_full_precision_bbl']


@pytest.fixture(scope='module')
def proved_preview(dv_session):
    s, _, baseline = dv_session
    s.result = deepcopy(baseline)
    return deepcopy(s.preview_dead_volume('Main', 10))


def restore_preview(s, preview):
    s.dv_preview = deepcopy(preview)
    s.dv_request_sha = preview['receipt']['request_sha256']


def test_invalid_values_roles_and_unadmitted_baselines_never_dispatch(checked, monkeypatch):
    s, path, baseline = checked
    def unexpected(*a, **k): pytest.fail('Invalid proposal reached G06-B transport')
    monkeypatch.setattr(b, 'inspect_selection', unexpected)
    for value in (None, -1, True, False, '0', float('nan'), float('inf'), float('-inf'), 10**400):
        with pytest.raises(ValueError): s.preview_dead_volume('Main', value)
        assert s.dv_preview is None and s.current() == baseline
    for role in (None, '', 'Tail', 'Spacer', ['Main'], ['Main', 'Main']):
        with pytest.raises(ValueError): s.preview_dead_volume(role, 0)
        assert s.dv_preview is None and s.current() == baseline
    for kind in ('absent', 'incomplete', 'rejected', 'c03', 'operator', 'duplicate-role', 'report-id'):
        s.result = deepcopy(baseline)
        if kind == 'absent': s.result = None
        else:
            if kind == 'incomplete': s.result['run_outcome'] = 'INPUT_INCOMPLETE'
            elif kind == 'rejected': s.result['receipt']['cement_admission']['status'] = 'INPUT_REJECTED'
            elif kind == 'c03': s.result['results']['C03']['status'] = 'INPUT_REJECTED'
            elif kind == 'operator': s.result['receipt']['inputs_snapshot']['cement']['slurries']['Main']['density_pcf'] = 999
            elif kind == 'duplicate-role': s.result['receipt']['inputs_snapshot']['cement']['active_fluids'].append('Main')
            if kind != 'report-id':
                s.result['report_id'] = g.report_identity(s.result); s.result['receipt']['report_id'] = s.result['report_id']
            else: s.result['report_id'] = '0'*64
        with pytest.raises(ValueError): s.preview_dead_volume('Main', 0)
        assert s.dv_preview is None
    assert path.read_bytes() == (g.ROOT/'c04/fixtures/synthetic-main.docx').read_bytes()


def test_dv_lifecycle_no_resurrection_cross_session_or_G06A_interference(checked, proved_preview):
    s, path, baseline = checked; restore_preview(s, proved_preview)
    assert s.current_dead_volume_preview('Main', 10) == proved_preview
    assert s.current_volume_preview('Main', 55) is None
    assert s.current_dead_volume_preview('Main', 10) == proved_preview
    assert s.current_dead_volume_preview('Main', 0) is None
    assert s.current_dead_volume_preview('Main', 10) is None
    restore_preview(s, proved_preview)
    with pytest.raises(ValueError): s.current_dead_volume_preview('Tail', 10)
    assert s.dv_preview is None and s.current() == baseline
    restore_preview(s, proved_preview)
    other = g.PrivateSession(); other.result = deepcopy(baseline); other.document = path
    restore_preview(other, proved_preview)
    with pytest.raises(ValueError): other.current_dead_volume_preview('Main', 10)
    assert other.dv_preview is None
    assert s.invalidate('new-independent-input') and s.current() is None and s.dv_preview is None


def test_tampered_preview_claims_request_and_response_fail_closed(checked, proved_preview):
    s, _, baseline = checked
    for kind in ('request', 'response', 'bindings', 'nonce'):
        restore_preview(s, proved_preview)
        if kind == 'request': s.dv_preview['receipt']['request']['corrected_dead_volume_bbl'] = 0
        elif kind == 'response': s.dv_preview['impact']['impact_ledger']['historical_exact_delta'] = 0
        elif kind == 'bindings': s.dv_preview['receipt']['g06b_bindings']['selected_claims_sha256'] = '0'*64
        else: s.dv_preview['receipt']['preview_run_id'] = 'forged'
        with pytest.raises(ValueError): s.current_dead_volume_preview('Main', 10)
        assert s.dv_preview is None and s.current() == baseline


def test_fresh_inspection_and_exact_edit_are_rechecked(checked, proved_preview, monkeypatch):
    s, path, baseline = checked
    inspection = b.inspect_selection(path, baseline['receipt']['inputs_snapshot']['cement'], 'Main')
    for kind in ('schema', 'status', 'operation', 'source', 'document', 'operator', 'c03', 'claims', 'role'):
        bad = deepcopy(inspection)
        if kind in ('schema', 'status', 'operation'): bad[kind] = 'forged'
        elif kind == 'source': bad['bindings']['source_sha'] = '0'*40
        elif kind == 'c03': bad['original_c03']['status'] = 'forged'
        elif kind == 'claims': bad['selected_claims']['gross'] = []
        else: bad['bindings'][{'document':'original_document_sha256', 'operator':'operator_sha256', 'role':'selected_slurry'}[kind]] = 'forged'
        monkeypatch.setattr(b, 'inspect_selection', lambda *a, value=bad: deepcopy(value))
        with pytest.raises(ValueError): s.preview_dead_volume('Main', 10)
        assert s.dv_preview is None and s.current() == baseline
    monkeypatch.setattr(b, 'inspect_selection', lambda *a: deepcopy(inspection))
    def response(doc, operator, edit):
        assert doc == path and operator == baseline['receipt']['inputs_snapshot']['cement']
        assert edit == {'schema':'g06b.1','bindings':inspection['bindings'],'slurry':'Main','corrected_dead_volume_bbl':10}
        return deepcopy(proved_preview['impact'])
    monkeypatch.setattr(b, 'dead_volume_impact', response)
    assert s.preview_dead_volume('Main', 10)['impact'] == proved_preview['impact']
    for kind in ('bindings', 'c03', 'c04', 'ledger', 'invariant', 'write'):
        bad = deepcopy(proved_preview['impact'])
        if kind == 'bindings': bad['bindings']['selected_claims_sha256'] = 'forged'
        elif kind == 'c03': bad['original_c03']['water_findings'] = []
        elif kind == 'c04': bad['c04']['selected_dead_volume_preview']['slurry'] = 'Tail'
        elif kind == 'ledger': bad['impact_ledger']['gross_additives'][0]['source_after_full_precision'] = 1
        elif kind == 'invariant': bad['c04']['selected_dead_volume_preview']['unaffected']['source_invariants_preserved'] = False
        else: bad['word_modified'] = True
        monkeypatch.setattr(b, 'dead_volume_impact', lambda *a, value=bad: deepcopy(value))
        with pytest.raises(ValueError): s.preview_dead_volume('Main', 10)
        assert s.dv_preview is None and s.current() == baseline


@pytest.mark.parametrize('kind', ['timeout', 'filesystem'])
def test_worker_errors_are_safe_and_leave_no_preview(checked, proved_preview, monkeypatch, kind):
    from subprocess import TimeoutExpired
    s, path, baseline = checked; restore_preview(s, proved_preview)
    def failed(*a):
        if kind == 'timeout': raise TimeoutExpired('/private/secret', 120, stderr='PRIVATE-PAYLOAD')
        raise OSError('/private/secret PRIVATE-PAYLOAD')
    monkeypatch.setattr(b, 'inspect_selection', failed)
    with pytest.raises(ValueError) as error: s.preview_dead_volume('Main', 10)
    assert 'private' not in str(error.value) and 'PAYLOAD' not in str(error.value)
    assert s.dv_preview is None and s.current() == baseline


@pytest.mark.parametrize('kind', ['hidden-gross', 'split-gross', 'merged', 'duplicate-note'])
def test_G07_admission_never_bypasses_G06B_physical_refusal(dv_session, kind):
    from docx import Document
    from docx.oxml import OxmlElement
    from io import BytesIO
    _, path, baseline = dv_session; original = path.read_bytes(); d = Document(BytesIO(original))
    table = next(t for t in d.tables if t.cell(0,0).text == 'Main Cement Slurry Additives Data')
    p = table.rows[2].cells[6].paragraphs[0]
    if kind == 'hidden-gross': p.runs[0]._r.get_or_add_rPr().append(OxmlElement('w:vanish'))
    elif kind == 'split-gross': text = p.text; p.runs[0].text = text[:2]; p.add_run(text[2:])
    elif kind == 'merged': table.rows[2].cells[5].merge(table.rows[2].cells[6])
    else:
        note = next(p for p in d.paragraphs if 'Mix above Additives in' in p.text)
        note._p.addnext(deepcopy(note._p))
    stream = BytesIO(); d.save(stream)
    s = g.PrivateSession(); bad = s.store('unproved.docx', stream.getvalue())
    checked = s.check(bad, deepcopy(baseline['receipt']['inputs_snapshot'])); before = deepcopy(checked)
    assert checked['run_outcome'] == 'PARTIAL_FINDINGS_ONLY'
    with pytest.raises(ValueError): s.preview_dead_volume('Main', 10)
    assert s.dv_preview is None and s.current() == before and path.read_bytes() == original


def test_foreign_document_symlink_and_traversal_do_not_dispatch(checked, monkeypatch):
    s, path, baseline = checked
    def unexpected(*a): pytest.fail('Unsafe path reached G06-B')
    monkeypatch.setattr(b, 'inspect_selection', unexpected)
    alias = s.folder/'alias.docx'; alias.symlink_to(path)
    other = g.PrivateSession(); foreign = other.store('foreign.docx', path.read_bytes())
    for unsafe in (alias, foreign, s.folder/'..'/s.folder.name/path.name):
        s.result = deepcopy(baseline); s.document = unsafe
        with pytest.raises(ValueError): s.preview_dead_volume('Main', 0)
        assert s.dv_preview is None


def test_two_slurries_keep_unselected_source_and_G06A_preview(dv_session):
    from docx import Document
    from io import BytesIO
    from docx.table import _Cell
    from docx.oxml.ns import qn
    _, _, baseline = dv_session
    op = deepcopy(baseline['receipt']['inputs_snapshot']['cement']); recipe = op['slurries'].pop('Main')
    op.update(job_type='CSG 13 3/8"', active_fluids=['Lead','Tail'])
    op['slurries'] = {'Lead':recipe, 'Tail':dict(recipe, density_pcf=118, client_volume_bbl=30)}
    s = g.PrivateSession(); path = s.folder/'source-two.docx'
    g.c04_runtime.call({'action':'fixture','operator':op,'docx':str(path),
        'fixture':{'Lead':{'dead':5,'tank':'Mud Reserve Tanks'},'Tail':{'dead':2,'tank':'Batch Mixer Tanks'}}})
    # Separate literal source-valued variant admits C10/G06-A targets. Canonical
    # source NOTE/gross grid is retained, never relaxed to obtain DV eligibility.
    original = path.read_bytes(); first = s.check(s.store('source.docx', original), submitted(op))
    d = Document(BytesIO(original))
    for f in first['results']['C03']['c02']['findings']:
        if f['field'] in ('yield','sacks'):
            loc = f['locator']; table = d.element.body[loc['body_block']]
            cell = table.findall(qn('w:tr'))[loc['row']].findall(qn('w:tc'))[loc['column']]
            _Cell(cell, None).text = f['raw_reported_text']
    stream = BytesIO(); d.save(stream); p = s.store('literal-variant.docx', stream.getvalue())
    before = deepcopy(s.check(p, submitted(op))); a = deepcopy(s.preview_volume('Lead', 55))
    dv = s.preview_dead_volume('Lead', 0)
    assert s.current_volume_preview('Lead', 55) == a and s.current() == before
    unselected = dv['impact']['impact_ledger']['source_invariants_and_unselected_slurries']['unselected_slurry_references']
    assert unselected == {'Tail':before['results']['C03']['c02']['reference']['slurries']['Tail']}
    assert s.current_volume_preview('Lead', 60) is None
    assert s.current_dead_volume_preview('Lead', 0) == dv
    assert path.read_bytes() == original


def test_native_widget_contract_zero_positive_and_stale_invalidation(ui_boundary):
    app = ready_boundary_page(ui_boundary); app.button[0].click().run()
    s = app.session_state['_private']; before = deepcopy(s.current())
    assert app.number_input(key='g06b:dv').value is None
    app.selectbox(key='g06b:selected').select('Main').run()
    app.number_input(key='g06b:dv').set_value(0.0).run()
    action = next(b for b in app.button if b.label == 'Preview explicit Dead Volume impact')
    assert not action.disabled
    action.click().run(); assert not app.exception
    assert s.dv_preview['impact']['impact_ledger']['explicit_dead_volume_bbl'] == 0
    assert s.current() == before
    app.number_input(key='g06b:dv').set_value(10.0).run()
    assert s.dv_preview is None and s.current() == before
    assert app.text_area(key='engineer_message').value == before['message']
    app.number_input(key='CSG 20":Main:volume').set_value(51).run()
    assert s.result is None and s.dv_preview is None
    assert not any(t.key == 'engineer_message' for t in app.text_area)


def test_C09_independent_DV_is_not_reused_or_changed(controls, procedure_control):
    _, inputs, _ = procedure_control; inputs = deepcopy(inputs)
    inputs['procedure']['preparation']['Main']['dead_volume_bbl'] = 77
    s = g.PrivateSession(); path = s.store('source.docx', controls['good'])
    before = deepcopy(s.check(path, inputs))
    assert before['results']['C09']['reference']['reference']['preparation']['Main']['dead_volume_bbl'] == 77
    with pytest.raises(ValueError): s.current_dead_volume_preview('Main', None)
    dv = s.preview_dead_volume('Main', 0)
    assert dv['impact']['impact_ledger']['explicit_dead_volume_bbl'] == 0
    assert s.current() == before and path.read_bytes() == controls['good']
