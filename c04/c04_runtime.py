"""C04-only process boundary for immutable C03/source execution."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
PIN='60dffefb8c941ad90cb7caba0992126a35803717'
PINS={'c03/c03_source.py':'aca286244e1909e9112f04c3e938c701bd47b5b4954897a0d365d0e918feeea0',
      'c03/c03_water.py':'c3b0c63eae178c94ed5a9b531bbba1cce4dd99fbdd7b3dd3ea3f83d1dce0e09d',
      'checker_parser.py':'d1265e61d7b62164942e47e04d24b6ce82ef7218ea0d724e92de1d08f30ebcb7',
      'c02/c02_engine.py':'b3327b430b37df45421d81f6bed7087c381eca02cf66dc12b0df6f4262ede6bd',
      'c02/c02_compare.py':'3c416fa4d3ec7f4ba9f606cb3b8698d52391e85cde28b7295d2ebbed5d671e0d'}


def verify_parents():
    for name,digest in PINS.items():
        p=ROOT/name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
            raise RuntimeError('Accepted parent identity mismatch: '+name)


def local_path(path):
    p=Path(path).resolve(strict=True)
    if not p.is_relative_to(HERE):raise ValueError('Input path escapes c04')
    return p


def call(payload):
    verify_parents()
    environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(HERE/'tmp'),
        XDG_CACHE_HOME=str(HERE/'cache'),XDG_CONFIG_HOME=str(HERE/'cache/config'),MPLCONFIGDIR=str(HERE/'cache/mpl'))
    p=subprocess.run([sys.executable,'-B',str(HERE/'c04_runtime.py')],input=json.dumps(payload,allow_nan=False),
                     capture_output=True,text=True,cwd=HERE,env=environment,timeout=90)
    if p.returncode:raise RuntimeError(p.stderr[-800:])
    result=json.loads(p.stdout)
    if 'runtime_error' in result:raise ValueError(result['runtime_error'])
    return result


def child(payload):
    verify_parents()
    sys.path.insert(0,str(ROOT/'c03'))
    import c03_source as cs
    import c03_water as cw
    # Only immutable modules' runtime-path globals change in this fresh child.
    # ROOT stays the accepted parent; no source/algorithm/record is replaced.
    cs.HERE=HERE;cw.HERE=HERE;cw.request=cs.run
    cs.install_audit()
    if payload['action']=='fixture':return cs.run(dict(payload,action='render_fixture'))
    if payload['action']=='baseline':return cw.analyze(local_path(payload['docx']),payload['operator'])
    if payload['action']=='preview':
        path=local_path(payload['docx'])
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        baseline=cw.analyze(path,payload['operator'])
        from c04_preview import compose
        return compose(baseline,payload['operator'],payload['edit'],digest)
    raise ValueError('Unknown runtime action')


if __name__=='__main__':
    try:result=child(json.loads(sys.stdin.read()))
    except (ValueError,TypeError,KeyError,OSError,RuntimeError,ArithmeticError) as error:
        result={'runtime_error':str(error)}
    print(json.dumps(result,allow_nan=False))
