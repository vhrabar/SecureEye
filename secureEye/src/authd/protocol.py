"""Framing and validation for the authd IPC protocol (docs/auth-protocol-v1.md, -v2.md)."""

import json
import socket
import struct
import time
from dataclasses import dataclass

PROTO_VERSION = 1
MAX_PAYLOAD = 4096
DEFAULT_DEADLINE_MS = 2500

# v2: management requests from the GUI
MANAGE_VERSION = 2
# frame events carry a JPEG preview, so the daemon may send bigger frames than it accepts
MAX_EVENT_PAYLOAD = 64 * 1024
MANAGE_TYPES = frozenset({"models_list", "models_remove", "models_clear", "enroll", "test"})
DEFAULT_TEST_DURATION_MS = 15000


class ProtocolError(ValueError):
    pass


@dataclass
class AuthRequest:
    id: str
    username: str
    service: str
    tty: str
    rhost: str
    deadline_ms: int


def read_exact(conn: socket.socket, size: int, deadline: float | None = None) -> bytes:
    """
    Read a fixed-size chunk from the client.
    :param conn: the client connection
    :param size: number of bytes to read
    :param deadline: optional time.monotonic() value by which all bytes must have arrived
    :return: the read bytes
    :raises ConnectionError: if the peer closed the connection before sending all data
    :raises TimeoutError: if the deadline passes first
    """
    data = bytearray()
    while len(data) < size:
        if deadline is not None:
            # per-recv timeouts alone would let a client trickle one byte at a time forever
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("read deadline exceeded")
            conn.settimeout(remaining)
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise ConnectionError("peer closed connection")
        data.extend(chunk)
    return bytes(data)


def read_frame(conn: socket.socket, deadline: float | None = None) -> dict:
    """
    Read input frame from the client.
    :param conn: the client connection
    :param deadline: optional time.monotonic() value by which the whole frame must have arrived
    :return: the parsed payload as a dict
    :raises ProtocolError: if the frame is invalid
    :raises TimeoutError: if the deadline passes first
    """
    header = read_exact(conn, 4, deadline)
    (length,) = struct.unpack("!I", header)
    if length < 1 or length > MAX_PAYLOAD:
        raise ProtocolError("invalid frame length")

    body = read_exact(conn, length, deadline)
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise ProtocolError("invalid utf8/json") from exc

    if not isinstance(payload, dict):
        raise ProtocolError("payload must be object")
    return payload


def write_frame(conn: socket.socket, payload: dict, max_payload: int = MAX_PAYLOAD) -> None:
    """
    Send a framed payload to the client.
    :param conn: the client connection
    :param payload: the response payload
    :param max_payload: largest encoded payload allowed
    :return: None
    :raises ProtocolError: if the encoded payload exceeds max_payload
    """
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(data) > max_payload:
        raise ProtocolError("response payload too large")
    conn.sendall(struct.pack("!I", len(data)) + data)


def validate_auth_request(payload: dict) -> AuthRequest:
    """
    Validate the payload of an incoming auth request.
    :param payload: the payload to validate
    :return: the validated payload as an AuthRequest object
    :raises ProtocolError: if the payload is invalid
    """

    # validate header
    if payload.get("v") != PROTO_VERSION:
        raise ProtocolError("unsupported protocol version")
    if payload.get("type") != "auth_request":
        raise ProtocolError("invalid message type")

    # Protocol v1 uses request_id; keep `id` as legacy fallback.
    request_id = str(payload.get("request_id", payload.get("id", "")))
    username = str(payload.get("username", ""))
    service = str(payload.get("service", ""))
    tty = str(payload.get("tty", ""))
    rhost = str(payload.get("rhost", ""))
    try:
        deadline_ms = int(payload.get("deadline_ms", DEFAULT_DEADLINE_MS))
    except (TypeError, ValueError) as exc:
        raise ProtocolError("invalid deadline_ms") from exc

    # validate body content
    if not (1 <= len(request_id) <= 64):
        raise ProtocolError("invalid id")
    if not (1 <= len(username) <= 64):
        raise ProtocolError("invalid username")
    if len(service) > 64 or len(tty) > 128 or len(rhost) > 256:
        raise ProtocolError("invalid metadata lengths")
    if not (100 <= deadline_ms <= 30000):
        raise ProtocolError("invalid deadline_ms")

    return AuthRequest(
        id=request_id,
        username=username,
        service=service,
        tty=tty,
        rhost=rhost,
        deadline_ms=deadline_ms,
    )


@dataclass
class ManageRequest:
    id: str
    type: str
    username: str
    # models_remove
    model: int | None = None
    # enroll
    label: str = ""
    replace: bool = False
    # enroll, test
    preview: bool = False
    # test
    duration_ms: int = DEFAULT_TEST_DURATION_MS


def validate_manage_request(payload: dict) -> ManageRequest:  # noqa: C901
    """
    Validate the payload of an incoming v2 management request.
    :param payload: the payload to validate
    :return: the validated payload as a ManageRequest object
    :raises ProtocolError: if the payload is invalid
    """
    if payload.get("v") != MANAGE_VERSION:
        raise ProtocolError("unsupported protocol version")
    kind = payload.get("type")
    if kind not in MANAGE_TYPES:
        raise ProtocolError("invalid message type")

    request_id = payload.get("request_id")
    username = payload.get("username")
    if not isinstance(request_id, str) or not (1 <= len(request_id) <= 64):
        raise ProtocolError("invalid request_id")
    if not isinstance(username, str) or not (1 <= len(username) <= 64):
        raise ProtocolError("invalid username")

    req = ManageRequest(id=request_id, type=kind, username=username)

    if kind == "models_remove":
        model = payload.get("model")
        # bool is an int subclass; reject it explicitly
        if not isinstance(model, int) or isinstance(model, bool) or model < 0:
            raise ProtocolError("invalid model")
        req.model = model

    if kind in ("enroll", "test"):
        req.preview = _flag(payload, "preview")

    if kind == "enroll":
        label = payload.get("label")
        if not isinstance(label, str) or not (1 <= len(label) <= 64):
            raise ProtocolError("invalid label")
        req.label = label
        req.replace = _flag(payload, "replace")

    if kind == "test":
        duration_ms = payload.get("duration_ms", DEFAULT_TEST_DURATION_MS)
        if (
            not isinstance(duration_ms, int)
            or isinstance(duration_ms, bool)
            or not (1000 <= duration_ms <= 60000)
        ):
            raise ProtocolError("invalid duration_ms")
        req.duration_ms = duration_ms

    return req


def _flag(payload: dict, key: str) -> bool:
    value = payload.get(key, False)
    if not isinstance(value, bool):
        raise ProtocolError(f"invalid {key}")
    return value
