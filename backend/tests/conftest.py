import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app(0.01)) as test_client:
        yield test_client


@pytest.fixture
def slow_client():
    with TestClient(create_app(0.2)) as test_client:
        yield test_client
