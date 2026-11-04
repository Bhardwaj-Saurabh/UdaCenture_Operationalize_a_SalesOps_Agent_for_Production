import pytest

from salesops_agent.config import load_config
from salesops_agent.data_access.crm_store import CrmStore


@pytest.fixture(scope="session")
def config():
    return load_config()


@pytest.fixture(scope="session")
def store(config):
    return CrmStore.from_directory(config.paths.crm_data)
