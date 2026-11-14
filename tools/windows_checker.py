"""One-time Windows setup and offline launch; never changes the Cementing App."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import venv
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
PORT=8502


def source_files(root):
    ignored={'.git','__pycache__','.pytest_cache'}
    result={}
    for path in sorted(root.rglob('*')):
        if any(part in ignored for part in path.relative_to(root).parts):continue
        if path.is_symlink() or path.resolve()!=path.absolute():raise ValueError('SOURCE_PATH_ALIAS_REJECTED')
        if path.is_file():result[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def location():
    files=source_files(ROOT)
    identity=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()[:20]
    base=Path(os.environ['LOCALAPPDATA'])/'CementingCheckerW2'
    return base,base/identity,files


def product_env(runtime):
    return dict(os.environ,PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',
        TMPDIR=str(runtime/'tmp'),TEMP=str(runtime/'tmp'),TMP=str(runtime/'tmp'),
        XDG_CACHE_HOME=str(runtime/'cache'),XDG_CONFIG_HOME=str(runtime/'cache/config'),
        MPLCONFIGDIR=str(runtime/'cache/mpl'),STREAMLIT_BROWSER_GATHER_USAGE_STATS='false')


def run_checked(args,code,**kwargs):
    # Package diagnostics stay in the private install directory, never in the UI.
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,**kwargs)
    if result.returncode:raise ValueError(code)
    return result


def setup(wheelhouse=None):
    from private_files import create_private_directory,private_permissions
    from tools.provision import verify_candidate,bundled_source
    verify_candidate(ROOT);lock=json.loads((ROOT/'upstream.lock.json').read_text());bundled_source(ROOT,lock)
    base,install,files=location()
    if os.name=='nt':
        from private_files import _windows
        _windows().local_volume(install)
    if (not install.is_absolute() or install.is_relative_to(ROOT) or ROOT.is_relative_to(install)
            or any((parent/'.git').exists() for parent in (install,*install.parents))):
        raise ValueError('PRIVATE_INSTALL_OUTSIDE_CHECKOUTS_REQUIRED')
    if not base.exists():create_private_directory(base)
    if not private_permissions(base):raise ValueError('UNSUPPORTED_WINDOWS_SECURITY')
    if install.exists():raise ValueError('INSTALLATION_EXISTS_USE_RUN_OR_REVIEW_FAILED_SETUP')
    create_private_directory(install)
    environment=install/'python';runtime=install/'runtime'
    venv.EnvBuilder(with_pip=True).create(environment)
    python=environment/'Scripts/python.exe'
    args=[str(python),'-m','pip','install','--disable-pip-version-check','--only-binary=:all:','-r',str(ROOT/'requirements.txt')]
    if wheelhouse:args[4:4]=['--no-index','--find-links',str(Path(wheelhouse).resolve(strict=True))]
    run_checked(args,'MISSING_DEPENDENCY_WHEEL_OR_PACKAGE',cwd=install,timeout=900)
    run_checked([str(python),'-B',str(ROOT/'tools/provision.py'),'--destination',str(runtime)],'PROVISION_IDENTITY_OR_ISOLATION_FAILURE',cwd=install,timeout=150)
    run_checked([str(python),'-B','tools/provision.py','--seed'],'SOURCE_SEED_FAILED',cwd=runtime,env=product_env(runtime),timeout=270)
    if not private_permissions(runtime):raise ValueError('UNSUPPORTED_WINDOWS_SECURITY')
    candidate={k:v for k,v in files.items() if not k.startswith('checker_engine'+os.sep)}
    state={'schema':'w2.1','source_files':files,'runtime_files':candidate,'runtime':str(runtime),'python':str(python)}
    from private_files import exclusive_create
    fd=exclusive_create(install/'installation.json')
    with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as out:json.dump(state,out,sort_keys=True)
    preflight(install,files)
    print('SETUP_COMPLETE — WINDOWS_NATIVE_NOT_VERIFIED; Owner-machine full UAT is required before READY_OFFLINE acceptance.')


def preflight(install,files):
    from private_files import private_permissions
    if not private_permissions(install) or not private_permissions(install/'installation.json'):
        raise ValueError('UNSUPPORTED_WINDOWS_SECURITY')
    state=json.loads((install/'installation.json').read_text(encoding='utf-8'))
    if state['schema']!='w2.1' or state['source_files']!=files:raise ValueError('INSTALLATION_SOURCE_DRIFT')
    runtime=install/'runtime';python=install/'python/Scripts/python.exe'
    if Path(state['runtime'])!=runtime or Path(state['python'])!=python or not private_permissions(runtime):
        raise ValueError('INSTALLATION_PATH_OR_SECURITY_DRIFT')
    for name,expected in state['runtime_files'].items():
        path=runtime/name
        if path.is_symlink() or path.resolve()!=path or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('RUNTIME_CODE_DRIFT')
    script='from tools.provision import verify_candidate;from tools.ci import source_proof,environment_proof;verify_candidate(__import__("pathlib").Path.cwd());source_proof();environment_proof()'
    run_checked([str(python),'-B','-c',script],'RUNTIME_SOURCE_OR_DEPENDENCY_DRIFT',cwd=runtime,env=product_env(runtime),timeout=60)
    return python,runtime


def launch():
    base,install,files=location();python,runtime=preflight(install,files)
    with socket.socket() as sock:
        try:sock.bind(('127.0.0.1',PORT))
        except OSError:raise ValueError('PORT_8502_IN_USE; close the existing Checker, not Cementing App')
    args=[str(python),'-B','-m','streamlit','run','c10_delivery.py','--server.address','127.0.0.1',
        '--server.port',str(PORT),'--server.headless','true','--server.maxUploadSize','32','--browser.gatherUsageStats','false']
    import signal
    process=subprocess.Popen(args,cwd=runtime,env=product_env(runtime),creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        import urllib.request
        deadline=time.monotonic()+45
        while process.poll() is None:
            try:
                # Deliberately local, with no inherited external HTTP proxy.
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open('http://127.0.0.1:8502/_stcore/health',timeout=1) as response:
                    if response.read()!=b'ok':raise ValueError('LOCAL_SERVER_HEALTH_REJECTED')
                webbrowser.open('http://127.0.0.1:8502');print('Checker running locally. Ctrl+C stops this Checker instance.');break
            except OSError:
                if time.monotonic()>=deadline:raise ValueError('LOCAL_SERVER_START_FAILED')
                time.sleep(.2)
        if process.poll() is not None:raise ValueError('LOCAL_SERVER_EXITED')
        process.wait()
    finally:
        if process.poll() is None:
            process.send_signal(signal.CTRL_BREAK_EVENT)
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


def main():
    if os.name!='nt' or sys.version_info[:2]!=(3,12):raise ValueError('NATIVE_WINDOWS_PYTHON_312_REQUIRED')
    if len(sys.argv)<2 or sys.argv[1] not in ('setup','run'):raise ValueError('USE_SETUP_OR_RUN_LAUNCHER')
    if sys.argv[1]=='setup':setup(sys.argv[2] if len(sys.argv)>2 else None)
    else:launch()


if __name__=='__main__':
    # Parent is only a Python bootstrap/import location; no App/engine import occurs here.
    sys.path.insert(0,str(ROOT))
    try:main()
    except KeyboardInterrupt:print('Checker stopped.')
    except Exception as error:
        reason=str(error) if isinstance(error,ValueError) else 'UNSUPPORTED_WINDOWS_SECURITY' if isinstance(error,OSError) else 'SETUP_OR_LAUNCH_FAILED'
        print(reason);raise SystemExit(1)
