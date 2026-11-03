"""Run from a provisioned Git-free runtime: streamlit run c10_delivery.py."""
from hashlib import sha256
import json
from subprocess import TimeoutExpired
from zipfile import BadZipFile
import pandas as pd
import streamlit as st
import g07_report as report
import c10_delivery as delivery


def main():
    st.set_page_config(page_title='Cementing Program Checker', layout='wide')
    st.title('Cementing Program Checker')
    st.caption('PARTIAL_FINDINGS_ONLY — individual checks only; no overall program PASS.')
    try:
        report.identities()
        if st.get_option('browser.gatherUsageStats'):
            raise ValueError('Start with --browser.gatherUsageStats false')
        if '_private' not in st.session_state:
            st.session_state['_private'] = report.PrivateSession()
            st.session_state['_catalog'] = st.session_state['_private'].source_catalog
        session = st.session_state['_private']; catalog = st.session_state['_catalog']
        session.folder_check()
    except TimeoutExpired:
        st.session_state.pop('engineer_message', None)
        st.error('NOT_VERIFIABLE: source catalog timed out; no checks were run.'); st.stop()
    except (ValueError, RuntimeError, OSError) as error:
        st.error('Private runtime unavailable or identity/configuration rejected. '+str(error)); st.stop()
    with st.expander('Document and independent job inputs', expanded=True):
        upload = st.file_uploader('Original DOCX (maximum 32 MiB)', type=['docx'])
        job = st.selectbox('Job type', catalog['jobs'], index=None, key='job')
        mud = st.selectbox('Independent mud type', ['WBM', 'OBM'], index=None, key='mud')
        eligible = catalog['eligible'][job][mud] if job and mud else []
        active = st.multiselect('Active fluids', eligible, key=f'active:{job}:{mud}')
        active = [f for f in catalog['order'] if f in active]
        st.text('Source pumping order: '+', '.join(active))
        st.caption('Enter independent facts only. Nothing is populated from Word. Optional fluids are never mandatory.')
    fluid_inputs = {}; slurries = {}; completion = True; neat_confirmations={}
    for fluid in active:
        with st.expander(fluid+' — independent fluid / formulation inputs', expanded=True):
            prefix = f'{job}:{fluid}:'
            volume = st.number_input(fluid+' client volume (bbl)', value=None, key=prefix+'volume')
            density = st.number_input(fluid+' density (pcf)', value=None, key=prefix+'density')
            rate = st.text_input(fluid+' pump rate (bbl/min; original source range syntax allowed)', key=prefix+'rate')
            material = st.text_input(fluid+' material name (optional independent name)', key=prefix+'material')
            fluid_inputs[fluid] = {'volume': volume, 'density': density, 'pump_rate': rate}
            if material: fluid_inputs[fluid]['material_name'] = material
            if fluid in catalog['cement_roles']:
                base = st.selectbox(fluid+' base cement', catalog['cement_names'], index=None, key=prefix+'base')
                sg = st.number_input(fluid+' independently supplied cement SG', value=None, key=prefix+'sg')
                neat = st.checkbox(fluid+' has no additives (explicit neat formulation)', key=prefix+'neat')
                neat_confirmations[fluid]=neat
                adds = []
                if not neat:
                    adds = report.clean_rows(st.data_editor(pd.DataFrame(columns=['Material Type', 'Name', 'Physical State', 'Mix Method', 'User Input', 'Density']).astype({'User Input': 'float64', 'Density': 'float64'}),
                        num_rows='dynamic', key=prefix+'additives', hide_index=True).to_dict('records'))
                    st.caption('Enter source-valid material identity, Powder/Liquid, Dry Blend/In Mix Water, dosage and any required independent density. No recipe defaults.')
                ready = volume is not None and density is not None and base is not None and sg is not None and (neat or bool(adds))
                ready = ready and all(set(a) >= {'Material Type', 'Name', 'Physical State', 'Mix Method', 'User Input'} for a in adds)
                completion = completion and ready
                slurries[fluid] = {'client_volume_bbl': volume, 'density_pcf': density,
                    'base_cement': base, 'cement_sg': sg, 'additives': adds}
    cop = {'job_type': job, 'active_fluids': active, 'slurries': slurries} if job and active and slurries and completion else None
    fop = {'job_type': job, 'mud_type': mud, 'fluids': fluid_inputs} if job and active and all(
        f['volume'] is not None and f['density'] is not None and f['pump_rate'].strip() for f in fluid_inputs.values()) else None
    with st.expander('Independent hardware (C06)'):
        hardware_on = st.checkbox('Check independently entered hardware')
        hardware = []
        if hardware_on:
            hardware = report.clean_rows(st.data_editor(pd.DataFrame(columns=catalog['hardware_fields']).astype({
                k: 'float64' for k in ('ID (in)', 'Joint (m)', 'Weight (ppf)', 'Collapse (psi)', 'Burst (psi)')}),
                num_rows='dynamic', hide_index=True, key=f'hardware:{job}').to_dict('records'))
            st.text('Source descriptions: '+', '.join(catalog['hardware_descriptions']))
            st.caption('MD (m) uses the original scalar/range syntax. Placement/excess/geothermal contexts are NOT_VERIFIABLE here.')
    hop = {'job_type': job, 'hardware': hardware} if job and hardware and all('Description' in r and 'MD (m)' in r for r in hardware) else None
    with st.expander('Independent laboratory observations (partial C07)'):
        lab_on = st.checkbox('Check partial laboratory evidence')
        conditions = {}; measurements = {}; measured_fluid = None
        if lab_on:
            for key, label in (('bhct', 'BHCT (degF)'), ('bhst', 'BHST (degF)'), ('bhsp', 'BHSP (psi)')):
                value = st.number_input(label, value=None, key=f'lab:{job}:{key}')
                if value is not None: conditions[key] = value
            fluid = st.selectbox('Measured fluid', active, index=None, key=f'lab-fluid:{job}')
            measured_fluid = fluid
            if fluid:
                qc = {}
                for key, label in (('free_water', 'Free water (ml)'), ('free_water_45', 'Free water at 45 degrees (ml)'), ('surface_hardened_hours', 'Surface hardened hours')):
                    value = st.number_input(label, value=None, key=f'lab:{job}:{fluid}:{key}')
                    if value is not None: qc[key] = value
                if qc: measurements[fluid] = qc
            st.caption('No measurements are predicted. Full rheology/thickening/compressive/API admission and configured Spacer context are NOT_VERIFIABLE here.')
    lop = None
    if lab_on and job and active and (conditions or measurements or cop):
        lop = {'job_type': job, 'mud_type': mud, 'active_fluids': active, 'conditions': conditions, 'measurements': measurements}
        if cop: lop['cement_operator'] = cop
    with st.expander('Independently approved Executive Summary text (C08)'):
        text = st.text_area('Independent approved summary reference', key=f'summary:{job}')
        approval = st.text_input('Independent approval reference', key=f'approval:{job}')
        confirmed = st.checkbox('I confirm this reference was independently approved', key=f'approved:{job}')
    sop = {'job_type': job, 'manual_summary': {'text': text, 'approval_reference': approval, 'text_sha256': sha256(text.encode()).hexdigest()}} if job and text.strip() and approval.strip() and confirmed else None
    inputs = {'job_type':job,'mud_type':mud,'active_fluids':active,'cement': cop, 'fluids': fop, 'hardware': hop if hardware_on else None, 'lab': lop, 'summary': sop}
    with st.expander('Optional independent Procedure and ordered NOTES (C09)'):
        procedure = {'selected': st.checkbox('Check source-backed Procedure and ordered NOTES', key='c09:selected')}
        if procedure['selected']:
            options = catalog['procedure']; prefix = f'c09:{job}:'
            procedure.update(
                well_type=st.selectbox('C09 canonical well type', options['well_types'], index=None, key=prefix+'well_type'),
                td_m=st.number_input('C09 independent vertical well depth (m)', value=None, key=prefix+'td'),
                geo_md=st.number_input('C09 independent measured MD (m)', value=None, key=prefix+'md'),
                target_mode=st.selectbox('C09 placement target', [options['manual_target']], index=None,
                    format_func=lambda _: 'Independent manual target depth', key=prefix+'target_mode'),
                target_depth_m=st.number_input('C09 independent placement target depth (m MD)', value=None, key=prefix+'target'),
                excess_mode=st.selectbox('C09 source excess mode', options['excess_modes'], index=None, key=prefix+'excess_mode'),
                no_additional_context=st.checkbox('C09 summary context has no additional hardware qualifiers', key=prefix+'context'),
                excess={}, roles={})
            if procedure['excess_mode'] == 'apply':
                for field, label in options['excess_fields']:
                    procedure['excess'][field] = st.number_input('C09 '+label, value=None, key=prefix+field)
            for role in active:
                if role not in options['roles']: continue
                key = prefix+role+':'
                procedure['roles'][role] = {
                    'top_mode': st.selectbox('C09 '+role+' Top mode', options['top_modes'], index=None, key=key+'top_mode'),
                    'top_depth': st.number_input('C09 '+role+' Top depth (m MD; Surface permits blank or zero)', value=None, key=key+'top'),
                    'volume_basis': st.selectbox('C09 '+role+' volume basis', options['volume_bases'], index=None, key=key+'basis'),
                    'tank_name': st.selectbox('C09 '+role+' mixing tank', options['tanks'].get(job, []), index=None, key=key+'tank'),
                    'dead_volume_bbl': st.number_input('C09 '+role+' explicit dead volume (bbl)', value=None, key=key+'dead'),
                    'surface_hardened_hours': st.number_input('C09 '+role+' observed surface-hardened hours', value=None, key=key+'hours')}
            st.caption('Uses the independently entered cement, fluid rates and hardware above. Vertical ordinary casing only; no measurements or Word corrections are generated.')
        inputs['procedure'], procedure_status = report.procedure_input(inputs, procedure, catalog)
        if procedure['selected']: st.text('C09: '+procedure_status)
    # Include incomplete drafts, not just admitted operators, in stale-result invalidation.
    draft = {'job': job, 'mud': mud, 'active': active, 'fluid_inputs': fluid_inputs, 'slurries': slurries,
        'hardware_on': hardware_on, 'hardware': hardware, 'lab_on': lab_on, 'conditions': conditions,
        'measurements': measurements, 'measured_fluid': measured_fluid, 'neat_confirmations':neat_confirmations,
        'summary_text': text, 'approval': approval, 'confirmed': confirmed, 'procedure': procedure}
    raw = upload.getvalue() if upload else b''
    revision = report.submission_revision(raw,upload.name if upload else None,inputs,draft)
    if session.invalidate(revision): st.session_state.pop('engineer_message', None)
    admission=report.cement_admission(inputs,catalog)
    st.text('Cement submission: '+admission['status'])
    st.text('Backend submission SHA256: '+report.digest(inputs))
    if admission['status'] in ('INPUT_INCOMPLETE','INPUT_REJECTED'):st.warning(admission['reason'])
    with st.expander('Review committed independent inputs'):
        with st.container(key='g07-input-review'):
            st.code(json.dumps({'revision':revision,'inputs':inputs,'draft':draft},sort_keys=True,indent=2),language='json')
    if st.button('Run Check', disabled=not(upload and job and mud and active) or admission['status'] in ('INPUT_INCOMPLETE','INPUT_REJECTED'), type='primary'):
        session.result = None; st.session_state.pop('engineer_message', None)
        try:
            with st.spinner('Running supplied source-backed checks'):
                path = session.store(upload.name, raw); result = session.check(path, inputs,revision=revision,draft=draft)
            st.session_state['engineer_message'] = result['message']
        except BadZipFile:
            session.result = None; st.error('INPUT_REJECTED: invalid DOCX package; no check result is available.')
        except TimeoutExpired:
            session.result = None; st.error('NOT_VERIFIABLE: source process timed out; no check result is available.')
        except (ValueError, RuntimeError, OSError, KeyError, TypeError, ArithmeticError):
            session.result = None; st.error('INPUT_REJECTED / NOT_VERIFIABLE: document, independent inputs or source boundary rejected the check.')
    if session.result is not None:
        try:result=session.current()
        except (BadZipFile,ValueError,RuntimeError,OSError,KeyError):
            session.result = None
            st.session_state.pop('engineer_message',None);st.error('Run receipt rejected; recompute current independent inputs.');st.stop()
        st.subheader('English findings — PARTIAL_FINDINGS_ONLY')
        st.text('Run outcome: '+result['run_outcome'])
        st.text('Run receipt: '+result['receipt']['run_id'])
        st.text('Report identity: '+result['report_id'])
        st.caption('Original DOCX SHA256: '+result['document_sha256']+'. Original bytes unchanged. Raw non-ASCII claims are escaped in the table and retained in evidence.')
        for name, status in result['availability'].items(): st.text(name+': '+status)
        visible = [{k: v for k, v in row.items() if k not in ('Judgments', 'Message eligible')} for row in result['rows']]
        st.dataframe(pd.DataFrame(visible), hide_index=True, width='stretch')
        with st.expander('Original findings, overlapping judgments and provenance'):
            st.json(result)
        with st.container(key='g07-message-copy'):
            st.subheader('Editable engineer message')
            edited = st.text_area('Engineer message', key='engineer_message', height=180)
            st.caption('Copy Message: commit edits with Ctrl+Enter or leave the field, then use the native copy icon below. It copies the currently displayed edited text for the current run receipt.')
            st.code(edited, language=None, wrap_lines=True)
        with st.expander('Optional G06-A client-volume reference impact'):
            st.text('Proposed client volume — source-reference impact only; no Word edit')
            st.caption('The authoritative client request, baseline findings and engineer message remain unchanged. Source eligibility and physical Yield/Sacks identity are inspected only on preview. C09 Dead Volume is not carried into G06-A.')
            cop = result['receipt']['inputs_snapshot'].get('cement') or {}
            roles = [n for n in catalog['order'] if n in cop.get('slurries', {}) and n in catalog['procedure']['roles']]
            selected = st.selectbox('G06-A selected active ordinary slurry', roles, index=None, key='g06a:selected')
            proposed = st.number_input('G06-A proposed client volume (bbl)', value=None, key='g06a:volume')
            preview = None; ready = False
            try:
                preview = session.current_volume_preview(selected, proposed); ready = True
            except (ValueError, OSError, KeyError, TypeError):
                pass  # Incomplete/invalid controls invalidate preview only, never the baseline.
            if st.button('Preview client-volume reference impact', disabled=not ready):
                try:
                    with st.spinner('Inspecting the bound source reference'):
                        preview = session.preview_volume(selected, proposed)
                except TimeoutExpired:
                    preview = None; st.error('NOT_VERIFIABLE: G06-A source process timed out; no preview is available. Baseline unchanged.')
                except (BadZipFile, ValueError, RuntimeError, OSError, KeyError, TypeError, ArithmeticError):
                    preview = None; st.error('INPUT_REJECTED / NOT_VERIFIABLE: G06-A selection, physical claims or source reference could not be proved. No preview is available; baseline unchanged.')
            if preview is None:
                st.text('G06-A: NOT_RUN / NOT_VERIFIABLE — a current admitted C02/C03 run, one selected slurry and a finite positive proposal are required; no preview is credited.')
            else:
                impact = preview['impact']
                st.text('G06-A: CLIENT_VOLUME_REFERENCE_IMPACT — PARTIAL_FINDINGS_ONLY')
                st.text('G06-A preview receipt: '+preview['receipt']['preview_run_id'])
                st.text('Preview identity: '+preview['preview_id'])
                volume_row = next(r for r in impact['source_dependency_ledger'] if r['dependency'] == 'client_requested_volume')
                st.text('Authoritative baseline reference: '+str(volume_row['old_full_precision'])+' bbl; proposed reference only: '+str(volume_row['new_full_precision'])+' bbl.')
                for title, key in (('Source-reference dependencies', 'source_dependency_ledger'),
                        ('Original Word claims — unchanged', 'word_claim_impacts'),
                        ('Unresolved dependencies', 'unresolved_dependencies')):
                    st.text(title)
                    st.dataframe(pd.DataFrame([{k: report.ascii_text(v) if v is not None else 'null'
                        for k, v in row.items()} for row in impact[key]]), hide_index=True, width='stretch')
                st.caption('Unproved source display changes remain null. MATCH/DISCREPANCY compares unchanged Word with a proposed reference; nothing has been repaired. Calculated recipe is not measured Lab.')
                st.text(impact['reference_dead_volume_policy'])
                with st.expander('G06-A preview bindings and complete provenance'):
                    st.json(preview)
        with st.expander('Optional G06-B explicit Dead Volume impact'):
            st.caption('Read-only source what-if. Historical DV is inferred and nonunique, never measured. Client Requested Volume, baseline findings, engineer message and original Word remain unchanged. C09 DV is not reused.')
            cop = result['receipt']['inputs_snapshot'].get('cement') or {}
            roles = [n for n in catalog['order'] if n in cop.get('slurries', {}) and n in catalog['procedure']['roles']]
            selected_dv = st.selectbox('G06-B selected active ordinary slurry', roles, index=None, key='g06b:selected')
            proposed_dv = st.number_input('G06-B independent proposed Dead Volume (bbl)', min_value=0.0, value=None, key='g06b:dv')
            dv_preview = None; dv_ready = False
            try:
                dv_preview = session.current_dead_volume_preview(selected_dv, proposed_dv); dv_ready = True
            except (ValueError, OSError, KeyError, TypeError, ArithmeticError):
                pass  # DV controls invalidate only their own optional evidence.
            if st.button('Preview explicit Dead Volume impact', disabled=not dv_ready):
                try:
                    with st.spinner('Proving original NOTE/gross claims and source impact'):
                        dv_preview = session.preview_dead_volume(selected_dv, proposed_dv)
                except (BadZipFile, ValueError, RuntimeError, OSError, KeyError, TypeError, ArithmeticError):
                    dv_preview = None
                    st.error('NOT_VERIFIABLE: G06-B physical claims, current receipt or source availability could not be proved. No DV preview is credited; baseline unchanged.')
            if dv_preview is None:
                st.text('G06-B: NOT_RUN / NOT_VERIFIABLE — select one current admitted ordinary slurry and an independent finite DV of zero or greater, then explicitly preview.')
            else:
                impact = dv_preview['impact']; ledger = impact['impact_ledger']
                note = impact['selected_claims']['water']
                st.text('G06-B: EXPLICIT_DV_IMPACT — PARTIAL_FINDINGS_ONLY')
                st.text('G06-B preview receipt: '+dv_preview['receipt']['preview_run_id'])
                st.text('DV preview identity: '+dv_preview['preview_id'])
                st.text('Original Word NOTE — unchanged: '+report.ascii_text(note['raw_text']))
                st.json({'original_NOTE_locator': note['locator'],
                    'historical_DV_qualification': ledger['before_qualification'],
                    'inferred_nonunique_historical_DV_bbl': ledger['before_dv_interval'],
                    'explicit_proposed_DV_bbl': ledger['explicit_dead_volume_bbl'],
                    'unchanged_pure_Mix_Water_full_precision_bbl': ledger['pure_mix_water_full_precision_bbl'],
                    'source_after_total_preparation_water_full_precision_bbl': ledger['source_after_total_preparation_water_full_precision_bbl'],
                    'source_after_NOTE_display_bbl': ledger['source_after_NOTE_display_bbl'],
                    'historical_exact_delta': ledger['historical_exact_delta']})
                st.text('Gross additives — original Word claims/locators and proposed source displays')
                st.dataframe(pd.DataFrame([{k: report.ascii_text(v) if v is not None else 'null'
                    for k, v in row.items()} for row in ledger['gross_additives']]), hide_index=True, width='stretch')
                st.text('Unresolved dependencies')
                st.dataframe(pd.DataFrame(impact['unresolved_dependencies']), hide_index=True, width='stretch')
                st.caption('Gross full precision is unexposed/null. Display agreement is not an exact historical change. No NOTE, Procedure, Summary, measured Lab or Word correction is generated; no whole-program certification.')
                with st.expander('G06-B source invariants, original C03 and complete provenance'):
                    st.json(dv_preview)
        with st.expander('Optional C10 selective safe-copy DOCX'):
            st.caption('PARTIAL_FINDINGS_ONLY; selectable Yield/Sacks only; original Word unchanged; unselected and dependent items unverified/manual; no overall PASS.')
            inspection = None; copy_ready = False
            try:
                inspection = session.current_copy_proposals(); copy_ready = True
            except (BadZipFile, ValueError, RuntimeError, OSError, KeyError, TypeError):
                pass
            if st.button('Inspect C10 selective-copy proposals', disabled=not copy_ready):
                try:
                    with st.spinner('Inspecting source replacements and physical cells'):
                        inspection = session.inspect_copy_proposals()
                except (BadZipFile, ValueError, RuntimeError, OSError, KeyError, TypeError, ArithmeticError):
                    inspection = None
                    st.error('NOT_VERIFIABLE: C10 proposal/source inspection failed. No copy or download is available; original and baseline unchanged.')
            if inspection is None:
                st.text('C10: NOT_RUN — a current source-admitted run and explicit proposal inspection are required.')
            else:
                st.text('C10: PREVIEW_ONLY — no DOCX has been created by this inspection.')
                st.text('C10 inspection receipt: '+inspection['receipt']['inspection_run_id'])
                st.dataframe(pd.DataFrame([{k:report.ascii_text(v) for k,v in p.items()}
                    for p in inspection['proposal']['proposals']]), hide_index=True, width='stretch')
                for text in inspection['proposal']['limitations']: st.text(text)
                selected_ids = []
                for item in inspection['proposal']['proposals']:
                    if item['action'] != 'SELECTABLE': continue
                    label = 'C10 '+item['slurry']+' '+item['field']+': '+report.ascii_text(item['original_raw_text'])+' -> '+report.ascii_text(item['replacement'])
                    if st.checkbox(label, key='c10:'+inspection['proposal_id']+':'+item['finding_id']):
                        selected_ids.append(item['finding_id'])
                if not any(p['action'] == 'SELECTABLE' for p in inspection['proposal']['proposals']):
                    st.text('No SELECTABLE C10 claim. Manual/unverified items cannot generate a copy.')
                consent = st.checkbox('Confirm creation of a new DOCX for only the individually selected C10 cells',
                    key='c10:confirm:'+inspection['proposal_id']+':'+report.digest(selected_ids), disabled=not selected_ids)
                created = None
                try: created = session.current_created_copy(selected_ids, consent)
                except (BadZipFile, ValueError, RuntimeError, OSError, KeyError, TypeError): pass
                if st.button('Create selected-copy DOCX', disabled=not(selected_ids and consent)):
                    try:
                        with st.spinner('Applying and rechecking exact selected cells'):
                            created = session.create_selected_copy(selected_ids, consent)
                    except (BadZipFile, ValueError, RuntimeError, OSError, KeyError, TypeError, ArithmeticError):
                        created = None
                        st.error('NOT_VERIFIABLE: C10 creation/recheck or private cleanup failed. No download is credited; original and baseline unchanged.')
                if created is not None:
                    st.text('C10: COPY_CREATED — selected C02 cells rechecked; dependent program remains partial/manual.')
                    st.text('C10 copy receipt: '+created['receipt']['copy_run_id'])
                    st.caption('C10 delivery requires the current selection, consent and run. Changing them, independent inputs or the upload revokes subsequent transfers. Saved files cannot be recalled. PARTIAL_FINDINGS_ONLY; original Word unchanged.')
                    try:
                        st.html(delivery.issue(session, st.context.cookies.get(delivery.COOKIE), selected_ids, consent))
                    except (ValueError, RuntimeError, OSError, KeyError, TypeError):
                        st.error('NOT_VERIFIABLE: authorized delivery unavailable. Use the documented entrypoint; no download is available.')
                    with st.expander('C10 selected/unselected recheck and copy provenance'):
                        st.json({k:v for k,v in created.items() if k != 'bytes'})
                with st.expander('C10 complete proposal and source provenance'):
                    st.json(inspection)
    else:
        st.info('NOT_RUN — enter independent inputs and select Run Check. Previous results and messages are cleared when document or inputs change.')
    with st.expander('Coverage and blocked dependencies'):
        for name, status in report.BLOCKED.items(): st.text(name+': '+status)
        st.text('Cover/document control, survey, centralizer, pore/frac, IOD, images, schematic and charts are excluded. Only the explicit C10 selected-cell copy can offer a new DOCX; no automatic sending is available.')


if __name__ == '__main__': main()
