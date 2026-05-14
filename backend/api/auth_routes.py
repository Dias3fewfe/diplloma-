"""Authentication endpoints.

Endpoints:
    POST /api/auth/login   — validate credentials, return JWT
    GET  /api/auth/verify  — check if a token is still valid
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from jose import JWTError, jwt
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config import (
    ACCESS_TOKEN_EXPIRE_HOURS,
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
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
