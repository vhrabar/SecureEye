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
    MAX_PAYLOAD,
    ProtocolError,
    read_frame,
    validate_auth_request,
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
