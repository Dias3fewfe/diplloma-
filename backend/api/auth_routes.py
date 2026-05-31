"""Authentication endpoints.

Endpoints:
    POST /api/auth/login              — validate credentials, return JWT
    GET  /api/auth/verify             — check if a token is still valid
    GET  /api/auth/google             — redirect to Google OAuth consent screen
    GET  /api/auth/google/callback    — handle Google OAuth callback, issue JWT
"""

import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config import (
    ACCESS_TOKEN_EXPIRE_HOURS,
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    FRONTEND_URL,
    GOOGLE_ALLOWED_EMAIL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    SECRET_KEY,
)

router_auth = APIRouter(prefix="/api/auth")

ALGORITHM = "HS256"


class LoginRequest(BaseModel):
    """Credentials payload for the login endpoint."""
    username: str
    password: str


def _create_token(username: str) -> str:
    """Create a signed JWT with a 24-hour expiry.

    Args:
        username: The authenticated user's name (stored as 'sub' claim).

    Returns:
        Encoded JWT string.
    """
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    """Decode and validate a JWT, returning the subject (username).

    Args:
        token: Encoded JWT string.

    Returns:
        Username string from 'sub' claim.

    Raises:
        HTTPException 401: If the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub", "")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router_auth.post("/login")
def login(body: LoginRequest) -> dict:
    """Validate credentials and return a JWT access token.

    Args:
        body: LoginRequest with username and password fields.

    Returns:
        Dict with status, token, and username.

    Raises:
        HTTPException 401: If credentials are incorrect.
    """
    if body.username != ADMIN_USERNAME or body.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = _create_token(body.username)
    return {"status": "ok", "data": {"token": token, "username": body.username}, "error": None}


@router_auth.get("/google")
def google_login() -> RedirectResponse:
    """Redirect the user to the Google OAuth consent screen."""
    params = urllib.parse.urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router_auth.get("/google/callback")
async def google_callback(code: str = "", error: str = "") -> RedirectResponse:
    """Exchange the Google authorization code for a JWT and redirect to the frontend.

    Args:
        code: Authorization code returned by Google.
        error: Error string if the user denied access.

    Returns:
        Redirect to frontend with ?token= on success or ?error= on failure.
    """
    if error or not code:
        return RedirectResponse(f"{FRONTEND_URL}?error=google_denied")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        return RedirectResponse(f"{FRONTEND_URL}?error=google_token_failed")

    access_token = token_resp.json().get("access_token", "")

    async with httpx.AsyncClient() as client:
        info_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if info_resp.status_code != 200:
        return RedirectResponse(f"{FRONTEND_URL}?error=google_userinfo_failed")

    user_info = info_resp.json()
    email: str = user_info.get("email", "")

    if GOOGLE_ALLOWED_EMAIL and email != GOOGLE_ALLOWED_EMAIL:
        return RedirectResponse(f"{FRONTEND_URL}?error=google_not_allowed")

    jwt_token = _create_token(email)
    params = urllib.parse.urlencode({"token": jwt_token, "username": email})
    return RedirectResponse(f"{FRONTEND_URL}?{params}")


@router_auth.get("/verify")
def verify(authorization: str = Header(default="")) -> dict:
    """Check whether the provided Bearer token is valid.

    Args:
        authorization: Value of the Authorization header (Bearer <token>).

    Returns:
        Dict confirming the token is valid and who it belongs to.

    Raises:
        HTTPException 401: If the token is missing, invalid, or expired.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.removeprefix("Bearer ")
    username = decode_token(token)
    return {"status": "ok", "data": {"username": username}, "error": None}
