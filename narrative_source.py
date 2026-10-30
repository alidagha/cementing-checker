"""Locked narrative invocation in Streamlit's isolated ScriptRunner, never live App state."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from engineering_source import ROOT, SNAPSHOT, install_audit
sys.path.insert(0, str(ROOT / 'c02'))
from c02_engine import SOURCE_SHA, read_json, verify_source


def request(operator, action='summary', destination=None):
    if not SNAPSHOT.is_dir() or any((p/'.git').exists() for p in (ROOT, *ROOT.parents)):
        raise ValueError('Separate Git-free provisioned runtime required')
    environment=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT/'tmp'),
        XDG_CACHE_HOME=str(ROOT/'cache'), XDG_CONFIG_HOME=str(ROOT/'cache/config'),
        MPLCONFIGDIR=str(ROOT/'cache/mpl'))
    process=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve())],
        input=json.dumps({'operator':operator,'action':action,'destination':destination},allow_nan=False),
        capture_output=True,text=True,cwd=ROOT,env=environment,timeout=90)
    if process.returncode:
        raise ValueError('Narrative subprocess failed: '+process.stderr[-400:])
    result=read_json(process.stdout)
    if 'error' in result:raise ValueError(result['error'])
    if result['source_sha']!=SOURCE_SHA:raise ValueError('Narrative source drift')
    return result


def manual_reference(operator):
    if not isinstance(operator,dict) or set(operator)!={'job_type','manual_summary'}:
        raise ValueError('Manual mode accepts only canonical job and independent approved summary reference')
    item=operator['manual_summary']
    if not isinstance(item,dict) or set(item)!={'text','approval_reference','text_sha256'}:
        raise ValueError('Explicit independently approved text, provenance and digest required')
    if not isinstance(item['text'],str) or not item['text'].strip() or not isinstance(item['approval_reference'],str) or not item['approval_reference'].strip():
        raise ValueError('Missing independent manual approval reference')
    if hashlib.sha256(item['text'].encode()).hexdigest()!=item['text_sha256']:
        raise ValueError('Independent approved summary SHA drift')
    # Canonical job validation stays at the verified source boundary.
    from c02_engine import verify_source, SNAPSHOT
    verify_source()
    import sys
    sys.path.insert(0,str(SNAPSHOT))
    import materials_db
    if operator['job_type'] not in materials_db.JOB_TYPES:raise ValueError('Unknown canonical job')
    return {'text':item['text'],'kind':'INDEPENDENT_APPROVED_MANUAL_TEXT',
        'function':'Independent approved text; manual authority project_state.py:sync_report_text (not invoked)',
        'approval_reference':item['approval_reference'],'text_sha256':item['text_sha256'],'cement_calls':[]}



def summary_reference(operator):
    """Independent canonical facts; no approval/cache/signature fields accepted."""
    import pandas as pd
    import materials_db as db
    import engineering_tools as eng
    import placement
    import phase_10_procedure as report
    from engineering_source import fluid_reference, well_reference
    from c02_engine import reference as cement_reference
    if isinstance(operator,dict) and 'manual_summary' in operator:return manual_reference(operator)
    required={'job_type','fluids','hardware','placement_config','cement_operator','tops',
        'executive_summary_config','geo_md'}
    if not isinstance(operator,dict) or set(operator)!=required:
        raise ValueError('Explicit independent narrative fields required; no state/approval flags')
    job=operator['job_type']
    if job not in db.JOB_TYPES:raise ValueError('Unknown canonical job')
    if job==db.CT_JOB:raise ValueError('CT source admission requires a complete independent CT project; unsupported here')
    depth=operator['geo_md']
    if isinstance(depth,bool) or not isinstance(depth,(int,float)):
        raise ValueError('Independent measured depth required')
    eng.require_nonnegative_number(depth,'MD')
    # Existing adapters execute genuine validation/calculation authorities.
    f=fluid_reference({'job_type':job,'fluids':operator['fluids']})
    well_reference({k:operator[k] for k in ('job_type','hardware','placement_config')})
    cement=operator['cement_operator']
    if cement.get('job_type')!=job or cement.get('active_fluids')!=f['order']:
        raise ValueError('Independent cement/fluid identities disagree')
    trace=sys.gettrace()
    try:c=cement_reference(cement)
    finally:sys.settrace(trace)
    active=list(c['slurries'])
    if not active or set(active)-set(db.PLACEMENT_SLURRIES) or set(operator['tops'])!=set(active):
        raise ValueError('Exactly active placement-slurry tops required; Scavenger unsupported')
    for name in active:
        item=cement['slurries'][name];fluid=operator['fluids'][name]
        if item['client_volume_bbl']!=fluid['volume'] or item['density_pcf']!=fluid['density']:
            raise ValueError('Crossed independent cement volume/density')
        top=operator['tops'][name]
        if not isinstance(top,dict) or set(top)!={'top_job_type','top_mode','top_depth'} or top['top_job_type']!=job:
            raise ValueError('Explicit job-scoped top mode/depth required')
        if top['top_mode'] not in ('Surface','Depth (m MD)'):
            raise ValueError('Unproved top mode')
        if top['top_mode']=='Surface' and top['top_depth']!=0:
            raise ValueError('Contradictory independent surface top')
        if isinstance(top['top_depth'],bool) or not isinstance(top['top_depth'],(int,float)):
            raise ValueError('Explicit numeric top depth required')
        eng.require_nonnegative_number(top['top_depth'],'Top depth')
    hw=pd.DataFrame(operator['hardware']);pc=operator['placement_config']
    target=placement.target_depth(hw,job,pc)
    intervals=placement.slurry_intervals(hw,job,pc,active,operator['tops'],f['fluids'])
    if target is None or set(intervals)!=set(active) or any(v.get('issue') or v['top_depth'] is None or v['bottom_depth'] is None for v in intervals.values()):
        raise ValueError('Independent target/placement incomplete')
    config=operator['executive_summary_config'];placement.validate_executive_summary_config(config)
    if config['job_type']!=job or set(config.get('per_slurry',{}))!=set(active) or 'placement_context_rows' not in config:
        raise ValueError('Explicit current summary metadata and per-slurry basis required')
    for name,record in config['per_slurry'].items():
        if 'volume_basis' not in record:raise ValueError('Independent volume basis required')
        for key in ('wet_inside_host_row','liner_lap_host_row'):
            if key in record and not placement.hardware_context_label(hw,record[key]):
                raise ValueError('Unproved qualifier hardware token')
        for number,host in (('wet_stands','wet_inside_host_row'),('liner_lap_m','liner_lap_host_row')):
            if record.get(host) and record.get(number) is None:raise ValueError('Qualifier host without independent quantity')
    if any(not placement.hardware_context_label(hw,k) for k in config['placement_context_rows']):
        raise ValueError('Unproved summary context row')
    if 'TIE BACK' in job and 'tie_back_origin' not in config:raise ValueError('Independent tie-back origin required')
    if 'SQUEEZE' in job and 'squeeze_scope' not in config:raise ValueError('Independent squeeze scope required')
    if config.get('squeeze_context_row') and not placement.hardware_row_metadata(hw,config['squeeze_context_row']):
        raise ValueError('Unproved squeeze hardware token')
    additives={n:pd.DataFrame(c['slurries'][n]['operator_additives']) for n in active}
    text=report.generate_executive_summary(job,f['fluids'],f['order'],additives,hw,depth,
        operator['tops'],pc,config)
    if '[' in text or '....' in text or 'None' in text:
        raise ValueError('Source retains incomplete/unsupported narrative context')
    return {'text':text,'kind':'LOCKED_SOURCE_FROM_INDEPENDENT_INPUTS',
        'function':'phase_10_procedure.py:generate_executive_summary','placement':intervals,
        'target_depth_m':target,'fluid_order':f['order'],'cement_calls':c['source_calls']}


def invoke(payload):
    """AppTest owns the real ScriptRunner context; no source gate/state is patched."""
    from tools.provision import verify_candidate
    verify_candidate(ROOT);verify_source()
    before=json.dumps(payload['operator'],sort_keys=True,allow_nan=False)
    from streamlit.testing.v1 import AppTest
    # Streamlit creates a fresh session. The script imports no App UI entrypoint.
    # Input is ordinary independent data, never serialized SessionState/approval caches.
    script='''
import json,sys,threading
from pathlib import Path
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx
from narrative_source import summary_reference, SNAPSHOT
sys.path.insert(0,str(SNAPSHOT))
assert get_script_run_ctx() is not None
assert type(st.session_state).__module__=='streamlit.runtime.state.session_state_proxy'
calls=set()
def trace(frame,event,arg):
    if event=='call' and str(frame.f_code.co_filename).startswith(str(SNAPSHOT)+'/'):
        calls.add(Path(frame.f_code.co_filename).name+':'+frame.f_code.co_name)
    return trace
sys.settrace(trace)
try:
    result=summary_reference(json.loads(INPUT))
    result['source_calls']=sorted(calls | set(result.pop('cement_calls')))
    result['session_state_implementation']=type(st.session_state).__module__
    result['approval_flags_supplied']=False
    st.session_state['narrative_result']=result
finally:
    sys.settrace(None)
'''
    # Literal JSON only; no input is interpolated as executable Python.
    script='INPUT='+repr(before)+'\n'+script
    app=AppTest.from_string(script,default_timeout=60).run()
    if app.exception:raise ValueError('Source narrative invocation rejected: '+str(app.exception[0].message))
    result=app.session_state['narrative_result']
    origins={}
    for path in SNAPSHOT.glob('*.py'):
        module=sys.modules.get(path.stem)
        if module is not None:
            if Path(module.__file__).resolve()!=path.resolve():raise ValueError('Non-snapshot source import')
            origins[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    verify_candidate(ROOT);verify_source()
    if json.dumps(payload['operator'],sort_keys=True,allow_nan=False)!=before:raise ValueError('Operator input mutated')
    output={'source_sha':SOURCE_SHA,'reference':result,'source_module_sha256':origins,
        'operator_input_sha256':hashlib.sha256(before.encode()).hexdigest()}
    if payload['action']=='render_summary':
        destination=Path(payload['destination']).absolute()
        if destination.suffix!='.docx' or not destination.is_relative_to(ROOT/'tmp') or destination.resolve()!=destination or destination.exists():
            raise ValueError('New synthetic fixture must stay in runtime/tmp')
        from docxtpl import DocxTemplate
        import phase_10_procedure as report
        template=DocxTemplate(str(SNAPSHOT/'master_template.docx'))
        context={'executive_summary':result['text'],'procedure_steps':[], 'slurries':[],
            'hardware':[],'well_data':{},'fluids_train':[], 'has_preflush':False,
            'has_spacer':False,'has_scavenger':False}
        template.render(report._escape_xml_special_chars(report._word_quantity_context(context)))
        template.save(str(destination))
    elif payload['action']!='summary':raise ValueError('Unknown narrative action')
    return output


if __name__=='__main__':
    sys.dont_write_bytecode=True
    install_audit()
    try:result=invoke(read_json(sys.stdin.read()))
    except (ValueError,TypeError,KeyError,RuntimeError,OSError,OverflowError) as error:
        result={'error':str(error),'source_sha':SOURCE_SHA}
    print(json.dumps(result,allow_nan=False))
