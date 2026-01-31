from fastapi.testclient import TestClient


def test_auth_login_redirects(client: TestClient):
    # Test Google Login Redirect
    response = client.get("/auth/login/google", follow_redirects=False)
    assert response.status_code == 307
    assert "location" in response.headers

    # Test Github Login Redirect
    response = client.get("/auth/login/github", follow_redirects=False)
    assert response.status_code == 307
    assert "location" in response.headers


def test_auth_callback_google_mock(client: TestClient):
    # Simulate a successful callback with mock credentials
    response = client.get(
        "/auth/callback/google?code=mock_code&state=mock_state", follow_redirects=False
    )
    # Expect redirect to dashboard and session cookie
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "oponn_session" in response.cookies


def test_auth_callback_github_mock(client: TestClient):
    # Simulate a successful callback with mock credentials (GET for simplicity in mock mode)
    response = client.get(
        "/auth/callback/github?code=mock_code&state=mock_state", follow_redirects=False
    )
    # Expect redirect to dashboard and session cookie
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "oponn_session" in response.cookies
