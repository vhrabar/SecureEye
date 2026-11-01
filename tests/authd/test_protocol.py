import json
import socket
import struct
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "secureEye" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from authd.protocol import (  # noqa: E402
    MAX_EVENT_PAYLOAD,
    MAX_PAYLOAD,
    ProtocolError,
    read_frame,
    validate_auth_request,
    validate_manage_request,
    write_frame,
)


@pytest.fixture
def pair():
    a, b = socket.socketpair()
    a.settimeout(1.0)
    b.settimeout(1.0)
    yield a, b
    a.close()
    b.close()


def _send_raw(sock: socket.socket, body: bytes, length: int | None = None) -> None:
    sock.sendall(struct.pack("!I", len(body) if length is None else length) + body)


def _request(**overrides) -> dict:
    req = {
        "v": 1,
        "type": "auth_request",
        "request_id": "abc123",
        "username": "alice",
        "service": "sudo",
        "tty": "/dev/pts/2",
        "rhost": "",
        "deadline_ms": 2500,
    }
    req.update(overrides)
    return req


def test_round_trip(pair):
    a, b = pair
    write_frame(a, _request())
    assert read_frame(b) == _request()


def test_write_frame_uses_big_endian_length_prefix(pair):
    a, b = pair
    write_frame(a, {"k": "v"})
    body = json.dumps({"k": "v"}, separators=(",", ":")).encode()
    assert b.recv(64) == struct.pack(">I", len(body)) + body


@pytest.mark.parametrize("length", [0, MAX_PAYLOAD + 1])
def test_read_frame_rejects_bad_length(pair, length):
    a, b = pair
    _send_raw(a, b"", length=length)
    with pytest.raises(ProtocolError, match="invalid frame length"):
        read_frame(b)


def test_read_frame_accepts_max_length(pair):
    a, b = pair
    body = json.dumps({"x": "y" * (MAX_PAYLOAD - 9)}).encode()
    assert len(body) == MAX_PAYLOAD
    _send_raw(a, body)
    assert read_frame(b)["x"] == "y" * (MAX_PAYLOAD - 9)


@pytest.mark.parametrize("body", [b"\xff\xfe", b"{not json", b""])
def test_read_frame_rejects_invalid_body(pair, body):
    a, b = pair
    _send_raw(a, body or b" ")
    with pytest.raises(ProtocolError, match="invalid utf8/json"):
        read_frame(b)


@pytest.mark.parametrize("body", [b"[]", b"1", b'"s"', b"null"])
def test_read_frame_rejects_non_object(pair, body):
    a, b = pair
    _send_raw(a, body)
    with pytest.raises(ProtocolError, match="payload must be object"):
        read_frame(b)


def test_read_frame_raises_on_truncated_body(pair):
    a, b = pair
    _send_raw(a, b'{"a":', length=20)
    a.shutdown(socket.SHUT_WR)
    with pytest.raises(ConnectionError):
        read_frame(b)


def test_write_frame_rejects_oversized_payload(pair):
    a, _ = pair
    with pytest.raises(ProtocolError, match="too large"):
        write_frame(a, {"x": "y" * MAX_PAYLOAD})


def test_validate_returns_request():
    req = validate_auth_request(_request())
    assert (req.id, req.username, req.service, req.tty, req.rhost, req.deadline_ms) == (
        "abc123",
        "alice",
        "sudo",
        "/dev/pts/2",
        "",
        2500,
    )


def test_validate_accepts_legacy_id_and_default_deadline():
    payload = _request()
    del payload["request_id"]
    del payload["deadline_ms"]
    payload["id"] = "legacy"
    req = validate_auth_request(payload)
    assert req.id == "legacy"
    assert req.deadline_ms == 2500


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"v": 2}, "unsupported protocol version"),
        ({"v": "1"}, "unsupported protocol version"),
        ({"type": "auth_response"}, "invalid message type"),
        ({"request_id": ""}, "invalid id"),
        ({"request_id": "x" * 65}, "invalid id"),
        ({"username": ""}, "invalid username"),
        ({"username": "u" * 65}, "invalid username"),
        ({"service": "s" * 65}, "invalid metadata lengths"),
        ({"tty": "t" * 129}, "invalid metadata lengths"),
        ({"rhost": "r" * 257}, "invalid metadata lengths"),
        ({"deadline_ms": 99}, "invalid deadline_ms"),
        ({"deadline_ms": 30001}, "invalid deadline_ms"),
        ({"deadline_ms": "soon"}, "invalid deadline_ms"),
        ({"deadline_ms": None}, "invalid deadline_ms"),
    ],
)
def test_validate_rejects(overrides, message):
    with pytest.raises(ProtocolError, match=message):
        validate_auth_request(_request(**overrides))


def test_write_frame_allows_bigger_events_when_asked(pair):
    a, b = pair
    payload = {"x": "y" * (MAX_PAYLOAD * 2)}
    write_frame(a, payload, max_payload=MAX_EVENT_PAYLOAD)
    b.settimeout(1.0)
    header = b.recv(4)
    assert struct.unpack("!I", header)[0] > MAX_PAYLOAD


# v2 management requests


def _manage(**overrides):
    payload = {"v": 2, "type": "models_list", "request_id": "r1", "username": "alice"}
    payload.update(overrides)
    return payload


def test_manage_defaults():
    req = validate_manage_request(_manage(type="test"))
    assert (req.type, req.username, req.preview, req.duration_ms) == ("test", "alice", False, 15000)


def test_manage_enroll_fields():
    req = validate_manage_request(_manage(type="enroll", label="desk", replace=True, preview=True))
    assert (req.label, req.replace, req.preview) == ("desk", True, True)


def test_manage_remove_takes_a_model_id():
    assert validate_manage_request(_manage(type="models_remove", model=3)).model == 3


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"v": 1}, "unsupported protocol version"),
        ({"type": "auth_request"}, "invalid message type"),
        ({"type": "cancel"}, "invalid message type"),
        ({"request_id": ""}, "invalid request_id"),
        ({"request_id": 5}, "invalid request_id"),
        ({"username": "u" * 65}, "invalid username"),
        ({"username": None}, "invalid username"),
        ({"type": "models_remove"}, "invalid model"),
        ({"type": "models_remove", "model": -1}, "invalid model"),
        ({"type": "models_remove", "model": "0"}, "invalid model"),
        ({"type": "models_remove", "model": True}, "invalid model"),
        ({"type": "enroll"}, "invalid label"),
        ({"type": "enroll", "label": ""}, "invalid label"),
        ({"type": "enroll", "label": "l" * 65}, "invalid label"),
        ({"type": "enroll", "label": "x", "replace": "yes"}, "invalid replace"),
        ({"type": "test", "preview": 1}, "invalid preview"),
        ({"type": "test", "duration_ms": 999}, "invalid duration_ms"),
        ({"type": "test", "duration_ms": 60001}, "invalid duration_ms"),
        ({"type": "test", "duration_ms": 1.5}, "invalid duration_ms"),
    ],
)
def test_manage_rejects(overrides, message):
    with pytest.raises(ProtocolError, match=message):
        validate_manage_request(_manage(**overrides))
