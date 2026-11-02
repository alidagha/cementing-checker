"""G08-A4 source-backed preview controls; one whole-module shard assignment."""
from copy import deepcopy
from pathlib import Path
import tempfile

from docx import Document
import pytest
import g07_report as g
from test_g07 import controls, procedure_control, ready_boundary_page, submitted, ui_boundary


@pytest.fixture(scope='module')
def volume_control(controls):
    from c02_compare import engine
    from test_c02 import fixture
    op = deepcopy(controls['op']); source = engine(op); row = source['slurries']['Main']
    # An eligible literal manual-program layout, rendered from actual locked-source
    # values. This is neither the pinned App template nor a Golden/export claim.
    with tempfile.TemporaryDirectory(dir=g.ROOT/'tmp', prefix='g08a4-control-') as folder:
        path = fixture(Path(folder)/'source.docx', values={'yield': row['display']['yield_cuft_sk'],
            'sacks': row['blend'][0]['sks or lbs'].removesuffix(' sks'),
            'water': row['display']['mix_water_bbl'], 'density': row['density']}, labrows=[])
        yield {'docx': path.read_bytes(), 'op': op, 'source': source}


def test_bound_volume_preview_keeps_authoritative_run_and_original_bytes(volume_control):
    session = g.PrivateSession(); path = session.store('source.docx', volume_control['docx'])
    baseline = session.check(path, submitted(volume_control['op']))
    before = deepcopy(baseline); original = path.read_bytes()
    preview = session.preview_volume('Main', 55)
    impact = preview['impact']; rows = {r['dependency']: r for r in impact['source_dependency_ledger']}
    assert rows['sacks']['old_source_display'] == '154.4' and rows['sacks']['new_source_display'] == '169.9'
    assert rows['pure_mix_water']['old_source_display'] == '34.8' and rows['pure_mix_water']['new_source_display'] == '38.3'
    assert rows['yield']['old_source_display'] == rows['yield']['new_source_display'] == '1.818'
    assert rows['calculated_600ml_recipe']['classification'] == 'SOURCE_UNCHANGED'
    assert rows['client_requested_volume']['source_display_changed'] is None
    sacks = next(f for f in impact['word_claim_impacts'] if f['field'] == 'sacks')
    assert sacks['original_raw_claim'] == '154.4 sks' and sacks['new_comparison'] == 'DISCREPANCY'
    assert preview['receipt']['request']['baseline_report_id'] == baseline['report_id']
    assert preview['receipt']['request']['original_operator_sha256'] == baseline['receipt']['cement_operator_sha256']
    assert impact['edited_operator_reference']['slurries']['Main']['client_volume_bbl'] == 55
    assert session.current() == before and baseline['receipt']['inputs_snapshot']['cement']['slurries']['Main']['client_volume_bbl'] == 50
    assert session.current_volume_preview('Main', 55) == preview
    assert path.read_bytes() == original and impact['docx_written'] is impact['word_modified'] is False


def checked_volume_session(control):
    session = g.PrivateSession(); path = session.store('source.docx', control['docx'])
    baseline = session.check(path, submitted(control['op']))
    return session, path, baseline


def test_volume_preview_invalid_controls_never_dispatch(volume_control, monkeypatch):
    import g06a_client_volume
    session, path, baseline = checked_volume_session(volume_control); original = path.read_bytes()
    before = deepcopy(baseline)
    def no_transport(*args, **kwargs): pytest.fail('Invalid controls reached source transport')
    monkeypatch.setattr(g06a_client_volume.subprocess, 'run', no_transport)
    for value in (None, 0, -1, True, '55', float('nan'), float('inf')):
        with pytest.raises(ValueError): session.preview_volume('Main', value)
        assert session.volume_preview is None and session.current() == before
    for role in (None, '', 'Tail', 'Scavenger', ['Main', 'Main']):
        with pytest.raises(ValueError): session.preview_volume(role, 55)
        assert session.volume_preview is None and session.current() == before
    assert path.read_bytes() == original


def test_volume_preview_without_current_run_is_not_available():
    session = g.PrivateSession()
    with pytest.raises(ValueError): session.preview_volume('Main', 55)
    assert session.volume_preview is None


def test_volume_preview_noop_and_proposal_lifecycle_preserve_baseline(volume_control):
    session, path, baseline = checked_volume_session(volume_control); before = deepcopy(baseline)
    preview = session.preview_volume('Main', 50)
    assert all(r['classification'] == 'SOURCE_UNCHANGED' for r in preview['impact']['source_dependency_ledger'])
    assert session.current_volume_preview('Main', 55) is None and session.current() == before
    assert session.current_volume_preview('Main', 50) is None  # no resurrection after changing back
    preview = session.preview_volume('Main', 55)
    for dependency in preview['impact']['unresolved_dependencies']:
        assert dependency['classification'] in ('NOT_VERIFIABLE', 'MANUAL_REVIEW_REQUIRED')
    with pytest.raises(ValueError): session.current_volume_preview('Tail', 55)
    with pytest.raises(ValueError): session.current_volume_preview(None, 55)
    assert session.volume_preview is None and session.current() == before
    assert session.invalidate('changed-original-draft') and session.current() is None
    with pytest.raises(ValueError): session.current_volume_preview('Main', 55)
    assert path.read_bytes() == volume_control['docx']


def test_volume_preview_sealed_result_and_foreign_session_are_rejected(volume_control):
    session, path, baseline = checked_volume_session(volume_control)
    preview = session.preview_volume('Main', 55)
    other, _, other_baseline = checked_volume_session(volume_control)
    other.volume_preview = deepcopy(preview)
    assert other.current_volume_preview('Main', 55) is None and other.current() == other_baseline
    preview['impact']['edited_operator_reference']['slurries']['Main']['client_volume_bbl'] = 999
    with pytest.raises(ValueError): session.current_volume_preview('Main', 55)
    assert session.volume_preview is None and session.current() == baseline
    assert path.read_bytes() == volume_control['docx']


def test_volume_preview_rechecks_real_c02_c03_receipt_not_only_flags(volume_control):
    session, path, baseline = checked_volume_session(volume_control)
    before = deepcopy(baseline)
    for mutation in ('receipt-id', 'admission', 'missing-c03', 'foreign-document'):
        session.result = deepcopy(before); session.document = path
        if mutation == 'receipt-id': session.result['receipt']['report_id'] = '0'*64
        elif mutation == 'admission': session.result['receipt']['cement_admission']['status'] = 'INPUT_REJECTED'
        elif mutation == 'missing-c03': del session.result['results']['C03']
        else:
            foreign = session.folder.parent/'foreign-volume.docx'; foreign.write_bytes(path.read_bytes())
            session.document = foreign
        if mutation != 'receipt-id':
            session.result['report_id'] = g.report_identity(session.result)
            session.result['receipt']['report_id'] = session.result['report_id']
        try:
            with pytest.raises(ValueError): session.preview_volume('Main', 55)
            assert session.volume_preview is None
        finally:
            if mutation == 'foreign-document': foreign.unlink()
    assert path.read_bytes() == volume_control['docx']


@pytest.mark.parametrize('failure', ['timeout', 'oserror'])
def test_volume_preview_source_process_failure_cleans_copy_and_retains_base(volume_control, monkeypatch, failure):
    from subprocess import TimeoutExpired
    import subprocess
    session, path, baseline = checked_volume_session(volume_control); before = deepcopy(baseline)
    original_run = subprocess.run; folders = set((g.ROOT/'tmp').glob('g07-volume-*'))
    def failed_transport(command, *args, **kwargs):
        if any(str(x).endswith('g06a_client_volume.py') for x in command):
            if failure == 'timeout': raise TimeoutExpired('/private/SECRET', 120, stderr='SECRET-G06A-PAYLOAD')
            raise OSError('/private/SECRET transport unavailable')
        return original_run(command, *args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', failed_transport)
    with pytest.raises((TimeoutExpired, OSError)): session.preview_volume('Main', 55)
    assert set((g.ROOT/'tmp').glob('g07-volume-*')) == folders
    assert session.volume_preview is None and session.current() == before
    assert path.read_bytes() == volume_control['docx']


def test_volume_preview_copy_symlink_guard_never_touches_original(volume_control, monkeypatch):
    session, path, baseline = checked_volume_session(volume_control); before = deepcopy(baseline)
    original_mkdtemp = g.tempfile.mkdtemp; created = []
    def alias_copy(*args, **kwargs):
        folder = original_mkdtemp(*args, **kwargs)
        if kwargs.get('prefix') == 'g07-volume-':
            (Path(folder)/'input.docx').symlink_to(path); created.append(Path(folder))
        return folder
    monkeypatch.setattr(g.tempfile, 'mkdtemp', alias_copy)
    with pytest.raises(ValueError): session.preview_volume('Main', 55)
    assert created and all(not folder.exists() for folder in created)
    assert session.volume_preview is None and session.current() == before
    assert path.read_bytes() == volume_control['docx']


def test_pinned_template_admission_does_not_imply_g06a_physical_eligibility(controls):
    session = g.PrivateSession(); path = session.store('pinned-template.docx', controls['good'])
    baseline = session.check(path, submitted(controls['op'])); before = deepcopy(baseline)
    folders = set((g.ROOT/'tmp').glob('g07-volume-*'))
    assert baseline['receipt']['cement_admission']['status'] == 'SOURCE_ADMITTED'
    with pytest.raises(ValueError, match='PHYSICAL_REFERENCE'): session.preview_volume('Main', 55)
    assert session.volume_preview is None and session.current() == before
    assert set((g.ROOT/'tmp').glob('g07-volume-*')) == folders and path.read_bytes() == controls['good']


def test_volume_preview_never_carries_c09_dead_volume(procedure_control, volume_control):
    _, inputs, _ = procedure_control; inputs = deepcopy(inputs)
    inputs['procedure']['preparation']['Main']['dead_volume_bbl'] = 77
    session = g.PrivateSession(); path = session.store('literal.docx', volume_control['docx'])
    baseline = session.check(path, inputs); before = deepcopy(baseline)
    c09 = baseline['results']['C09']
    assert c09['reference']['operator_input_sha256'] == g.digest(inputs['procedure'])
    assert c09['reference']['reference']['preparation']['Main']['dead_volume_bbl'] == 77
    # The independent C09 source is admitted, but this literal paired-table Word
    # control has no complete Procedure sequence: do not fabricate C09 coverage.
    assert 'C09' not in baseline['completed_adapters'] and 'NOT_VERIFIABLE' in baseline['availability']['C09']
    preview = session.preview_volume('Main', 55); impact = preview['impact']
    assert impact['edited_operator_reference'] == {**inputs['cement'], 'slurries': {
        'Main': {**inputs['cement']['slurries']['Main'], 'client_volume_bbl': 55}}}
    assert 'total_preparation_water_and_gross_with_dead_volume' not in {r['dependency'] for r in impact['source_dependency_ledger']}
    assert any(r['dependency'] == 'total_preparation_water_and_gross_with_dead_volume'
               and r['classification'] == 'NOT_VERIFIABLE' for r in impact['unresolved_dependencies'])
    assert session.current() == before and baseline['receipt']['inputs_snapshot']['procedure']['preparation']['Main']['dead_volume_bbl'] == 77


def test_volume_preview_two_slurry_selection_preserves_unselected_source(volume_control):
    from c02_compare import engine
    from test_c02 import fixture
    op = deepcopy(volume_control['op']); recipe = op['slurries'].pop('Main')
    op['active_fluids'] = ['Lead', 'Tail']
    op['slurries'] = {'Lead': recipe, 'Tail': {**deepcopy(recipe), 'client_volume_bbl': 30, 'density_pcf': 118}}
    source = engine(op)
    with tempfile.TemporaryDirectory(dir=g.ROOT/'tmp') as folder:
        paths = []
        for role in op['active_fluids']:
            row = source['slurries'][role]
            paths.append(fixture(Path(folder)/(role+'.docx'), fluid=role, values={
                'yield': row['display']['yield_cuft_sk'], 'sacks': row['blend'][0]['sks or lbs'].removesuffix(' sks'),
                'water': row['display']['mix_water_bbl'], 'density': row['density']}, labrows=[]))
        document = Document(paths[0]); tail = Document(paths[1]); note = next(p for p in document.paragraphs if p.text.startswith('NOTE'))
        for table in tail.tables[:2]: note._p.addprevious(deepcopy(table._tbl))
        document.save(paths[0]); original = paths[0].read_bytes()
        session = g.PrivateSession(); path = session.store('two.docx', original); baseline = session.check(path, submitted(op))
        before = deepcopy(baseline); preview = session.preview_volume('Lead', 55)
        impact = preview['impact']
        assert impact['edited_operator_reference']['slurries']['Tail'] == op['slurries']['Tail']
        assert impact['unselected_slurry_source_hashes']['Tail'] == g.digest(baseline['results']['C03']['c02']['reference']['slurries']['Tail'])
        assert session.current_volume_preview('Tail', 55) is None and session.current() == before
        assert path.read_bytes() == original


def test_ui_volume_timeout_and_proposal_change_keep_baseline_and_message(ui_boundary, volume_control, monkeypatch):
    from io import BytesIO
    from subprocess import TimeoutExpired
    import subprocess
    _, uploads = ui_boundary; upload = BytesIO(volume_control['docx']); upload.name = 'literal.docx'; uploads[0] = upload
    app = ready_boundary_page(ui_boundary); app.button[0].click().run()
    session = app.session_state['_private']; baseline = deepcopy(session.current())
    message = app.text_area(key='engineer_message').value; original = session.document.read_bytes()
    app.selectbox(key='g06a:selected').select('Main').run()
    app.number_input(key='g06a:volume').set_value(55).run()
    assert session.current() == baseline and app.text_area(key='engineer_message').value == message
    real_run = subprocess.run
    def timeout(command, *args, **kwargs):
        if any(str(x).endswith('g06a_client_volume.py') for x in command):
            raise TimeoutExpired('/private/SECRET', 120, stderr='SECRET-G06A-PAYLOAD')
        return real_run(command, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(subprocess, 'run', timeout)
        next(b for b in app.button if b.label == 'Preview client-volume reference impact').click().run()
    assert not app.exception and session.volume_preview is None and session.current() == baseline
    assert any('source process timed out' in error.value for error in app.error)
    assert all('SECRET' not in error.value and '/private/' not in error.value for error in app.error)
    assert app.text_area(key='engineer_message').value == message
    app.number_input(key='g06a:volume').set_value(0).run()
    assert next(b for b in app.button if b.label == 'Preview client-volume reference impact').disabled
    assert session.current() == baseline and session.document.read_bytes() == original
