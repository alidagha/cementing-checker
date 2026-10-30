from pathlib import Path
import pytest
from tools.tmp_factory import LocalFactory

@pytest.fixture(scope='session')
def tmp_path_factory(tmp_path_factory):
    return LocalFactory(Path(__file__).resolve().parent,tmp_path_factory)
