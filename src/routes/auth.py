import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi_sso.sso.google import GoogleSSO
from itsdangerous import URLSafeTimedSerializer

from ..dependencies import get_auth_service
from ..services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key_change_in_prod")
signer = URLSafeTimedSerializer(SECRET_KEY, salt="oponn-auth")

# Initialize SSO
google_sso = GoogleSSO(
    client_id=os.getenv("GOOGLE_CLIENT_ID", "mock-id"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET", "mock-secret"),
    redirect_uri=os.getenv(
        "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback/google"
    ),
    allow_insecure_http=True,
)


@router.get("/login/{provider}")
async def login(provider: str):
    if provider == "google":
        # Check if we should use the mock login flow
        # We allow mock login if no client ID is provided, allowing testing even in prod-sim
        if os.getenv("GOOGLE_CLIENT_ID", "mock-id") == "mock-id":
            # Development Mock Login
            return RedirectResponse(
                url="/auth/callback/google?code=mock_code&state=mock_state"
            )
        return await google_sso.get_login_redirect()
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
        if os.getenv("GOOGLE_CLIENT_ID", "mock-id") == "mock-id":
            # Mock User
            user_email = "dev@example.com"
            provider_id = "mock_google_id_123"
        else:
            user = await google_sso.verify_and_process(request)
            if not user or not user.email:
                raise HTTPException(status_code=400, detail="Login failed")
            user_email = user.email
            provider_id = user.id or user.email  # Fallback if ID is missing
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
