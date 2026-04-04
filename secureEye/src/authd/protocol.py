import json
import struct
from typing import Callable

MAX_FRAME = 64 * 1024


class ProtocolError(Exception):
    pass


def encode_frame(obj: dict) -> bytes:
    """
    Encode a dict as a framed JSON payload.
    :param obj: the dict to encode
    :return: encoded bytes
    """
    payload = json.dumps(obj, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(payload) > MAX_FRAME:
        raise ProtocolError("payload too large")
    return struct.pack(">I", len(payload)) + payload


def decode_frame(read_exact: Callable[[int], bytes]) -> dict:
    """
    Decode a framed JSON payload.
    :param read_exact:
    :return: decoded dict
    """
    # read_exact(n) must return exactly n bytes or raise
    header = read_exact(4)
    (size,) = struct.unpack(">I", header)
    if size <= 0 or size > MAX_FRAME:
        raise ProtocolError("invalid frame size")
    payload = read_exact(size)
    try:
        obj = json.loads(payload.decode("utf-8"))
    except Exception as e:
        raise ProtocolError("invalid json") from e
    return obj


def validate_auth_request(msg: dict) -> None:
    """
    Validate an auth_request message.
    :param msg: message to validate
    :return: None
    """
    if msg.get("version") != 1:
        raise ProtocolError("unsupported version")
    if msg.get("type") != "auth_request":
        raise ProtocolError("invalid type")
    for k in ("request_id", "username"):
        if not isinstance(msg.get(k), str) or not msg[k]:
            raise ProtocolError(f"invalid {k}")
