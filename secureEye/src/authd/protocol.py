"""Framing and validation for the authd IPC protocol (docs/auth-protocol-v1.md)."""

import json
import socket
import struct
from dataclasses import dataclass

PROTO_VERSION = 1
MAX_PAYLOAD = 4096
DEFAULT_DEADLINE_MS = 2500


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


def read_exact(conn: socket.socket, size: int) -> bytes:
    """
    Read a fixed-size chunk from the client.
    :param conn: the client connection
    :param size: number of bytes to read
    :return: the read bytes
    :raises ConnectionError: if the peer closed the connection before sending all data
    """
    data = bytearray()
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise ConnectionError("peer closed connection")
        data.extend(chunk)
    return bytes(data)


def read_frame(conn: socket.socket) -> dict:
    """
    Read input frame from the client.
    :param conn: the client connection
    :return: the parsed payload as a dict
    :raises ProtocolError: if the frame is invalid
    """
    header = read_exact(conn, 4)
    (length,) = struct.unpack("!I", header)
    if length < 1 or length > MAX_PAYLOAD:
        raise ProtocolError("invalid frame length")

    body = read_exact(conn, length)
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise ProtocolError("invalid utf8/json") from exc

    if not isinstance(payload, dict):
        raise ProtocolError("payload must be object")
    return payload


def write_frame(conn: socket.socket, payload: dict) -> None:
    """
    Send a framed payload to the client.
    :param conn: the client connection
    :param payload: the response payload
    :return: None
    :raises ProtocolError: if the encoded payload exceeds MAX_PAYLOAD
    """
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(data) > MAX_PAYLOAD:
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
