import os

from fastapi.testclient import TestClient
from src.dependencies import validate_csrf
from src.main import app


def test_measure_length_validation(client: TestClient):
    # Too short
    response = client.post(
        "/create",
        data={"measure": "ab", "options_raw": "A, B"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "at least 3 characters" in response.text

    # Too long
    response = client.post(
        "/create",
        data={"measure": "a" * 256, "options_raw": "A, B"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "at most 255 characters" in response.text


def test_options_count_validation(client: TestClient):
    # No write-in: need 2 options
    response = client.post(
        "/create",
        data={"measure": "Test", "options_raw": "Only One", "allow_write_in": ""},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "at least 2 options" in response.text

    # With write-in: 1 option is OK
    response = client.post(
        "/create",
        data={"measure": "Test", "options_raw": "Only One", "allow_write_in": "on"},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 204
    assert "HX-Redirect" in response.headers


def test_option_length_validation(client: TestClient):
    # Option too long
    response = client.post(
        "/create",
        data={"measure": "Test", "options_raw": "A, " + ("b" * 65)},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "between 1 and 64 characters" in response.text


def test_vote_write_in_length_validation(client: TestClient):
    # Create ballot allowing write-ins
    response = client.post(
        "/create",
        data={"measure": "Write-in Test", "options_raw": "A", "allow_write_in": "on"},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    ballot_id = response.headers["HX-Redirect"].split("/")[-1]

    # Vote with too long write-in
    response = client.post(
        f"/vote/{ballot_id}",
        data={"option": "__write_in__", "write_in_value": "w" * 65},
    )
    assert response.status_code == 200
    assert "at most 64 characters" in response.text


def test_csrf_protection(client: TestClient):
    # Ensure environment variable doesn't disable it
    old_val = os.environ.get("OPONN_SKIP_CSRF")
    os.environ["OPONN_SKIP_CSRF"] = "false"

    # Enable CSRF check for this test
    _ = app.dependency_overrides.pop(validate_csrf, None)

    try:
        # Try to post without CSRF Token
        response = client.post(
            "/create", data={"measure": "No CSRF", "options_raw": "A, B"}
        )
        assert response.status_code == 403
        assert "Invalid or Missing CSRF Token" in response.text
    finally:
        # Restore override and environment
        app.dependency_overrides[validate_csrf] = lambda: None
        if old_val:
            os.environ["OPONN_SKIP_CSRF"] = old_val
        else:
            _ = os.environ.pop("OPONN_SKIP_CSRF", None)


def test_scheduled_start_time_persistence(client: TestClient):
    """Regression test: Ensure scheduled_start_time persists on validation error."""
    # 1. Submit with valid scheduled time but invalid measure (too short)
    test_time = "2026-01-25T15:00:00Z"
    response = client.post(
        "/create",
        data={
            "measure": "a",  # Invalid
            "options_raw": "A, B",
            "start_time_type": "scheduled",
            "scheduled_start_time": test_time,
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200

    # 2. Verify hidden field still has the value
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(response.text, "html.parser")
    hidden_input = soup.find("input", {"name": "scheduled_start_time"})
    assert hidden_input is not None
    assert hidden_input["value"] == test_time
