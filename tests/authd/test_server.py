import os
import pwd
import socket
import stat
import struct
import sys
import threading
import time
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "secureEye" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from auth import ExitCode  # noqa: E402
from authd import main as authd_main  # noqa: E402
from authd.camera import CameraArbiter  # noqa: E402
from authd.protocol import read_frame, write_frame  # noqa: E402


ME = pwd.getpwuid(os.getuid()).pw_name


class FakeSession:
    """Stands in for AuthSession; tracks how many sessions hold the camera at once."""

    hold_s = 0.0
    active = 0
    max_active = 0
    lock = threading.Lock()

    def __init__(self):
        self.cancelled = threading.Event()

    def run(self, user):
        FakeSession.runs.append(user)
        with FakeSession.lock:
            FakeSession.active += 1
            FakeSession.max_active = max(FakeSession.max_active, FakeSession.active)
        try:
            # ignores cancel on purpose: models a camera that is slow to let go
            time.sleep(FakeSession.hold_s)
            return int(ExitCode.SUCCESS)
        finally:
            with FakeSession.lock:
                FakeSession.active -= 1

    def cancel(self):
        self.cancelled.set()


@pytest.fixture
def server(monkeypatch, tmp_path):
    FakeSession.hold_s = 0.0
    FakeSession.active = 0
    FakeSession.max_active = 0
    FakeSession.runs = []
    monkeypatch.setattr(authd_main, "AuthSession", FakeSession)
    monkeypatch.setattr(authd_main, "_camera", CameraArbiter())
    monkeypatch.setattr(authd_main, "READ_TIMEOUT_S", 0.3)

    path = str(tmp_path / "authd.sock")
    srv = authd_main._prepare_socket(path)
    stop = threading.Event()
    thread = threading.Thread(target=authd_main.serve, args=(srv, stop), daemon=True)
    thread.start()
    yield path
    stop.set()
    thread.join(5)
    srv.close()


def _connect(path: str) -> socket.socket:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(path)
    return sock


def _auth(path: str, deadline_ms: int = 2500, username: str = ME) -> dict:
    with _connect(path) as sock:
        write_frame(
            sock,
            {
                "v": 1,
                "type": "auth_request",
                "request_id": "r1",
                "username": username,
                "deadline_ms": deadline_ms,
            },
        )
        return read_frame(sock)


def test_request_succeeds(server):
    resp = _auth(server)
    assert resp["result_code"] == 0
    assert resp["request_id"] == "r1"


def test_silent_client_does_not_block_others(server):
    with _connect(server):
        start = time.monotonic()
        assert _auth(server)["result_code"] == 0
        assert time.monotonic() - start < 0.3


def test_silent_client_is_dropped_after_read_timeout(server):
    with _connect(server) as silent:
        start = time.monotonic()
        resp = read_frame(silent)
    assert resp["result_code"] == authd_main.INTERNAL_ERROR_CODE
    assert 0.2 < time.monotonic() - start < 2


def test_trickling_client_is_cut_off_at_deadline(server):
    with _connect(server) as sock:
        start = time.monotonic()
        sock.sendall(struct.pack("!I", 100))
        try:
            for _ in range(10):
                sock.sendall(b" ")
                time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError):
            pass
        resp = read_frame(sock)
    assert resp["result_code"] == authd_main.INTERNAL_ERROR_CODE
    assert time.monotonic() - start < 1.5


def test_connections_over_cap_are_closed(monkeypatch, server):
    monkeypatch.setattr(authd_main, "MAX_CLIENTS", 1)
    # MAX_CLIENTS is read when serve() starts, so restart the loop against a fresh socket
    path = server + ".capped"
    srv = authd_main._prepare_socket(path)
    stop = threading.Event()
    thread = threading.Thread(target=authd_main.serve, args=(srv, stop), daemon=True)
    thread.start()
    try:
        with _connect(path):
            time.sleep(0.05)
            with _connect(path) as extra:
                assert extra.recv(1) == b""
    finally:
        stop.set()
        thread.join(5)
        srv.close()


def test_sessions_never_hold_camera_concurrently(server):
    FakeSession.hold_s = 0.2
    results = []
    threads = [threading.Thread(target=lambda: results.append(_auth(server))) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
    assert [r["result_code"] for r in results] == [0, 0, 0]
    assert FakeSession.max_active == 1


def test_waiting_for_camera_respects_deadline(server):
    FakeSession.hold_s = 1.0
    first = threading.Thread(target=_auth, args=(server,))
    first.start()
    time.sleep(0.1)
    start = time.monotonic()
    # 800ms deadline leaves the minimum 100ms worker budget
    resp = _auth(server, deadline_ms=800)
    elapsed = time.monotonic() - start
    first.join(5)
    assert resp["result_code"] == int(ExitCode.TIMEOUT_REACHED)
    assert elapsed < 0.5


def test_timed_out_session_keeps_camera_until_it_finishes(server):
    FakeSession.hold_s = 0.5
    assert _auth(server, deadline_ms=800)["result_code"] == int(ExitCode.TIMEOUT_REACHED)
    # the timed-out worker is still running; the next session must wait for it, not overlap
    assert _auth(server)["result_code"] == 0
    assert FakeSession.max_active == 1


def test_socket_is_open_to_every_user(server):
    assert stat.S_IMODE(os.stat(server).st_mode) == 0o666


@pytest.mark.skipif(os.getuid() == 0, reason="root may authenticate anyone")
def test_user_cannot_authenticate_someone_else(server):
    resp = _auth(server, username="root")
    assert resp["result_code"] == authd_main.INTERNAL_ERROR_CODE
    assert resp["detail"] == "forbidden"
    assert resp["request_id"] == "r1"
    assert FakeSession.runs == []


def test_user_authenticates_themselves(server):
    assert _auth(server)["result_code"] == 0
    assert FakeSession.runs == [ME]


def test_root_may_authenticate_anyone():
    assert authd_main._may_authenticate(0, "nobody-by-this-name")


def test_unknown_user_is_refused():
    assert not authd_main._may_authenticate(1000, "nobody-by-this-name")


def test_peer_uid_is_the_connecting_process():
    left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    with left, right:
        assert authd_main._peer_uid(left) == os.getuid()
