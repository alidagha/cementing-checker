"""G03 private production-DOCX admission; external assertions never prove execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from comparison_records import ROOT
from checker_parser import parse_docx
from c08_summary import section_records
from c02_engine import read_json, SOURCE_SHA

JOBS=('CSG 30"','CSG 24"','CSG 20"','CSG 18 5/8"','CSG 13 3/8"','CSG 9 5/8"','CSG 7"',
    'LNR 7"','LNR 5"','LNR 4 1/2"','CMT PLUG','CMT PLUG WITH CT','CMT SQUEEZE','TIE BACK LNR 7"','TIE BACK LNR 5"')
STATUSES=('UNAVAILABLE','INPUT_INCOMPLETE','GENERATION_BLOCKED','SOURCE_GENERATED_SYNTHETIC',
    'SOURCE_GENERATED_CANDIDATE','PARTIAL_VERIFIED','GOLDEN_PASS','NOT_RUN')
PIPELINE=('phase_10_procedure.py:build_master_context','docxtpl.template:DocxTemplate.render',
    'well_report.py:postprocess_well_report')
TEMPLATE_SHA256='a1128b0e9352e1dd7c8768eecc9335c50858356cee80ed33c0ec275e26c4d08b'
TEMPLATE_BLOB='1d77ebb7140e1bf0fa3d7cbd092f215290a187c0'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def case_record(job):
    if job not in JOBS:raise ValueError('Unknown canonical job')
    return {'case_id':f'J{JOBS.index(job)+1:02d}','job_type':job,'status':'NOT_RUN',
        'source_sha':SOURCE_SHA,'template_blob':TEMPLATE_BLOB,'template_sha256':TEMPLATE_SHA256,
        'independent_input_sha256':None,'source_document_sha256':None,
        'pipeline_calls':[],'parity_status':'NOT_RUN','hosted_golden_uat':'NOT_RUN_HOSTED',
        'native_word_browser':'NOT_RUN','file_privacy':'PRIVATE_RUNTIME_ONLY','golden_pass_allowed':False,
        'in_scope_C01R_C09_parity':'NOT_RUN','negative_controls_on_authentic_docx':'NOT_RUN',
        'acceptance_A_H':dict.fromkeys('ABCDEFGH','NOT_RUN')}


def inspect_external(docx, expected):
    """Integrity/structure alone cannot authenticate a report's generator history."""
    job=expected.get('job_type');record=case_record(job)
    path=Path(docx)
    if not path.exists():return dict(record,status='UNAVAILABLE',blocker='DOCX_UNAVAILABLE')
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
        return dict(record,status='INPUT_INCOMPLETE',blocker='UNPROVED_PRIVATE_PATH')
    before=digest(path)
    record['source_document_sha256']=before
    try:
        if set(expected)!={'job_type','source_sha','template_sha256','document_sha256','independent_input_sha256'}:
            raise ValueError('UNTRUSTED_OR_INCOMPLETE_PROVENANCE')
        if expected['source_sha']!=SOURCE_SHA or expected['template_sha256']!=TEMPLATE_SHA256 or expected['document_sha256']!=before:
            raise ValueError('SOURCE_TEMPLATE_OR_DOCUMENT_HASH_MISMATCH')
        if not isinstance(expected['independent_input_sha256'],str) or len(expected['independent_input_sha256'])!=64 or any(c not in '0123456789abcdef' for c in expected['independent_input_sha256']):
            raise ValueError('INDEPENDENT_INPUT_PROVENANCE_MISSING')
        parsed=parse_docx(path)
        if parsed['status']=='REJECTED':raise ValueError('UNSUPPORTED_OR_DAMAGED_DOCX')
        for section in ('summary','procedure'):section_records(path,parsed,section)
        # Not even a perfect-looking document + claimed source hashes/call names
        # prove that build_master_context and postprocessing actually executed.
        record.update(status='GENERATION_BLOCKED',blocker='FRESH_LEGITIMATE_PRODUCTION_EXECUTION_REQUIRED',
            independent_input_sha256=expected['independent_input_sha256'])
    except (ValueError,OSError,TypeError,KeyError) as error:
        record.update(status='INPUT_INCOMPLETE',blocker=str(error))
    if digest(path)!=before:raise RuntimeError('Original DOCX changed')
    return record


def generate(reference):
    """Only a fresh fixed worker may supply production execution evidence.

    No receipt/source_calls/status from an input JSON is accepted as authority.
    Reviewed measured inputs cannot be replaced by synthetic values or flags.
    """
    if not isinstance(reference,dict) or set(reference)!={'kind','project'} or reference['kind'] not in ('SYNTHETIC_TEST_INPUT','INDEPENDENT_PROGRAM_INPUT'):
        raise ValueError('Explicit independent input classification/project required')
    project=reference['project']
    if not isinstance(project,dict):raise ValueError('Canonical project must be an object')
    record=case_record(project.get('job_type'))
    if not (ROOT/'snapshot').is_dir() or any((p/'.git').exists() for p in (ROOT,*ROOT.parents)):
        raise ValueError('Separate Git-free private runtime required')
    before=json.dumps(reference,sort_keys=True,allow_nan=False)
    record['independent_input_sha256']=hashlib.sha256(before.encode()).hexdigest()
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp'),
        XDG_CACHE_HOME=str(ROOT/'cache'),XDG_CONFIG_HOME=str(ROOT/'cache/config'),MPLCONFIGDIR=str(ROOT/'cache/mpl'))
    proc=subprocess.run([sys.executable,'-B',str(ROOT/'golden_source.py')],input=before,text=True,
        capture_output=True,cwd=ROOT,env=env,timeout=90)
    if proc.returncode:raise ValueError('Production worker failed closed: '+proc.stderr[-300:])
    result=read_json(proc.stdout)
    if result.get('source_sha')!=SOURCE_SHA or result.get('independent_input_sha256')!=record['independent_input_sha256']:
        raise ValueError('Production execution identity mismatch')
    record.update(input_kind=reference['kind'],pipeline_calls=result.get('pipeline_calls',[]),
        source_files_verified=result.get('source_files_verified'),source_module_sha256=result.get('source_module_sha256',{}))
    if result.get('error'):
        return dict(record,status='GENERATION_BLOCKED',blocker='ORIGINAL_APP_EXPORT_GATE',
            private_gate_details=result['error'],last_stage=result.get('last_stage'))
    # A successful worker still earns generation only, never parity or Golden PASS.
    path=Path(result['docx']).resolve(strict=True)
    if record['source_files_verified']!=143 or not path.is_relative_to(ROOT/'tmp') or path.is_symlink() or set(PIPELINE)-set(record['pipeline_calls']):
        raise ValueError('Production path/call provenance incomplete')
    if digest(path)!=result['document_sha256'] or result['template_sha256']!=TEMPLATE_SHA256:
        raise ValueError('Production document/template identity mismatch')
    record.update(status='SOURCE_GENERATED_SYNTHETIC' if reference['kind']=='SYNTHETIC_TEST_INPUT' else 'SOURCE_GENERATED_CANDIDATE',
        source_document_sha256=result['document_sha256'],private_document_path=str(path))
    return record


def public_metadata(record):
    """Allowlist metadata; no private paths, identifiers, inputs, text or raw logs."""
    allowed={'case_id','job_type','status','source_sha','template_blob','template_sha256',
        'independent_input_sha256','source_document_sha256','pipeline_calls','parity_status',
        'hosted_golden_uat','native_word_browser','golden_pass_allowed','acceptance_A_H',
        'input_kind','file_privacy','in_scope_C01R_C09_parity','negative_controls_on_authentic_docx','source_files_verified','source_module_sha256','last_stage','blocker'}
    if record.get('status') not in STATUSES or record.get('status') in ('GOLDEN_PASS','PARTIAL_VERIFIED'):
        raise ValueError('No G03 promotion without independently proved scope/negative controls; GOLDEN_PASS is forbidden')
    if record.get('golden_pass_allowed') is not False:raise ValueError('Golden acceptance is reserved')
    result={k:v for k,v in record.items() if k in allowed}
    # Public blockers are controlled codes; raw source exception text stays private.
    if result.get('blocker') not in (None,'DOCX_UNAVAILABLE','ORIGINAL_APP_EXPORT_GATE',
            'FRESH_LEGITIMATE_PRODUCTION_EXECUTION_REQUIRED','UNTRUSTED_OR_INCOMPLETE_PROVENANCE',
            'SOURCE_TEMPLATE_OR_DOCUMENT_HASH_MISMATCH','INDEPENDENT_INPUT_PROVENANCE_MISSING','UNSUPPORTED_OR_DAMAGED_DOCX'):
        result['blocker']='UNPROVED_STRUCTURE_OR_INPUT'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('reference_json')
    args=parser.parse_args();p=Path(args.reference_json).resolve(strict=True)
    if not p.is_relative_to(ROOT):raise ValueError('Private reference outside runtime')
    before=digest(p);result=generate(read_json(p.read_text()));assert digest(p)==before
    print(json.dumps(result,sort_keys=True,allow_nan=False))


if __name__=='__main__':main()
