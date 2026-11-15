"""The login page flow: session cookie, logout, expiry and the global backoff."""

import base64

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.services.auth import (
    MAX_SESSIONS,
    SESSION_TTL_SECONDS,
    AuthService,
    AuthState,
)

PASSWORD = "s3cret-pass"
COOKIE = "sd_scripts_gui_session"
HOST_COOKIE = "__Host-sd_scripts_gui_session"
PROTECTED = "/api/system/status"


class FakeClock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def protected(make_client):
    with make_client(SD_SCRIPTS_GUI_PASSWORD=PASSWORD) as client:
        yield client


@pytest.fixture
def clock(protected):
    fake = FakeClock()
    # The middleware and the routes share this one instance.
    protected.app.state.auth.clock = fake
    return fake


def login(client, password=PASSWORD, **kwargs):
    return client.post("/api/auth/login", json={"password": password}, **kwargs)


def bearer(password):
    return {"Authorization": f"Bearer {password}"}


def attributes(set_cookie):
    return {part.strip().lower() for part in set_cookie.split(";")[1:]}


# ---------------------------------------------------------------------------
# login, cookie and logout
# ---------------------------------------------------------------------------


def test_login_sets_a_strict_http_only_cookie(protected):
    assert protected.get(PROTECTED).status_code == 401
    response = login(protected)
    assert response.status_code == 204
    assert response.content == b""
    assert "www-authenticate" not in response.headers
    header = response.headers["set-cookie"]
    name, _, rest = header.partition("=")
    assert name == COOKIE
    assert PASSWORD not in header
    attrs = attributes(header)
    assert {"httponly", "samesite=strict", "path=/"} <= attrs
    assert f"max-age={SESSION_TTL_SECONDS}" in attrs
    assert SESSION_TTL_SECONDS == 7 * 24 * 60 * 60
    assert "secure" not in attrs and "domain" not in " ".join(attrs)
    # The cookie alone now opens the API.
    assert protected.get(PROTECTED).status_code == 200


def test_https_uses_a_host_prefixed_secure_cookie(protected):
    secure = TestClient(protected.app, base_url="https://testserver")
    response = login(secure)
    assert response.status_code == 204
    header = response.headers["set-cookie"]
    assert header.startswith(f"{HOST_COOKIE}=")
    attrs = attributes(header)
    assert {"secure", "httponly", "samesite=strict", "path=/"} <= attrs
    assert not any(attr.startswith("domain") for attr in attrs)
    assert f"max-age={SESSION_TTL_SECONDS}" in attrs
    assert secure.get(PROTECTED).status_code == 200


def test_wrong_password_is_a_plain_401(protected):
    for wrong in ("nope", "", PASSWORD + "x", PASSWORD[:-1]):
        response = login(protected, wrong)
        assert response.status_code == 401, wrong
        assert response.json() == {"detail": "Wrong password"}
        assert "set-cookie" not in response.headers
        assert "www-authenticate" not in response.headers
    assert protected.get(PROTECTED).status_code == 401


def test_login_validates_the_body(protected):
    assert protected.post("/api/auth/login", json={}).status_code == 422
    assert login(protected, "x" * 4097).status_code == 422
    assert login(protected, "x" * 4096).status_code == 401


def test_bearer_and_basic_still_work(protected):
    assert protected.get(PROTECTED, headers=bearer(PASSWORD)).status_code == 200
    assert protected.get(PROTECTED, headers=bearer("wrong")).status_code == 401
    token = base64.b64encode(f"anyone:{PASSWORD}".encode()).decode()
    assert (
        protected.get(
            PROTECTED, headers={"Authorization": f"Basic {token}"}
        ).status_code
        == 200
    )
    # Neither of them sets a cookie.
    assert (
        "set-cookie" not in protected.get(PROTECTED, headers=bearer(PASSWORD)).headers
    )


def test_a_non_ascii_password_works_everywhere(make_client):
    password = "pässwörd-日本"
    with make_client(SD_SCRIPTS_GUI_PASSWORD=password) as client:
        assert login(client, password).status_code == 204
        client.cookies.clear()
        basic = base64.b64encode(f"u:{password}".encode()).decode()
        ok = client.get(PROTECTED, headers={"Authorization": f"Basic {basic}"})
        assert ok.status_code == 200
        # Header values travel as raw bytes: the UTF-8 encoding of the password.
        raw = {"Authorization": b"Bearer " + password.encode("utf-8")}
        assert client.get(PROTECTED, headers=raw).status_code == 200


def test_logout_revokes_the_session(protected):
    login(protected)
    token = protected.cookies.get(COOKIE)
    assert token
    assert protected.get("/api/auth/status").json()["authenticated"] is True

    response = protected.post("/api/auth/logout")
    assert response.status_code == 204
    cleared = response.headers.get_list("set-cookie")
    assert any(h.startswith(f"{COOKIE}=") for h in cleared)
    assert any(h.startswith(f"{HOST_COOKIE}=") for h in cleared)
    for header in cleared:
        assert "max-age=0" in attributes(header)
        assert "path=/" in attributes(header)
        if header.startswith(HOST_COOKIE):
            assert "secure" in attributes(header)
    assert protected.get("/api/auth/status").json()["authenticated"] is False

    # Replaying the old cookie must fail: the session is gone on the server too.
    protected.cookies.clear()
    replay = protected.get(PROTECTED, headers={"Cookie": f"{COOKIE}={token}"})
    assert replay.status_code == 401


def test_logout_is_public_and_harmless_when_logged_out(protected):
    assert protected.post("/api/auth/logout").status_code == 204
    # A stale or foreign cookie value is ignored, not an error.
    response = protected.post("/api/auth/logout", headers={"Cookie": f"{COOKIE}=junk"})
    assert response.status_code == 204


def test_auth_status_is_public_and_reflects_the_session(protected):
    before = protected.get("/api/auth/status")
    assert before.status_code == 200
    assert before.json() == {"auth_required": True, "authenticated": False}
    login(protected)
    assert protected.get("/api/auth/status").json() == {
        "auth_required": True,
        "authenticated": True,
    }


def test_auth_status_ignores_passwords_and_never_counts_failures(protected, clock):
    for _ in range(20):
        response = protected.get("/api/auth/status", headers=bearer("wrong"))
        assert response.json() == {"auth_required": True, "authenticated": False}
    # A correct Bearer is not a session either.
    response = protected.get("/api/auth/status", headers=bearer(PASSWORD))
    assert response.json()["authenticated"] is False
    assert login(protected).status_code == 204


def test_without_a_password_auth_is_off(client):
    assert client.get("/api/auth/status").json() == {
        "auth_required": False,
        "authenticated": True,
    }
    response = login(client, "whatever")
    assert response.status_code == 204
    assert "set-cookie" not in response.headers
    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert client.get(PROTECTED).status_code == 200


def test_the_cookie_of_another_app_instance_is_rejected(make_client):
    with make_client(SD_SCRIPTS_GUI_PASSWORD=PASSWORD) as first:
        login(first)
        token = first.cookies.get(COOKIE)
        assert first.get("/api/auth/status").json()["authenticated"] is True
    with make_client(SD_SCRIPTS_GUI_PASSWORD=PASSWORD) as second:
        headers = {"Cookie": f"{COOKIE}={token}"}
        assert second.get(PROTECTED, headers=headers).status_code == 401
        status = second.get("/api/auth/status", headers=headers)
        assert status.json()["authenticated"] is False


def test_cross_site_login_and_logout_are_refused(protected):
    for _ in range(10):
        response = login(protected, headers={"Sec-Fetch-Site": "cross-site"})
        assert response.status_code == 403
        assert "set-cookie" not in response.headers
    response = protected.post(
        "/api/auth/logout", headers={"Sec-Fetch-Site": "same-site"}
    )
    assert response.status_code == 403
    # Refused before the password is looked at, so the backoff is untouched.
    assert (
        login(protected, headers={"Sec-Fetch-Site": "same-origin"}).status_code == 204
    )


def test_websockets_under_api_are_closed_without_credentials(protected):
    with pytest.raises(WebSocketDisconnect) as error:
        with protected.websocket_connect("/api/anything"):
            pass
    assert error.value.code == 1008


# ---------------------------------------------------------------------------
# session lifetime
# ---------------------------------------------------------------------------


def test_a_session_expires_after_seven_days(protected, clock):
    login(protected)
    clock.advance(SESSION_TTL_SECONDS - 1)
    assert protected.get(PROTECTED).status_code == 200
    clock.advance(2)
    assert protected.get(PROTECTED).status_code == 401
    assert protected.get("/api/auth/status").json()["authenticated"] is False


def test_logins_do_not_extend_other_sessions_and_each_has_its_own_expiry(
    protected, clock
):
    login(protected)
    first = protected.cookies.get(COOKIE)
    clock.advance(SESSION_TTL_SECONDS // 2)
    protected.cookies.clear()
    login(protected)
    second = protected.cookies.get(COOKIE)
    assert first != second
    clock.advance(SESSION_TTL_SECONDS // 2 + 10)
    assert protected.get(PROTECTED).status_code == 200  # the second session
    protected.cookies.clear()
    assert (
        protected.get(PROTECTED, headers={"Cookie": f"{COOKIE}={first}"}).status_code
        == 401
    )


def test_at_most_100_sessions_are_kept_and_the_oldest_is_evicted():
    clock = FakeClock()
    auth = AuthService(PASSWORD, clock=clock)
    tokens = []
    for _ in range(MAX_SESSIONS + 1):
        tokens.append(auth.create_session())
        clock.advance(1)
    assert len(set(tokens)) == len(tokens)
    assert not auth.session_valid(tokens[0])
    assert all(auth.session_valid(token) for token in tokens[1:])
    auth.revoke(tokens[1])
    assert not auth.session_valid(tokens[1])
    auth.revoke(tokens[1])  # revoking twice is fine


def test_only_the_digest_of_a_token_is_stored():
    auth = AuthService(PASSWORD)
    token = auth.create_session()
    assert token not in auth._sessions
    assert len(token) >= 43


# ---------------------------------------------------------------------------
# global backoff
# ---------------------------------------------------------------------------


def fail_logins(client, count):
    for number in range(count):
        response = login(client, "wrong")
        assert response.status_code == 401, number


def test_five_failures_are_free_then_the_next_attempt_is_locked(protected, clock):
    fail_logins(protected, 5)
    response = login(protected, "wrong")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "1"
    assert "www-authenticate" not in response.headers
    assert response.json() == {
        "detail": "Too many failed login attempts. Try again in 1 seconds."
    }
    # The correct password is not checked while locked (it must not act as an oracle).
    assert login(protected).status_code == 429
    assert "set-cookie" not in login(protected).headers

    clock.advance(1)
    assert login(protected, "wrong").status_code == 401  # a free-again attempt
    locked = login(protected, "wrong")
    assert locked.status_code == 429 and locked.headers["retry-after"] == "2"
    clock.advance(1)
    assert login(protected).status_code == 429  # still 1 second to go
    clock.advance(1.5)
    assert login(protected).status_code == 204


def test_the_lock_grows_and_is_capped_at_sixty_seconds(protected, clock):
    expected = [1, 2, 4, 8, 16, 32, 60, 60]
    fail_logins(protected, 5)
    for seconds in expected:
        locked = login(protected, "wrong")
        assert locked.status_code == 429
        assert locked.headers["retry-after"] == str(seconds)
        clock.advance(seconds)
        assert login(protected, "wrong").status_code == 401  # lock over, one more miss
    clock.advance(10_000)
    assert login(protected, "wrong").status_code == 401
    assert login(protected, "wrong").status_code == 429


def test_success_resets_the_counter(protected, clock):
    fail_logins(protected, 4)
    assert login(protected).status_code == 204
    # The earlier four misses are forgotten: five more are free again.
    fail_logins(protected, 5)
    assert login(protected, "wrong").status_code == 429
    clock.advance(1)
    assert login(protected).status_code == 204
    fail_logins(protected, 5)


def test_a_valid_session_is_never_throttled(protected, clock):
    login(protected)
    fail_logins(protected, 5)
    assert login(protected, "wrong").status_code == 429
    for _ in range(3):
        assert protected.get(PROTECTED).status_code == 200
    assert protected.get("/api/auth/status").json()["authenticated"] is True
    # Logging out and in again is throttled, but the cookie worked until then.
    assert protected.post("/api/auth/logout").status_code == 204
    assert login(protected).status_code == 429


def test_bearer_and_basic_share_the_same_backoff(protected, clock):
    fail_logins(protected, 3)
    for _ in range(2):
        assert protected.get(PROTECTED, headers=bearer("wrong")).status_code == 401
    blocked = protected.get(PROTECTED, headers=bearer("wrong"))
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "1"
    assert "www-authenticate" not in blocked.headers
    assert blocked.json()["detail"].startswith("Too many failed login attempts")
    # The right password over Bearer and Basic is refused too while locked.
    assert protected.get(PROTECTED, headers=bearer(PASSWORD)).status_code == 429
    assert protected.get(PROTECTED, auth=("u", PASSWORD)).status_code == 429
    clock.advance(1)
    assert protected.get(PROTECTED, auth=("u", PASSWORD)).status_code == 200
    fail_logins(protected, 5)  # reset by the success above


def test_requests_without_a_password_attempt_never_count(protected, clock):
    for _ in range(30):
        assert protected.get(PROTECTED).status_code == 401
        assert (
            protected.get(PROTECTED, headers={"Cookie": f"{COOKIE}=stale"}).status_code
            == 401
        )
        malformed = {"Authorization": "Basic !!!not-base64!!!"}
        assert protected.get(PROTECTED, headers=malformed).status_code == 401
        assert protected.get(PROTECTED, headers=bearer("")).status_code == 401
    assert login(protected).status_code == 204


def test_the_service_reports_states_directly():
    clock = FakeClock()
    auth = AuthService(PASSWORD, clock=clock)
    assert auth.verify_password(PASSWORD).state is AuthState.OK
    for _ in range(5):
        assert auth.verify_password("x").state is AuthState.INVALID
    locked = auth.verify_password("x")
    assert locked.state is AuthState.THROTTLED and locked.retry_after == 1
    disabled = AuthService(None)
    assert not disabled.enabled
    assert disabled.verify_password("anything").state is AuthState.OK
