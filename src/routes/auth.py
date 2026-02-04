from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi_sso.sso.github import GithubSSO
from fastapi_sso.sso.google import GoogleSSO
from itsdangerous import URLSafeTimedSerializer

from ..config import settings
from ..dependencies import get_auth_service
from ..services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = settings.secret_key
signer = URLSafeTimedSerializer(SECRET_KEY, salt="oponn-auth")

# Initialize SSO
google_sso = GoogleSSO(
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    redirect_uri="http://localhost:8000/auth/callback/google",
    allow_insecure_http=True,
)

github_sso = GithubSSO(
    client_id=settings.github_client_id,
    client_secret=settings.github_client_secret,
    redirect_uri="http://localhost:8000/auth/callback/github",
    allow_insecure_http=True,
)


@router.get("/login/{provider}")
async def login(provider: str):
    if provider == "google":
        # Check if we should use the mock login flow
        if settings.use_mock_auth:
            # Development Mock Login
            return RedirectResponse(
                url="/auth/callback/google?code=mock_code&state=mock_state"
            )
        return await google_sso.get_login_redirect()
    elif provider == "github":
        if settings.use_mock_auth:
            # Development Mock Login
            return RedirectResponse(
                url="/auth/callback/github?code=mock_code&state=mock_state"
            )
        return await github_sso.get_login_redirect()
    raise HTTPException(status_code=404, detail="Provider not supported")


@router.get("/callback/{provider}")
async def callback(
    provider: str,
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    user_email = ""
    provider_id = ""

    if provider == "google":
        # Check if we should use the mock login flow
        if settings.use_mock_auth:
            # Mock User
            user_email = "dev@example.com"
            provider_id = "mock_google_id_123"
        else:
            user = await google_sso.verify_and_process(request)
            if not user or not user.email:
                raise HTTPException(status_code=400, detail="Login failed")
            user_email = user.email
            provider_id = user.id or user.email  # Fallback if ID is missing
    elif provider == "github":
        if settings.use_mock_auth:
            # Mock User
            user_email = "dev_github@example.com"
            provider_id = "mock_github_id_123"
        else:
            user = await github_sso.verify_and_process(request)
            if not user or not user.email:
                raise HTTPException(status_code=400, detail="Login failed")
            user_email = user.email
            provider_id = user.id or user.email
    else:
        raise HTTPException(status_code=404, detail="Provider not supported")
    # Persist User
    db_user = await auth_service.authenticate_user(user_email, provider, provider_id)

    # Create Session Cookie
    user_id = str(db_user.id)
    token = signer.dumps(user_id)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="oponn_session",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,  # 7 days
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("oponn_session")
    return response


def get_current_user_id(request: Request) -> str | None:
    token = request.cookies.get("oponn_session")
    if not token:
        return None
    try:
        user_id = signer.loads(token, max_age=60 * 60 * 24 * 7)
        return str(user_id)
    except Exception:
        return None
