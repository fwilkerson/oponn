import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.dependencies import validate_csrf


@pytest.fixture
def client():
    # Override CSRF validation for tests
    app.dependency_overrides[validate_csrf] = lambda: None

    with TestClient(app) as c:
        yield c

    # Clean up overrides
    app.dependency_overrides.clear()
