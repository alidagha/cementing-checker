"""C09 canonical independent state -> genuine source report text and ordered NOTES."""
from copy import deepcopy
import hashlib
import sys

from narrative_source import summary_reference


def procedure_reference(operator):
    import pandas as pd
    import streamlit as st
    import materials_db as db
    import engineering_tools as eng
    import project_state
    import phase_5_cement as phase5
    import phase_10_procedure as report
    import well_profile
    from checker_parser import heading
    if not isinstance(operator,dict) or not {'program','preparation','well_geometry'}<=set(operator) or set(operator)-{'program','preparation','well_geometry','manual_procedure'}:
        raise ValueError('Independent program, per-slurry preparation and well_geometry required')
    program=operator['program'];summary=summary_reference(program)
    active=summary['fluid_order'];slurries=list(program['cement_operator']['slurries'])
    # A complete formulation/NOTE projection is not yet available for these fluids.
    if any(n in active for n in ('Spacer','Scavenger','Pre Flush','Diesel')):
        raise ValueError('This conditional fluid requires its own complete source NOTE context; unsupported in C09')
    if set(operator['preparation'])!=set(slurries):raise ValueError('Exactly active slurry preparation inputs required')
    geometry=deepcopy(operator['well_geometry'])
    if not isinstance(geometry,dict) or geometry.get('type') not in ('Vertical','Directional'):
        raise ValueError('Explicit canonical well type required for NOTE applicability')
    if 'survey' in geometry:
        geometry['survey']=pd.DataFrame(geometry['survey'],columns=well_profile.SURVEY_COLUMNS)
    well_profile.validate_well_inputs(geometry,{})
    # This is the real session owned by the isolated ScriptRunner. Only independent
    # canonical inputs are installed; original refresh functions own derived caches.
    state=st.session_state
    if any(k!='$$STREAMLIT_INTERNAL_KEY_TESTING' for k in state):
        raise ValueError('Narrative session was not fresh')
    state['job_type']=program['job_type']
    state['fluids_config']={'active':active,'params':deepcopy(program['fluids'])}
    state['hardware_table']=pd.DataFrame(program['hardware'])
    state['geo_md']=program['geo_md'];state['placement_config']=deepcopy(program['placement_config'])
    state['executive_summary_config']=deepcopy(program['executive_summary_config'])
    state['well_geometry']=geometry
    params={};frames={}
    for name in slurries:
        setup=operator['preparation'][name];recipe=program['cement_operator']['slurries'][name]
        if not isinstance(setup,dict) or set(setup)!={'tank_name','dead_volume_bbl','surface_hardened_hours'}:
            raise ValueError('Independent tank, allowance and observed surface hours required')
        if setup['tank_name'] not in db.get_available_tanks(program['job_type']):raise ValueError('Tank not available for source job')
        for key in ('dead_volume_bbl','surface_hardened_hours'):
            if isinstance(setup[key],bool) or not isinstance(setup[key],(int,float)):
                raise ValueError('Independent finite numeric preparation/observation required')
            eng.require_nonnegative_number(setup[key],key)
        params[name]={**program['tops'][name], 'auto_calc':True,'dead_vol':setup['dead_volume_bbl'],
            'tank_name':setup['tank_name'],'base_cement':recipe['base_cement'],
            'cmt_sg':recipe['cement_sg'],'cmt_sg_source':'manual'}
        frames[name]=pd.DataFrame(recipe['additives'],columns=[*phase5.REQUIRED_ADDITIVE_COLUMNS,'Density'])
    state['cement_params']=params;state['cement_additives_dfs']=frames
    project_state.refresh_fluids(state)
    if list(state['fluid_data'])!=active:raise ValueError('Source active train changed')
    issues=phase5.refresh_cement_calculations(state)
    if issues:raise ValueError(' | '.join(issues))
    specs=report.synchronize_report_texts()
    if any(v['pending'] for v in specs.values()):raise ValueError('Source reports pending manual review')
    official=specs['procedure_text']['generated']
    if report.UNRESOLVED_INPUT_TOKEN.search(official):raise ValueError('Source requires additional operational inputs')
    text=official;kind='LOCKED_SOURCE_FROM_INDEPENDENT_INPUTS';manual=None
    if 'manual_procedure' in operator:
        manual=operator['manual_procedure']
        if not isinstance(manual,dict) or set(manual)!={'text','approval_reference','text_sha256'}:
            raise ValueError('Explicit independent approved procedure and provenance required')
        if not isinstance(manual['text'],str) or not manual['text'].strip() or not isinstance(manual['approval_reference'],str) or not manual['approval_reference'].strip():
            raise ValueError('Missing independently approved procedure')
        if hashlib.sha256(manual['text'].encode()).hexdigest()!=manual['text_sha256']:raise ValueError('Approved procedure SHA drift')
        text=manual['text'];kind='INDEPENDENT_APPROVED_MANUAL_TEXT'
    # Physical line projection of the source text through the existing template
    # paragraph loop. No step renumbering, sentence generation or wording rewrite.
    lines=[line for line in text.split('\n') if line.strip()]
    if lines and heading(lines[0])=='procedure':lines=lines[1:]
    if not lines or any(heading(line) is not None for line in lines):raise ValueError('Ambiguous procedure boundary in independent text')
    payload=[]
    for name in report.REPORT_SLURRY_ORDER:
        if name not in slurries:continue
        p=state['cement_params'][name]
        payload.append({'name':name,'mixing_tank':p['tank_name'],
            'mix_water_bbl':p['mix_water'],'total_water_bbl':p['mix_water']+p['dead_vol'],
            'yield_cuft_sk':p['yield'],'total_sacks':p['total_sacks'],
            'blends':state['cement_blend_'+name].to_dict('records'),
            'additives':state['cement_calc_'+name].to_dict('records'),
            'lab':{'surface_hardened_hours':operator['preparation'][name]['surface_hardened_hours'],
                'rheology':{}}})
    notes=report.build_ordered_notes(program['job_type'],{},state['total_pump_time_min'],payload,
        report.centralizer_applicable(program['job_type']),is_vertical=geometry['type']=='Vertical')
    context={**notes,'executive_summary':summary['text'],'procedure_steps':lines,
        'slurries':payload,'fluids_train':list(state['fluid_data'].values()),
        'well_data':{},'hardware':[],'has_preflush':False,'has_spacer':False,'has_scavenger':False,
        'has_open_hole_notes':report.centralizer_applicable(program['job_type'])}
    return {'text':text,'official_generated_text':official,'procedure_steps':lines,
        'kind':kind,'function':'phase_10_procedure.py:generate_official_procedure; build_ordered_notes; synchronize_report_texts',
        'procedure_source_signature':specs['procedure_text']['signature'],
        'manual_reference':manual,'all_source_notes':notes['all_notes'],'context':context,
        'preparation':{n:{'pure_water_bbl':state['cement_params'][n]['mix_water'],
            'tank_name':state['cement_params'][n]['tank_name'],
            'dead_volume_bbl':state['cement_params'][n]['dead_vol']} for n in slurries},
        'cement_calls':summary['cement_calls']}
