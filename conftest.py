"""Native discovery evidence; accepted tests and their assertions remain unchanged."""
import json
import os
from pathlib import Path
import pytest
from tools.ci import execution_identity

def pytest_addoption(parser):
    parser.addoption('--audit-file',help='Write current ordered collection and phase results')

def pytest_configure(config):
    config._checker_audit={'nodeids':[],'reports':[],'warnings':[],
        'identity':execution_identity(Path(__file__).resolve().parent)}
    config._checker_progress = None
    if os.environ.get('CHECKER_DIAGNOSTIC_FILE'):
        if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('CHECKER_SHARD') not in ('A', 'B', 'C'):
            raise ValueError('Hosted native diagnostic binding required')
        from tools.ci_progress import Journal, Observer
        identity = config._checker_audit['identity']
        binding = {key:identity[key] for key in ('head', 'tree', 'run', 'attempt')}
        binding['shard'] = os.environ['CHECKER_SHARD']
        config._checker_progress = Journal(os.environ['CHECKER_DIAGNOSTIC_FILE'], binding)
        config._checker_observer = Observer(config._checker_progress)

def pytest_collection_finish(session):
    session.config._checker_audit['nodeids']=[item.nodeid for item in session.items]
    for ordinal, item in enumerate(session.items, 1):
        item._checker_ordinal = ordinal


@pytest.hookimpl(wrapper=True)
def pytest_collection(session):
    journal = session.config._checker_progress
    if journal is not None:
        journal.event('collection', edge='start')
    try:
        return (yield)
    finally:
        if journal is not None:
            journal.event('collection', edge='finish')


def progress(item, phase, edge):
    journal = item.config._checker_progress
    if journal is not None:
        journal.phase(item._checker_ordinal, item.nodeid, phase, edge)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item):
    progress(item, 'setup', 'start')
    try:
        return (yield)
    finally:
        progress(item, 'setup', 'finish')


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    progress(item, 'call', 'start')
    try:
        return (yield)
    finally:
        progress(item, 'call', 'finish')


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item):
    progress(item, 'teardown', 'start')
    try:
        return (yield)
    finally:
        progress(item, 'teardown', 'finish')

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


def pytest_unconfigure(config):
    if getattr(config, '_checker_progress', None) is not None:
        config._checker_observer.close()
