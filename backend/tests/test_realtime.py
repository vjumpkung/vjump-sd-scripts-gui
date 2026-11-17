"""The Socket.IO push channel: coalescing, the resource feed and the handshake rules.

Two rules for every WebSocket test: pass ``upgrade: websocket`` (Starlette's test
client does not send it and Engine.IO refuses without it), and never read a frame
before a spy has seen the event (``receive_text`` has no timeout).
"""

import asyncio
import json
import logging
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from app.services import realtime, system_monitor
from app.services.realtime import AUTH, DOWNLOADS, STATUS, TRAINING

from .conftest import wait_for
from .helpers import record_events, seen

POLLING = "/api/socket.io/?EIO=4&transport=polling"
WEBSOCKET = "/api/socket.io/?EIO=4&transport=websocket"
UPGRADE = {"upgrade": "websocket"}
PASSWORD = "s3cret-pass"
COOKIE = "sd_scripts_gui_session"


async def eventually(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Timed out waiting for condition")


def read_frame(ws) -> str:
    """The next Socket.IO frame; Engine.IO pings are answered and skipped."""
    while True:
        text = ws.receive_text()
        if text == "2":
            ws.send_text("3")
            continue
        return text


def connect_socketio(ws) -> None:
    assert ws.receive_text().startswith("0{")
    ws.send_text("40")
    assert ws.receive_text().startswith("40")


# ---------------------------------------------------------------------------
# the hub: coalescing and shutdown
# ---------------------------------------------------------------------------


async def test_notifications_coalesce_into_one_sorted_invalidate(make_app, monkeypatch):
    app = make_app()
    hub = app.state.realtime
    events = record_events(monkeypatch, app)

    hub.notify(TRAINING)
    hub.notify(STATUS, TRAINING, DOWNLOADS)
    hub.notify_log("job-b")
    hub.notify_log("job-a")
    hub.notify_log("job-b")
    await eventually(lambda: events)

    assert events == [
        (
            "invalidate",
            {"topics": ["downloads", "status", "training"], "logs": ["job-a", "job-b"]},
        )
    ]
    await asyncio.sleep(0.2)  # nothing else follows a flushed batch
    assert len(events) == 1


async def test_a_notification_during_an_emit_is_not_lost(make_app, monkeypatch):
    app = make_app()
    hub = app.state.realtime
    entered, release = asyncio.Event(), asyncio.Event()

    async def snapshot():
        entered.set()
        await release.wait()

    events = record_events(monkeypatch, app, snapshot)

    hub.notify(TRAINING)
    await asyncio.wait_for(entered.wait(), 5)
    hub.notify(AUTH)  # arrives while the first event is still being sent
    release.set()
    await eventually(lambda: len(events) == 2)

    assert [data for _, data in events] == [
        {"topics": ["training"], "logs": []},
        {"topics": ["auth"], "logs": []},
    ]


async def test_a_failing_emit_does_not_stop_later_flushes(
    make_app, monkeypatch, caplog
):
    app = make_app()
    hub = app.state.realtime
    monkeypatch.setattr(realtime, "COALESCE_SECONDS", 0.02)
    sent = []

    async def emit(event, data=None, **kwargs):
        sent.append(data)
        if len(sent) == 1:
            raise RuntimeError("boom")

    monkeypatch.setattr(hub.sio, "emit", emit)

    with caplog.at_level(logging.ERROR, logger=realtime.logger.name):
        hub.notify(TRAINING)
        await eventually(lambda: len(sent) == 1)
        hub.notify(STATUS)
        await eventually(lambda: len(sent) == 2)

    assert sent[1] == {"topics": ["status"], "logs": []}
    assert "Could not publish an invalidate event" in caplog.text


async def test_shutdown_cancels_pending_work_and_ignores_later_notifications(
    make_app, monkeypatch
):
    app = make_app()
    hub = app.state.realtime
    events = record_events(monkeypatch, app, coalesce=0.05)

    hub.notify(TRAINING)
    await hub.shutdown()
    hub.notify(STATUS)
    hub.notify_log("job")
    await asyncio.sleep(0.2)

    assert events == []


async def test_notify_without_a_running_loop_is_a_no_op(make_app):
    hub = make_app().state.realtime
    # Called from a worker thread: no running loop there, so nothing is scheduled.
    await asyncio.to_thread(hub.notify, TRAINING)
    assert hub._flush is None


# ---------------------------------------------------------------------------
# the resource feed handlers
# ---------------------------------------------------------------------------


async def test_other_subscribe_values_start_nothing(make_app):
    hub = make_app().state.realtime
    for args in [(), ("logs",), (["resources"],), (None,), ("Resources",), (1,)]:
        await hub._on_subscribe("sid", *args)
    await hub._on_subscribe("sid", "logs", "extra")
    assert hub._resource_sids == set()
    assert hub._sampler is None


# ---------------------------------------------------------------------------
# WebSocket and polling transports
# ---------------------------------------------------------------------------


def test_websocket_handshake_and_invalidate_frame(client, monkeypatch):
    events = record_events(monkeypatch, client.app, deliver=True)
    with client.websocket_connect(WEBSOCKET, headers=UPGRADE) as ws:
        first = ws.receive_text()
        assert first.startswith("0{") and '"sid"' in first
        ws.send_text("40")
        assert ws.receive_text().startswith("40")

        assert client.post("/api/training/queue/start").status_code == 200
        wait_for(lambda: seen(events, TRAINING), timeout=10)
        frame = read_frame(ws)

    assert frame.startswith("42")
    name, payload = json.loads(frame[2:])
    assert name == "invalidate"
    assert payload == {"topics": ["training"], "logs": []}


def test_polling_handshake_has_no_cors_headers(client):
    response = client.get(POLLING, headers={"Origin": "http://evil.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert response.text.startswith("0{")
    sid = json.loads(response.text[1:])["sid"]

    session = f"{POLLING}&sid={sid}"
    assert client.post(session, content="40").text == "OK"
    assert client.get(session).text.startswith("40")
    assert client.post(session, content="1").text == "OK"  # close the session


# ---------------------------------------------------------------------------
# resources subscription
# ---------------------------------------------------------------------------


@pytest.fixture
def resources(client, monkeypatch):
    monkeypatch.setattr(realtime, "RESOURCES_INTERVAL_SECONDS", 0.05)
    snapshot = {"timestamp": "now", "cpu": {"percent": 1.5}}
    monkeypatch.setattr(system_monitor, "_collect_resource_snapshot", lambda: snapshot)
    events = record_events(monkeypatch, client.app, deliver=True)
    return client.app.state.realtime, snapshot, events


def test_subscribing_streams_system_resources_until_unsubscribe(client, resources):
    hub, snapshot, events = resources
    with client.websocket_connect(WEBSOCKET, headers=UPGRADE) as ws:
        connect_socketio(ws)
        ws.send_text('42["subscribe","resources"]')
        wait_for(lambda: any(name == "system_resources" for name, _ in list(events)))
        name, payload = json.loads(read_frame(ws)[2:])
        assert (name, payload) == ("system_resources", snapshot)

        ws.send_text('42["unsubscribe","resources"]')
        wait_for(lambda: hub._sampler is None, timeout=10)
        assert hub._resource_sids == set()


def test_the_sampler_stops_when_the_subscriber_disconnects(client, resources):
    hub, _, events = resources
    with client.websocket_connect(WEBSOCKET, headers=UPGRADE) as ws:
        connect_socketio(ws)
        ws.send_text('42["subscribe","resources"]')
        wait_for(lambda: any(name == "system_resources" for name, _ in list(events)))
        assert hub._sampler is not None
    wait_for(lambda: hub._sampler is None, timeout=10)
    assert hub._resource_sids == set()


def test_unknown_topics_never_start_the_sampler_over_a_socket(client, resources):
    hub, _, events = resources
    with client.websocket_connect(WEBSOCKET, headers=UPGRADE) as ws:
        connect_socketio(ws)
        ws.send_text('42["subscribe","logs"]')
        time.sleep(0.3)  # long enough for six sampler intervals
        assert hub._sampler is None and hub._resource_sids == set()
        assert not any(name == "system_resources" for name, _ in list(events))


# ---------------------------------------------------------------------------
# the handshake origin rules (fetch-metadata middleware)
# ---------------------------------------------------------------------------

REFUSED_HANDSHAKES = {
    "cross-site": {"sec-fetch-site": "cross-site", "origin": "http://evil.example"},
    "same-site unlisted origin": {
        "sec-fetch-site": "same-site",
        "origin": "http://localhost:5173",
    },
    "foreign origin without fetch metadata": {"origin": "http://evil.example"},
    "null origin": {"origin": "null"},
    "other port": {"origin": "http://testserver:8080"},
    "explicit port against an unported host": {"origin": "https://testserver:80"},
    "invalid port": {"origin": "http://testserver:notaport"},
    "not an http origin": {"origin": "chrome-extension://testserver"},
    "forwarded host does not match": {
        "origin": "https://evil.example",
        "host": "127.0.0.1:8000",
        "x-forwarded-host": "gui.example.com",
    },
}

ACCEPTED_HANDSHAKES = {
    "no headers at all": {},
    "origin equals host": {"origin": "http://testserver"},
    "explicit default port": {"origin": "http://testserver:80"},
    "https origin behind a tls proxy": {"origin": "https://testserver"},
    "host with a port": {"origin": "http://127.0.0.1:8000", "host": "127.0.0.1:8000"},
    "origin matches x-forwarded-host": {
        "origin": "https://gui.example.com",
        "host": "127.0.0.1:8000",
        "x-forwarded-host": "gui.example.com",
    },
    "first x-forwarded-host value": {
        "origin": "https://gui.example.com",
        "host": "127.0.0.1:8000",
        "x-forwarded-host": "gui.example.com, proxy.internal",
    },
    "same-origin through a dev proxy": {
        "sec-fetch-site": "same-origin",
        "origin": "http://localhost:5173",
        "host": "127.0.0.1:8000",
    },
}


@pytest.mark.parametrize(
    "headers", REFUSED_HANDSHAKES.values(), ids=REFUSED_HANDSHAKES.keys()
)
def test_refused_handshakes_are_closed_with_1008(client, headers):
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(WEBSOCKET, headers={**UPGRADE, **headers}):
            pass
    assert error.value.code == 1008


@pytest.mark.parametrize(
    "headers", ACCEPTED_HANDSHAKES.values(), ids=ACCEPTED_HANDSHAKES.keys()
)
def test_accepted_handshakes_open_a_session(client, headers):
    with client.websocket_connect(WEBSOCKET, headers={**UPGRADE, **headers}) as ws:
        assert ws.receive_text().startswith("0")


@pytest.mark.parametrize(
    "headers",
    [
        {"sec-fetch-site": "cross-site", "origin": "http://localhost:5173"},
        {"sec-fetch-site": "same-site", "origin": "http://localhost:5173"},
        {"origin": "http://localhost:5173"},
    ],
    ids=["cross-site", "same-site", "no fetch metadata"],
)
def test_listed_origins_may_open_a_session(make_client, headers):
    with make_client(SD_SCRIPTS_GUI_CORS_ORIGINS="http://localhost:5173") as client:
        with client.websocket_connect(WEBSOCKET, headers={**UPGRADE, **headers}) as ws:
            assert ws.receive_text().startswith("0")


def test_the_http_rule_is_unchanged(client):
    foreign = {"Origin": "http://evil.example"}
    # A foreign Origin alone is not enough to refuse a plain HTTP request ...
    assert client.get("/api/system/status", headers=foreign).status_code == 200
    # ... but Sec-Fetch-Site still is.
    refused = client.get(
        "/api/system/status", headers={**foreign, "Sec-Fetch-Site": "cross-site"}
    )
    assert refused.status_code == 403
    assert refused.json() == {"detail": "Cross-site requests are not allowed"}
    # The polling transport is plain HTTP, so it follows the same rule.
    assert client.get(POLLING, headers=foreign).status_code == 200
    polling = client.get(POLLING, headers={"Sec-Fetch-Site": "cross-site"})
    assert polling.status_code == 403


# ---------------------------------------------------------------------------
# authentication
# ---------------------------------------------------------------------------


@pytest.fixture
def protected(make_client):
    with make_client(SD_SCRIPTS_GUI_PASSWORD=PASSWORD) as client:
        yield client


def test_socketio_requires_credentials(protected):
    with pytest.raises(WebSocketDisconnect) as error:
        with protected.websocket_connect(WEBSOCKET, headers=UPGRADE):
            pass
    assert error.value.code == 1008

    response = protected.get(POLLING)
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
    assert "www-authenticate" not in response.headers


def test_socketio_accepts_a_bearer_password(protected):
    headers = {**UPGRADE, "authorization": f"Bearer {PASSWORD}"}
    with protected.websocket_connect(WEBSOCKET, headers=headers) as ws:
        assert ws.receive_text().startswith("0{")


def test_socketio_accepts_the_session_cookie(protected):
    response = protected.post("/api/auth/login", json={"password": PASSWORD})
    assert response.status_code == 204
    token = protected.cookies.get(COOKIE)
    assert token
    protected.cookies.clear()  # only the explicit header may authenticate
    headers = {**UPGRADE, "cookie": f"{COOKIE}={token}"}
    with protected.websocket_connect(WEBSOCKET, headers=headers) as ws:
        assert ws.receive_text().startswith("0{")
