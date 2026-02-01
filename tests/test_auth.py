from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient


async def test_auth_login_redirects(client: AsyncClient):
    # Test Google Login Redirect (Mock Flow)
    response = await client.get("/auth/login/google", follow_redirects=False)
    assert response.status_code == 307
    assert "/auth/callback/google?code=mock_code" in response.headers["location"]

    # Test GitHub Login Redirect (Mock Flow)
    response = await client.get("/auth/login/github", follow_redirects=False)
    assert response.status_code == 307
    assert "/auth/callback/github?code=mock_code" in response.headers["location"]


async def test_auth_callback_google_mock(client: AsyncClient):
    # Mock the SSO verify logic
    # We need to mock the GoogleSSO.verify_and_process method
    # Since we can't easily patch the instance inside the route, we'll patch the dependency or the class.
    from src.routes.auth import google_sso

    mock_user = MagicMock()
    mock_user.email = "test@example.com"
    mock_user.display_name = "Test User"
    mock_user.id = "google-123"
    mock_user.picture = None

    # Async mock for verify_and_process
    google_sso.verify_and_process = AsyncMock(return_value=mock_user)

    # We also need to mock AuthService to verify it was called
    # But for E2E, we can just check if we get a cookie.

    response = await client.get(
        "/auth/callback/google?code=fake_code", follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "oponn_session" in response.cookies


async def test_auth_callback_github_mock(client: AsyncClient):
    from src.routes.auth import github_sso

    mock_user = MagicMock()
    mock_user.email = "test@github.com"
    mock_user.display_name = "Github User"
    mock_user.id = "github-456"
    mock_user.picture = "http://avatar.url"

    github_sso.verify_and_process = AsyncMock(return_value=mock_user)

    response = await client.get(
        "/auth/callback/github?code=fake_code", follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "oponn_session" in response.cookies
