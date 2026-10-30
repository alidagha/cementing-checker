"""Fresh unchanged full-App export attempt; never accepts approval/cache signatures."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from comparison_records import ROOT
from engineering_source import SNAPSHOT, install_audit
from c02_engine import read_json, SOURCE_SHA
from tools.ci import source_proof
from tools.provision import verify_candidate

PROJECT_FIELDS={'job_type','doc_control','well_name','hardware_table','fluids_config','cement_params',
    'cement_additives_dfs','placement_config','executive_summary_config','well_geometry','geothermal_config',
    'geo_md','geo_tvd','bhct','bhst','bhsp','mud_density','well_data','preflush_config','standalone_spacer_config',
    'lab_qc_params','lab_grid_dfs','ct_stage_config'}


def validate_project(project):
    if not isinstance(project,dict) or set(project)-PROJECT_FIELDS:raise ValueError('Only independent canonical project inputs accepted')
    def walk(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if not isinstance(key,str) or 'signature' in key.casefold() or key in ('reviewed','calculations_prepared') or key.startswith('_'):
                    raise ValueError('Review/signature/cache input prohibited; use the genuine App review workflow')
                walk(item)
        elif isinstance(value,list):
            for item in value:walk(item)
    walk(project)


def run(reference):
    verify_candidate(ROOT);proof=source_proof(ROOT);validate_project(reference['project'])
    before=json.dumps(reference,sort_keys=True,allow_nan=False)
    from streamlit.testing.v1 import AppTest
    script='''
import sys,json,io,hashlib
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx
from golden_source import SNAPSHOT
sys.path.insert(0,str(SNAPSHOT))
assert get_script_run_ctx() is not None
project=json.loads(INPUT)['project']
import materials_db
if project['job_type'] not in materials_db.JOB_TYPES:raise ValueError('Unknown source job')
for key,value in project.items():
    if key in ('hardware_table',):value=pd.DataFrame(value)
    elif key in ('cement_additives_dfs','lab_grid_dfs'):value={name:pd.DataFrame(rows) for name,rows in value.items()}
    elif key=='well_geometry' and 'survey' in value:
        from well_profile import SURVEY_COLUMNS
        value=dict(value,survey=pd.DataFrame(value['survey'],columns=SURVEY_COLUMNS))
    st.session_state[key]=value
calls=set();stage='build_master_context'
def trace(frame,event,arg):
    filename=frame.f_code.co_filename
    if event=='call' and filename.startswith(str(SNAPSHOT)+'/'):
        calls.add(Path(filename).name+':'+frame.f_code.co_name)
    if event=='call' and filename.endswith('/docxtpl/template.py') and frame.f_code.co_name=='render':
        calls.add('docxtpl.template:DocxTemplate.render')
    return trace
sys.settrace(trace)
try:
    import phase_10_procedure as report
    import pumping_simulation
    from well_schematic_adapter import prepare_schematic
    from well_report import postprocess_well_report
    from docxtpl import DocxTemplate
    context=report.build_master_context()  # Default full prepare/review gates, never True bypass.
    stage='DocxTemplate.render'
    pumping=pumping_simulation.run_pumping_simulation(st.session_state)
    schematic=prepare_schematic(st.session_state)
    template=DocxTemplate(str(SNAPSHOT/'master_template.docx'))
    template.render(report._word_quantity_context(context))
    stream=io.BytesIO();template.save(stream)
    stage='postprocess_well_report'
    final=postprocess_well_report(stream.getvalue(),context['well_profile_report'],context['note_vertical'],
        context['cement_chart_report'],context['centralizer_report'],pumping_report=pumping,schematic_report=schematic)
    destination=Path(OUTPUT);destination.write_bytes(final)
    result={'docx':str(destination),'document_sha256':hashlib.sha256(final).hexdigest()}
except (ValueError,TypeError,KeyError,RuntimeError,OSError,ArithmeticError) as error:
    result={'error':str(error),'last_stage':stage}
finally:
    sys.settrace(None)
result['pipeline_calls']=sorted(calls)
st.session_state['g03_result']=result
'''
    folder=Path(tempfile.mkdtemp(dir=ROOT/'tmp',prefix='g03-production-'))
    script_path=folder/'invoke.py'
    script_path.write_text('INPUT='+repr(before)+'\nOUTPUT='+repr(str(folder/'original.docx'))+'\n'+script)
    try:
        app=AppTest.from_file(script_path,default_timeout=60).run()
        if app.exception:raise ValueError('Original export invocation failed: '+str(app.exception[0].message))
        result=dict(app.session_state['g03_result'])
    finally:script_path.unlink()
    result.update(source_sha=SOURCE_SHA,independent_input_sha256=hashlib.sha256(before.encode()).hexdigest(),
        source_files_verified=proof['verified_files'],template_sha256=hashlib.sha256((SNAPSHOT/'master_template.docx').read_bytes()).hexdigest(),
        source_module_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SNAPSHOT.glob('*.py') if p.stem in sys.modules})
    for path in SNAPSHOT.glob('*.py'):
        module=sys.modules.get(path.stem)
        if module is not None and Path(module.__file__).resolve()!=path.resolve():
            raise ValueError('Non-snapshot original source import')
    verify_candidate(ROOT);source_proof(ROOT)
    return result


if __name__=='__main__':
    sys.dont_write_bytecode=True;install_audit()
    reference=read_json(sys.stdin.read())
    try:output=run(reference)
    except (ValueError,TypeError,KeyError,RuntimeError,OSError,ArithmeticError) as error:
        output={'error':str(error),'source_sha':SOURCE_SHA,
            'independent_input_sha256':hashlib.sha256(json.dumps(reference,sort_keys=True,allow_nan=False).encode()).hexdigest()}
    print(json.dumps(output,allow_nan=False))
