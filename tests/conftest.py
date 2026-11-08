import pytest
from fastapi.testclient import TestClient

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.main import create_app

TEST_KEY = "test-api-key-with-at-least-32-characters"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
        api_key=TEST_KEY,
        docs_enabled=True,
    )


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings)) as client:
        yield client
