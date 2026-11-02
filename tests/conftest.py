from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from bankbridge.api import create_app
from bankbridge.settings import Settings


@pytest.fixture
def test_context(tmp_path):
    settings = replace(Settings(), api_key="test-key", internal_token="test-internal", allow_demo_seed=True)
    app = create_app(settings, db_url="sqlite:///" + str(tmp_path / "test.db"))
    with TestClient(app) as client:
        yield client, app


@pytest.fixture
def auth():
    return {"X-API-Key": "test-key"}


@pytest.fixture
def internal():
    return {"X-Internal-Token": "test-internal"}
