"""Run from a provisioned Git-free runtime: streamlit run checker_ui.py."""
from hashlib import sha256
import json
from subprocess import TimeoutExpired
from zipfile import BadZipFile
import pandas as pd
import streamlit as st
import g07_report as report


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
                    adds = report.clean_rows(st.data_editor(pd.DataFrame(columns=['Material Type', 'Name', 'Physical State', 'Mix Method', 'User Input', 'Density']),
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
            hardware = report.clean_rows(st.data_editor(pd.DataFrame(columns=catalog['hardware_fields']),
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
    # Include incomplete drafts, not just admitted operators, in stale-result invalidation.
    draft = {'job': job, 'mud': mud, 'active': active, 'fluid_inputs': fluid_inputs, 'slurries': slurries,
        'hardware_on': hardware_on, 'hardware': hardware, 'lab_on': lab_on, 'conditions': conditions,
        'measurements': measurements, 'measured_fluid': measured_fluid, 'neat_confirmations':neat_confirmations,
        'summary_text': text, 'approval': approval, 'confirmed': confirmed}
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
    else:
        st.info('NOT_RUN — enter independent inputs and select Run Check. Previous results and messages are cleared when document or inputs change.')
    with st.expander('Coverage and blocked dependencies'):
        for name, status in report.BLOCKED.items(): st.text(name+': '+status)
        st.text('Cover/document control, survey, centralizer, pore/frac, IOD, images, schematic and charts are excluded. No corrected DOCX or automatic sending is available.')


if __name__ == '__main__': main()
