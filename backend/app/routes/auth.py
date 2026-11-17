"""Login page support: auth status, login (sets the session cookie) and logout."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from ..schemas.auth import LoginRequest
from ..services.auth import (
    COOKIE_NAMES,
    SECURE_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    AuthService,
    AuthState,
)
from ..services.realtime import AUTH
from ..utils.auth import throttled_detail

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_PATH = "/"


def _auth(request: Request) -> AuthService:
    return request.app.state.auth


@router.get("/status")
async def read_status(request: Request) -> dict[str, bool]:
    auth = _auth(request)
    if not auth.enabled:
        return {"auth_required": False, "authenticated": True}
    # Only the session cookie counts here: checking a Bearer or Basic password would
    # also feed the failed-attempt counter.
    authenticated = any(
        auth.session_valid(token) for token in auth.session_tokens(request.headers)
    )
    return {"auth_required": True, "authenticated": authenticated}


@router.post("/login", status_code=204)
async def login(payload: LoginRequest, request: Request) -> Response:
    auth = _auth(request)
    if not auth.enabled:
        return Response(status_code=204)
    result = auth.verify_password(payload.password)
    if result.state is AuthState.THROTTLED:
        raise HTTPException(
            status_code=429,
            detail=throttled_detail(result.retry_after),
            headers={"Retry-After": str(result.retry_after)},
        )
    if result.state is not AuthState.OK:
        raise HTTPException(status_code=401, detail="Wrong password")
    secure = request.url.scheme == "https"
    response = Response(status_code=204)
    response.set_cookie(
        auth.cookie_name(secure),
        auth.create_session(),
        max_age=SESSION_TTL_SECONDS,
        path=COOKIE_PATH,
        secure=secure,
        httponly=True,
        samesite="strict",
    )
    return response


@router.post("/logout", status_code=204)
async def logout(request: Request) -> Response:
    auth = _auth(request)
    for token in auth.session_tokens(request.headers):
        auth.revoke(token)
    request.app.state.realtime.notify(AUTH)
    response = Response(status_code=204)
    for name in COOKIE_NAMES:
        # A __Host- cookie can only be (over)written with Secure and Path=/.
        response.delete_cookie(
            name,
            path=COOKIE_PATH,
            secure=name == SECURE_COOKIE_NAME,
            httponly=True,
            samesite="strict",
        )
    return response
