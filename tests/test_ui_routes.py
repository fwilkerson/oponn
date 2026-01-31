from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_login_page_renders():
    response = client.get("/login")
    assert response.status_code == 200
    assert "sign_in_with_google" in response.text
    assert "sign_in_with_github" in response.text
    assert "continue_as_guest" in response.text


def test_index_page_links_to_login():
    response = client.get("/")
    assert response.status_code == 200
    # Check for the button link
    assert 'href="/login"' in response.text
    # Check for text in the button
    assert "sign_in" in response.text
