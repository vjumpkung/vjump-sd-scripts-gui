"""Shared-password authentication: login sessions, credential checks, brute-force backoff.

State lives in memory only, so a restart logs everyone out. A session token is random,
only its SHA-256 digest is stored, and it expires seven days after login. The password
is accepted as a session cookie, ``Authorization: Bearer <password>`` or
``Authorization: Basic <any user>:<password>``.

Password guesses share one global backoff (a per-client one would key on a spoofable
address): the first five consecutive failures are free, then the next password check is
refused for ``min(2 ** (failures - 5), 60)`` seconds. A valid session is never throttled.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import math
import secrets
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from starlette.datastructures import Headers
from starlette.requests import cookie_parser

SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_SESSIONS = 100
FREE_FAILURES = 5
MAX_LOCK_SECONDS = 60
COOKIE_NAME = "sd_scripts_gui_session"
# Over https the cookie gets the __Host- prefix: browsers then insist on Secure, Path=/
# and no Domain, so a sibling subdomain cannot plant or overwrite it.
SECURE_COOKIE_NAME = "__Host-sd_scripts_gui_session"
COOKIE_NAMES = (SECURE_COOKIE_NAME, COOKIE_NAME)


class AuthState(Enum):
    OK = "ok"
    MISSING = "missing"
    INVALID = "invalid"
    THROTTLED = "throttled"


@dataclass(frozen=True)
class AuthResult:
    state: AuthState
    # Whole seconds until the next password check is allowed (THROTTLED only).
    retry_after: int = 0


def _digest(value: bytes) -> bytes:
    return hashlib.sha256(value).digest()


class AuthService:
    def __init__(
        self, password: str | None, clock: Callable[[], float] = time.time
    ) -> None:
        self.clock = clock
        self.enabled = password is not None
        self._password_digest = _digest(password.encode("utf-8")) if password else b""
        # sha256(token) -> expiry. Insertion order is creation order, and the lifetime is
        # constant, so the oldest entry is also the first to expire.
        self._sessions: OrderedDict[str, float] = OrderedDict()
        self._failures = 0
        self._locked_until = 0.0

    # -- sessions -------------------------------------------------------------

    @staticmethod
    def _session_key(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _prune(self, now: float) -> None:
        while self._sessions:
            key, expires_at = next(iter(self._sessions.items()))
            if expires_at > now:
                break
            del self._sessions[key]

    def create_session(self) -> str:
        now = self.clock()
        self._prune(now)
        while len(self._sessions) >= MAX_SESSIONS:
            self._sessions.popitem(last=False)
        token = secrets.token_urlsafe(32)
        self._sessions[self._session_key(token)] = now + SESSION_TTL_SECONDS
        return token

    def session_valid(self, token: str) -> bool:
        now = self.clock()
        self._prune(now)
        return self._session_key(token) in self._sessions

    def revoke(self, token: str) -> None:
        self._sessions.pop(self._session_key(token), None)

    @staticmethod
    def cookie_name(secure: bool) -> str:
        return SECURE_COOKIE_NAME if secure else COOKIE_NAME

    @staticmethod
    def session_tokens(headers: Headers) -> list[str]:
        """Session cookie values of the request (either cookie name)."""
        jar = cookie_parser("; ".join(headers.getlist("cookie")))
        return [jar[name] for name in COOKIE_NAMES if jar.get(name)]

    # -- passwords ------------------------------------------------------------

    def verify_password(self, supplied: str) -> AuthResult:
        return self._check_password(supplied.encode("utf-8"))

    def _check_password(self, supplied: bytes) -> AuthResult:
        if not self.enabled:
            return AuthResult(AuthState.OK)
        if not supplied:  # an empty password is never a guess (it cannot match)
            return AuthResult(AuthState.INVALID)
        now = self.clock()
        if now < self._locked_until:
            return AuthResult(
                AuthState.THROTTLED, max(1, math.ceil(self._locked_until - now))
            )
        if secrets.compare_digest(_digest(supplied), self._password_digest):
            self._failures = 0
            self._locked_until = 0.0
            return AuthResult(AuthState.OK)
        # Capped so the exponent stays small; 2 ** 6 already exceeds the maximum lock.
        self._failures = min(self._failures + 1, FREE_FAILURES + 6)
        if self._failures >= FREE_FAILURES:
            lock = min(2 ** (self._failures - FREE_FAILURES), MAX_LOCK_SECONDS)
            self._locked_until = now + lock
        return AuthResult(AuthState.INVALID)

    @staticmethod
    def _password_from_authorization(header: str | None) -> bytes | None:
        """The password carried by a Bearer or Basic header, None when there is none."""
        if not header:
            return None
        scheme, _, credentials = header.partition(" ")
        credentials = credentials.strip()
        scheme = scheme.lower()
        if scheme == "bearer":
            # Header values are decoded as latin-1, so this recovers the original bytes.
            return credentials.encode("latin-1", errors="replace") or None
        if scheme == "basic":
            try:
                decoded = base64.b64decode(credentials, validate=True)
            except (binascii.Error, ValueError):
                return None
            _, separator, supplied = decoded.partition(b":")
            return (supplied or None) if separator else None
        return None

    # -- requests -------------------------------------------------------------

    def authenticate(self, headers: Headers) -> AuthResult:
        """Check a request: a valid session first, then a Bearer or Basic password."""
        if not self.enabled:
            return AuthResult(AuthState.OK)
        tokens = self.session_tokens(headers)
        if any(self.session_valid(token) for token in tokens):
            return AuthResult(AuthState.OK)
        supplied = self._password_from_authorization(headers.get("authorization"))
        if supplied is None:
            presented = bool(tokens) or "authorization" in headers
            return AuthResult(AuthState.INVALID if presented else AuthState.MISSING)
        return self._check_password(supplied)
