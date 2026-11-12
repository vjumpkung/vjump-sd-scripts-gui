import base64

import pytest

PASSWORD = "s3cret-pass"


@pytest.fixture
def web_dir(tmp_path):
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<html>SPA index</html>", encoding="utf-8")
    (web / "assets" / "app.js").write_text("console.log('app')", encoding="utf-8")
    return web


def basic(user, password):
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


# ---------------------------------------------------------------------------
# Basic auth
# ---------------------------------------------------------------------------


def test_no_auth_by_default(client):
    response = client.get("/api/system/status")
    assert response.status_code == 200
    assert response.json()["auth"] is False


def test_password_protects_every_api_route(make_client):
    with make_client(SD_SCRIPTS_GUI_PASSWORD=PASSWORD) as client:
        for method, path in [
            ("get", "/api/system/status"),
            ("get", "/api/presets"),
            ("get", "/api/datasets"),
            ("post", "/api/training/queue/start"),
            ("get", "/api/fs/list"),
            ("get", "/api/does-not-exist"),
        ]:
            response = getattr(client, method)(path)
            assert response.status_code == 401, path
            assert (
                response.headers["www-authenticate"] == 'Basic realm="SD-Scripts GUI"'
            )
            assert response.json() == {"detail": "Authentication required"}


def test_any_username_with_the_right_password_is_accepted(make_client):
    with make_client(SD_SCRIPTS_GUI_PASSWORD=PASSWORD) as client:
        for user in ("admin", "", "someone else", "ä"):
            response = client.get("/api/system/status", headers=basic(user, PASSWORD))
            assert response.status_code == 200, user
            assert response.json()["auth"] is True
        assert client.get("/api/system/status", auth=("x", PASSWORD)).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        basic("admin", "wrong"),
        basic("admin", ""),
        basic("admin", PASSWORD + "x"),
        basic("admin", PASSWORD[:-1]),
        {"Authorization": "Basic !!!not-base64!!!"},
        {"Authorization": "Basic " + base64.b64encode(PASSWORD.encode()).decode()},
        {"Authorization": "Bearer " + PASSWORD},
        {"Authorization": "Basic"},
        {"Authorization": ""},
    ],
)
def test_wrong_credentials_are_rejected(make_client, headers):
    with make_client(SD_SCRIPTS_GUI_PASSWORD=PASSWORD) as client:
        response = client.get("/api/system/status", headers=headers)
        assert response.status_code == 401


def test_password_is_never_returned(make_client):
    with make_client(SD_SCRIPTS_GUI_PASSWORD=PASSWORD) as client:
        status = client.get("/api/system/status", auth=("a", PASSWORD))
        assert PASSWORD not in status.text


def test_the_spa_is_protected_too(make_client, web_dir):
    with make_client(
        SD_SCRIPTS_GUI_PASSWORD=PASSWORD, SD_SCRIPTS_GUI_WEB_DIR=web_dir
    ) as client:
        for path in ("/", "/index.html", "/assets/app.js", "/some/client/route"):
            assert client.get(path).status_code == 401, path
        ok = client.get("/", auth=("a", PASSWORD))
        assert ok.status_code == 200 and "SPA index" in ok.text
        asset = client.get("/assets/app.js", auth=("a", PASSWORD))
        assert asset.status_code == 200


def test_cors_preflight_works_without_credentials_and_401_carries_cors(make_client):
    origin = "http://localhost:5173"
    with make_client(
        SD_SCRIPTS_GUI_PASSWORD=PASSWORD, SD_SCRIPTS_GUI_CORS_ORIGINS=origin
    ) as client:
        preflight = client.options(
            "/api/system/status",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin
        denied = client.get("/api/system/status", headers={"Origin": origin})
        assert denied.status_code == 401
        assert denied.headers["access-control-allow-origin"] == origin


def test_cors_can_be_disabled(make_client):
    with make_client(SD_SCRIPTS_GUI_CORS_ORIGINS="") as client:
        response = client.get(
            "/api/system/status", headers={"Origin": "http://localhost:5173"}
        )
        assert "access-control-allow-origin" not in response.headers


def test_no_cors_headers_by_default(client):
    # The SPA is served by this app (same origin); CORS is opt-in for a dev server.
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        response = client.get("/api/system/status", headers={"Origin": origin})
        assert "access-control-allow-origin" not in response.headers
        preflight = client.options(
            "/api/system/status",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" not in preflight.headers


def test_explicit_cors_origins_are_allowed(make_client):
    with make_client(SD_SCRIPTS_GUI_CORS_ORIGINS="http://127.0.0.1:5173") as client:
        response = client.get(
            "/api/system/status", headers={"Origin": "http://127.0.0.1:5173"}
        )
        assert (
            response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
        )
        other = client.get(
            "/api/system/status", headers={"Origin": "http://evil.example"}
        )
        assert "access-control-allow-origin" not in other.headers


# ---------------------------------------------------------------------------
# Trusted hosts
# ---------------------------------------------------------------------------


def test_trusted_host_rejects_unknown_hosts(make_client):
    with make_client(SD_SCRIPTS_GUI_ALLOWED_HOSTS="127.0.0.1,localhost") as client:
        assert client.get("/api/system/status").status_code == 400  # "testserver"
        for host in ("localhost", "127.0.0.1", "localhost:8765"):
            response = client.get("/api/system/status", headers={"Host": host})
            assert response.status_code == 200, host
        for host in ("evil.example", "localhost.evil.example", "127.0.0.2"):
            response = client.get("/api/system/status", headers={"Host": host})
            assert response.status_code == 400, host


def test_any_host_is_allowed_by_default(client):
    assert (
        client.get("/api/system/status", headers={"Host": "anything"}).status_code
        == 200
    )


# ---------------------------------------------------------------------------
# SPA
# ---------------------------------------------------------------------------


def test_spa_serves_index_assets_and_falls_back(make_client, web_dir):
    with make_client(SD_SCRIPTS_GUI_WEB_DIR=web_dir) as client:
        index = client.get("/")
        assert index.status_code == 200 and "SPA index" in index.text
        assert "console.log" in client.get("/assets/app.js").text
        fallback = client.get("/datasets/some/route")
        assert fallback.status_code == 200 and "SPA index" in fallback.text
        assert client.get("/api/system/status").json()["version"]  # API wins


def test_unknown_api_routes_return_json_404_never_index_html(make_client, web_dir):
    with make_client(SD_SCRIPTS_GUI_WEB_DIR=web_dir) as client:
        for method in ("get", "post", "put", "delete", "patch"):
            response = getattr(client, method)("/api/does/not/exist")
            assert response.status_code == 404, method
            assert response.json() == {"detail": "Not Found"}
            assert "SPA index" not in response.text
        assert client.get("/api").status_code == 404
        assert client.get("/api/").json() == {"detail": "Not Found"}
        assert client.get("/apifoo").status_code == 200  # not under /api/


def test_unknown_api_routes_are_json_404_without_a_web_dir(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
