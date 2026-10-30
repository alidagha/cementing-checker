"""Native discovery evidence; accepted tests and their assertions remain unchanged."""
import json
from pathlib import Path
import pytest
from tools.ci import execution_identity

def pytest_addoption(parser):
    parser.addoption('--audit-file',help='Write current ordered collection and phase results')

def pytest_configure(config):
    config._checker_audit={'nodeids':[],'reports':[],'warnings':[],
        'identity':execution_identity(Path(__file__).resolve().parent)}

def pytest_collection_finish(session):
    session.config._checker_audit['nodeids']=[item.nodeid for item in session.items]

@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report=yield
    item.config._checker_audit['reports'].append({'nodeid':report.nodeid,'phase':report.when,
        'outcome':report.outcome,'xfail':hasattr(report,'wasxfail'),'duration':report.duration})
    return report

def pytest_warning_recorded(warning_message, when, nodeid, location):
    # Detailed warning bodies stay in private logs; certificate records their presence.
    _warnings.append({'phase':when,'nodeid':nodeid,'category':warning_message.category.__name__})

_warnings=[]

def pytest_sessionfinish(session, exitstatus):
    destination=session.config.getoption('--audit-file')
    if destination:
        data=session.config._checker_audit
        data.update(exitstatus=int(exitstatus),warnings=_warnings)
        Path(destination).write_text(json.dumps(data,indent=2))
