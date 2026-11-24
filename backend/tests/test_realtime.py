"""The Socket.IO push channel: coalescing, the resource feed and the handshake rules.

Two rules for every WebSocket test: pass ``upgrade: websocket`` (Starlette's test
client does not send it and Engine.IO refuses without it), and never read a frame
before a spy has seen the event (``receive_text`` has no timeout).
"""

import asyncio
import json
import logging
import time
from uuid import uuid4

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


def subscribe_logs(ws, job_id, *, accepted=True) -> None:
    ws.send_text("421" + json.dumps(["subscribe", {"logs": job_id}]))
    assert read_frame(ws) == ("431[true]" if accepted else "431[false]")


# ---------------------------------------------------------------------------
# the hub: coalescing and shutdown
# ---------------------------------------------------------------------------


async def test_notifications_coalesce_into_one_sorted_invalidate(make_app, monkeypatch):
    app = make_app()
    hub = app.state.realtime
    events = record_events(monkeypatch, app)

    hub.notify(TRAINING)
    hub.notify(STATUS, TRAINING, DOWNLOADS)
    await eventually(lambda: events)

    assert events == [
        (
            "invalidate",
            {"topics": ["downloads", "status", "training"]},
        )
    ]
    await asyncio.sleep(0.2)  # nothing else follows a flushed batch
    assert len(events) == 1


async def test_a_notification_during_an_emit_is_not_lost(make_app, monkeypatch):
    app = make_app()
    hub = app.state.realtime
    entered, release = asyncio.Event(), asyncio.Event()
    entered_count = 0

    async def snapshot():
        nonlocal entered_count
        entered_count += 1
        entered.set()
        await release.wait()

    events = record_events(monkeypatch, app, snapshot)

    hub.notify(TRAINING)
    await asyncio.wait_for(entered.wait(), 5)
    hub.notify(AUTH)  # arrives while the first event is still being sent
    await asyncio.sleep(2 * realtime.COALESCE_SECONDS)
    assert entered_count == 1
    release.set()
    await eventually(lambda: len(events) == 2)

    assert [data for _, data in events] == [
        {"topics": ["training"]},
        {"topics": ["auth"]},
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

    assert sent[1] == {"topics": ["status"]}
    assert "Could not publish Socket.IO event invalidate" in caplog.text


async def test_shutdown_cancels_pending_work_and_ignores_later_notifications(
    make_app, monkeypatch
):
    app = make_app()
    hub = app.state.realtime
    events = record_events(monkeypatch, app, coalesce=0.05)

    hub.notify(TRAINING)
    await hub.shutdown()
    hub.notify(STATUS)
    hub.notify_job_progress("job", {"step": 42})
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
    assert payload == {"topics": ["training"]}


def test_log_pushes_are_coalesced_and_scoped_to_subscribers(client, monkeypatch):
    hub = client.app.state.realtime
    events = record_events(monkeypatch, client.app, deliver=True)
    job_id = str(uuid4())

    def publish():
        hub.notify_log(job_id, 7, "é".encode())
        hub.notify_log(job_id, 9, b" ok\n")
        hub.notify_log(str(uuid4()), 0, b"unsubscribed")
        hub.notify(TRAINING)

    with (
        client.websocket_connect(WEBSOCKET, headers=UPGRADE) as subscriber,
        client.websocket_connect(WEBSOCKET, headers=UPGRADE) as other,
    ):
        connect_socketio(subscriber)
        connect_socketio(other)
        subscribe_logs(subscriber, "invalid", accepted=False)
        subscribe_logs(subscriber, job_id)
        subscribe_logs(subscriber, job_id)
        subscribe_logs(other, str(uuid4()))
        client.portal.call(publish)
        wait_for(lambda: seen(events, TRAINING))
        assert json.loads(read_frame(subscriber)[2:]) == [
            "job_log",
            {"job_id": job_id, "offset": 7, "next_offset": 13, "content": "é ok\n"},
        ]
        assert json.loads(read_frame(subscriber)[2:])[0] == "invalidate"
        assert json.loads(read_frame(other)[2:])[0] == "invalidate"

        subscriber.send_text("422" + json.dumps(["unsubscribe", {"logs": job_id}]))
        assert read_frame(subscriber) == "432[true]"
        client.portal.call(publish)
        wait_for(lambda: seen(events, TRAINING, start=2))
        assert json.loads(read_frame(subscriber)[2:])[0] == "invalidate"
        assert [event for event, _ in events].count("job_log") == 1


def test_log_overflow_marks_latest_end_and_next_batch_recovers(client, monkeypatch):
    hub = client.app.state.realtime
    events = record_events(monkeypatch, client.app, deliver=True)
    job_id = str(uuid4())
    end = realtime.LOG_CHUNK_BYTES + 2

    def burst():
        hub.notify_log(job_id, 0, b"x" * realtime.LOG_CHUNK_BYTES)
        hub.notify_log(job_id, end - 2, b"x")
        hub.notify_log(job_id, end - 1, b"x")

    with client.websocket_connect(WEBSOCKET, headers=UPGRADE) as ws:
        connect_socketio(ws)
        subscribe_logs(ws, job_id)
        client.portal.call(burst)
        wait_for(lambda: len(events) == 1)
        assert json.loads(read_frame(ws)[2:]) == [
            "job_log",
            {"job_id": job_id, "offset": end, "next_offset": end, "content": ""},
        ]
        client.portal.call(hub.notify_log, job_id, end, b"next")
        wait_for(lambda: len(events) == 2)
        assert json.loads(read_frame(ws)[2:]) == [
            "job_log",
            {
                "job_id": job_id,
                "offset": end,
                "next_offset": end + 4,
                "content": "next",
            },
        ]


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


def test_logout_disconnects_only_the_socket_bound_to_the_revoked_cookie(
    protected, monkeypatch
):
    assert (
        protected.post("/api/auth/login", json={"password": PASSWORD}).status_code
        == 204
    )
    hub = protected.app.state.realtime
    events = record_events(monkeypatch, protected.app, deliver=True)
    headers = {**UPGRADE, "authorization": f"Bearer {PASSWORD}"}
    with (
        protected.websocket_connect(WEBSOCKET, headers=headers) as session,
        protected.websocket_connect(
            WEBSOCKET, headers={**headers, "cookie": f"{COOKIE}=invalid"}
        ) as bearer,
    ):
        connect_socketio(session)
        connect_socketio(bearer)
        assert len(hub._sessions) == 1
        assert protected.post("/api/auth/logout").status_code == 204
        assert read_frame(session) == "41"
        assert not hub._sessions
        wait_for(lambda: seen(events, AUTH))
        assert json.loads(read_frame(bearer)[2:]) == [
            "invalidate",
            {"topics": ["auth"]},
        ]


@pytest.mark.parametrize("expire_during_emit", [False, True])
def test_expired_session_receives_no_log_data(
    protected, monkeypatch, expire_during_emit
):
    auth = protected.app.state.auth
    now = auth.clock()
    monkeypatch.setattr(auth, "clock", lambda: now)
    assert (
        protected.post("/api/auth/login", json={"password": PASSWORD}).status_code
        == 204
    )
    hub = protected.app.state.realtime
    monkeypatch.setattr(realtime, "COALESCE_SECONDS", 0.01)
    original_emit = hub.sio.emit
    attempted = []

    async def emit(event, data, **kwargs):
        nonlocal now
        if expire_during_emit:
            now += 8 * 24 * 60 * 60
        await original_emit(event, data, **kwargs)
        attempted.append(event)

    monkeypatch.setattr(hub.sio, "emit", emit)
    job_id = str(uuid4())
    with protected.websocket_connect(WEBSOCKET, headers=UPGRADE) as ws:
        connect_socketio(ws)
        subscribe_logs(ws, job_id)
        if not expire_during_emit:
            now += 8 * 24 * 60 * 60
        protected.portal.call(hub.notify_log, job_id, 0, b"protected log")
        wait_for(lambda: attempted == ["job_log"])
        wait_for(lambda: not hub._sessions)
        assert read_frame(ws) == "41"
        assert not hub._sessions
