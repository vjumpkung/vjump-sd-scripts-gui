import base64

import pytest

PASSWORD = "s3cret-pass"
IMMUTABLE = "public, max-age=31536000, immutable"


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
# Password protection (Basic and Bearer; the login page is in test_login.py)
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
            # A WWW-Authenticate header would make browsers show their own prompt.
            assert "www-authenticate" not in response.headers, path
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
        {"Authorization": "Bearer wrong"},
        {"Authorization": "Bearer"},
        {"Authorization": "Digest " + PASSWORD},
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


def test_the_spa_is_public_but_the_api_is_not(make_client, web_dir):
    with make_client(
        SD_SCRIPTS_GUI_PASSWORD=PASSWORD, SD_SCRIPTS_GUI_WEB_DIR=web_dir
    ) as client:
        # The login page is part of the SPA, so its shell and assets must load.
        for path in ("/", "/index.html", "/assets/app.js", "/some/client/route"):
            response = client.get(path)
            assert response.status_code == 200, path
            assert "www-authenticate" not in response.headers, path
        assert "SPA index" in client.get("/").text
        assert client.get("/api/system/status").status_code == 401
        assert client.get("/api/nope").status_code == 401


def test_the_api_docs_need_authentication(make_client):
    with make_client(SD_SCRIPTS_GUI_PASSWORD=PASSWORD) as client:
        for path in ("/api/docs", "/api/openapi.json"):
            assert client.get(path).status_code == 401, path
            ok = client.get(path, auth=("a", PASSWORD))
            assert ok.status_code == 200, path
        assert "paths" in client.get("/api/openapi.json", auth=("a", PASSWORD)).json()
        # The old public locations are gone.
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404, path


def test_the_api_docs_are_served_under_api_without_a_password(client):
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/redoc").status_code == 404


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


def test_spa_shell_revalidates_and_hashed_assets_are_immutable(make_client, web_dir):
    (web_dir / "logo.png").write_bytes(b"\x89PNG\r\n")
    with make_client(SD_SCRIPTS_GUI_WEB_DIR=web_dir) as client:
        for path in ("/", "/index.html", "/logo.png", "/datasets/some/route"):
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.headers["cache-control"] == "no-cache", path
            assert response.headers["etag"], path
        asset = client.get("/assets/app.js")
        assert asset.status_code == 200
        assert asset.headers["cache-control"] == IMMUTABLE
        # The API is not the SPA: no caching policy of ours there.
        assert "cache-control" not in client.get("/api/system/status").headers


def test_spa_revalidation_is_a_304_until_index_html_changes(make_client, web_dir):
    with make_client(SD_SCRIPTS_GUI_WEB_DIR=web_dir) as client:
        for path, policy in (
            ("/", "no-cache"),
            ("/datasets/some/route", "no-cache"),
            ("/assets/app.js", IMMUTABLE),
        ):
            etag = client.get(path).headers["etag"]
            response = client.get(path, headers={"If-None-Match": etag})
            assert response.status_code == 304, path
            assert response.headers["cache-control"] == policy, path
            assert response.headers["etag"] == etag, path
        # An update rewrites index.html: the old ETag now gets the new file.
        stale = client.get("/").headers["etag"]
        (web_dir / "index.html").write_text(
            "<html>SPA index v2</html>", encoding="utf-8"
        )
        fresh = client.get("/", headers={"If-None-Match": stale})
        assert fresh.status_code == 200 and "v2" in fresh.text
        assert fresh.headers["cache-control"] == "no-cache"
        assert fresh.headers["etag"] != stale


def test_missing_assets_are_json_404_never_index_html(make_client, web_dir):
    with make_client(SD_SCRIPTS_GUI_WEB_DIR=web_dir) as client:
        # An old lazy chunk after an update must not be answered with index.html.
        for path in ("/assets/logs-CAkc99ji.js", "/assets/gone.css", "/assets"):
            response = client.get(path)
            assert response.status_code == 404, path
            assert response.json() == {"detail": "Not Found"}, path
            assert "immutable" not in response.headers.get("cache-control", ""), path
        assert client.get("/assetsfoo").status_code == 200  # not under /assets/


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
