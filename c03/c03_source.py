"""C03 subprocess bridge; accepted sources stay read-only, writes stay in c03."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PIN = '60dffefb8c941ad90cb7caba0992126a35803717'
PINS = {
    'checker_parser.py':'d1265e61d7b62164942e47e04d24b6ce82ef7218ea0d724e92de1d08f30ebcb7',
    'c02/c02_engine.py':'b3327b430b37df45421d81f6bed7087c381eca02cf66dc12b0df6f4262ede6bd',
    'c02/c02_compare.py':'3c416fa4d3ec7f4ba9f606cb3b8698d52391e85cde28b7295d2ebbed5d671e0d',
}


def verify_accepted():
    for name,digest in PINS.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Accepted source identity mismatch: '+name)


def request(payload):
    environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(HERE/'tmp'),
        XDG_CACHE_HOME=str(HERE/'cache'),XDG_CONFIG_HOME=str(HERE/'cache/config'),MPLCONFIGDIR=str(HERE/'cache/mpl'))
    result=subprocess.run([sys.executable,'-B',str(HERE/'c03_source.py')],input=json.dumps(payload,allow_nan=False),
        capture_output=True,text=True,cwd=HERE,env=environment,timeout=90)
    if result.returncode:raise ValueError(result.stderr[-600:])
    data=json.loads(result.stdout)
    if 'error' in data:raise ValueError(data['error'])
    if data.get('source_sha')!=PIN:raise ValueError('Source SHA drift')
    return data


def run(payload):
    verify_accepted()
    sys.path.insert(0,str(ROOT/'c02'));sys.path.insert(0,str(ROOT))
    from c02_engine import reference
    import c02_compare as cc
    # In this already isolated child, preserve the original comparator while
    # bypassing only its c02-specific cache/subprocess environment wrapper.
    cc.engine=reference
    operator=payload['operator']
    if payload['action']=='inspect':
        path=Path(payload['docx']).resolve(strict=True)
        if not path.is_relative_to(HERE):raise ValueError('DOCX outside c03')
        baseline=cc.compare_document(path,operator)
        if baseline['status']!='PARTIAL_FINDINGS_ONLY':raise ValueError(str(baseline))
        import materials_db as db
        return {'source_sha':PIN,'c02':baseline,'parsed':cc.parse_docx(path),
            'allowed_tanks':db.get_available_tanks(operator['job_type']),
            'ct_job':operator['job_type']==db.CT_JOB}
    if payload['action']=='gross':
        reference_data=reference(operator)
        import pandas as pd
        import phase_5_cement as phase5
        import engineering_tools as eng
        output={}
        for fluid,samples in payload['allowances'].items():
            s=reference_data['slurries'][fluid];op=operator['slurries'][fluid]
            before=json.dumps(s['calc'],sort_keys=True)
            frame=pd.DataFrame(s['operator_additives'],columns=[*phase5.REQUIRED_ADDITIVE_COLUMNS,'Density'])
            projections={}
            for name,dead in samples.items():
                p={'auto_calc':True,'dead_vol':dead,'cmt_sg':op['cement_sg'],
                   'base_cement':op['base_cement'],'tank_name':'<ATTRIBUTED IN WORD>'}
                eng.validate_cement_parameters(p)
                blend,adds,_=phase5.build_cement_tables(p,frame,s['calc'])
                b,a=blend.to_dict('records'),adds.to_dict('records')
                def base(rows):return [{k:v for k,v in r.items() if k!='lbs or gal (with dead Vol.)'} for r in rows]
                if b!=s['blend'] or base(a)!=base(s['additives']) or json.dumps(s['calc'],sort_keys=True)!=before:
                    raise ValueError('Source base/Yield/Sacks/Lab invariance failed')
                projections[name]={'blend':b,'additives':a}
            output[fluid]=projections
        return {'source_sha':PIN,'projections':output,'base_invariants_preserved':True,
                'source_function':'phase_5_cement.build_cement_tables (original snapshot)'}
    if payload['action']!='render_fixture':raise ValueError('Unknown internal source action')
    # Test-only fixture path, not an editable Dead Volume product input.
    reference_data=reference(operator)
    import pandas as pd
    import phase_5_cement as phase5
    import phase_10_procedure as report
    from docxtpl import DocxTemplate
    slurries=[];expected={}
    for fluid,s in reference_data['slurries'].items():
        setup=payload['fixture'][fluid];dead=float(setup['dead']);tank=setup['tank']
        params={'auto_calc':True,'dead_vol':dead,'cmt_sg':operator['slurries'][fluid]['cement_sg'],
                'base_cement':s['base_cement'],'tank_name':tank}
        import engineering_tools as eng
        eng.validate_cement_parameters(params)
        frame=pd.DataFrame(s['operator_additives'],columns=[*phase5.REQUIRED_ADDITIVE_COLUMNS,'Density'])
        blend,adds,_=phase5.build_cement_tables(params,frame,s['calc'])
        expected[fluid]={'blend':blend.to_dict('records'),'additives':adds.to_dict('records'),
                         'pure_water_bbl':s['calc']['field_water_bbl'],'dead':dead,'tank':tank}
        slurries.append({'name':fluid,'volume_bbl':operator['slurries'][fluid]['client_volume_bbl'],
            'density_pcf':float(s['density']),'yield_cuft_sk':s['calc']['yield_ft3_per_sk'],
            'solution':s['calc']['field_solution_bbl'],'mix_water_bbl':s['calc']['field_water_bbl'],
            'total_water_bbl':s['calc']['field_water_bbl']+dead,'mixing_tank':tank,
            'blends':blend.to_dict('records'),'additives':adds.to_dict('records'),
            'lab_conventional':[],'lab_additives':[],
            'lab':{'rheology':{},'surface_hardened_hours':0}})
    notes=report.build_ordered_notes(operator['job_type'],{},1,slurries,False)
    context=dict(notes,slurries=notes['slurries'],well_data={},hardware=[],fluids_train=[],
        has_preflush=False,has_spacer=False,has_scavenger=False,
        executive_summary='SYNTHETIC structural test only; no measured lab or program certification.',
        procedure_steps=payload.get('procedure',[]))
    path=Path(payload['docx']).resolve()
    if not path.is_relative_to(HERE) or path.exists():raise ValueError('Unsafe/existing fixture destination')
    doc=DocxTemplate(ROOT/'snapshot/master_template.docx')
    doc.render(report._word_quantity_context(context));doc.save(path)
    return {'source_sha':PIN,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'fixture_expected':expected,'reference':reference_data,
            'note_builder':'phase_10_procedure.build_ordered_notes',
            'renderer':'docxtpl + phase_10_procedure._word_quantity_context'}


def install_audit():
    def audit(event,args):
        if event in ('socket.connect','socket.getaddrinfo'):raise RuntimeError('Network prohibited')
        if event=='open':
            path,mode,flags=args
            write=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(3|64|512|1024))
            if write and not isinstance(path,int) and not Path(path).resolve().is_relative_to(HERE):
                raise RuntimeError('Write outside c03 prohibited')
    sys.addaudithook(audit)


if __name__=='__main__':
    sys.dont_write_bytecode=True
    install_audit()
    try:result=run(json.loads(sys.stdin.read()))
    except (ValueError,TypeError,KeyError,RuntimeError,OSError) as error:result={'error':str(error),'source_sha':PIN}
    print(json.dumps(result,allow_nan=False))
