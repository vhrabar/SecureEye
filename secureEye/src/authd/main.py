import json
import os
import signal
import socket
import struct
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from auth import ExitCode, AuthSession

SOCKET_PATH = os.environ.get("SECUREEYE_AUTHD_SOCKET", "/run/secureeye/authd.sock")
PROTO_VERSION = 1
MAX_PAYLOAD = 4096
DEFAULT_DEADLINE_MS = 2500
INTERNAL_ERROR_CODE = 99


@dataclass
class AuthRequest:
    id: str
    username: str
    service: str
    tty: str
    rhost: str
    deadline_ms: int


def _prepare_socket(socket_path: str) -> socket.socket:
    """
    Preapre a socket for listening.
    :param socket_path: path to the socket file, e.g. /run/secureeye/authd.sock
    :return: the prepared socket object, already bound and listening
    """
    os.makedirs(os.path.dirname(socket_path), exist_ok=True)
    try:
        os.unlink(socket_path)
    except FileNotFoundError:
        pass
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(socket_path)
    os.chmod(socket_path, 0o660)
    sock.listen(64)
    return sock


def _read_socket(conn: socket.socket, size: int) -> bytes:
    """
    Read a fixed-size chunk from the client.
    :param conn: the client connection
    :size: number of bytes to read
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


def _read_frame(conn: socket.socket) -> dict:
    """
    Read input frame from the client.
    :param conn: the client connection
    :return: the parsed payload as a dict
    :raises ValueError: if the frame is invalid
    """
    header = _read_socket(conn, 4)
    (length,) = struct.unpack("!I", header)
    if length < 1 or length > MAX_PAYLOAD:
        raise ValueError("invalid frame length")

    body = _read_socket(conn, length)
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid utf8/json") from exc

    if not isinstance(payload, dict):
        raise ValueError("payload must be object")
    return payload



def _validate_payload(payload: dict) -> AuthRequest:
    """
    Validate the payload of an incoming request.
    :param payload: the payload to validate
    :return: the validated payload as an AuthRequest object
    :raises ValueError: if the payload is invalid
    """

    # validate header
    if payload.get("v") != PROTO_VERSION:
        raise ValueError("unsupported protocol version")
    if payload.get("type") != "auth_request":
        raise ValueError("invalid message type")

    # extractbody
    request_id = str(payload.get("id", ""))
    username = str(payload.get("username", ""))
    service = str(payload.get("service", ""))
    tty = str(payload.get("tty", ""))
    rhost = str(payload.get("rhost", ""))
    deadline_ms = int(payload.get("deadline_ms", DEFAULT_DEADLINE_MS))

    # validate body content
    if not (1 <= len(request_id) <= 64):
        raise ValueError("invalid id")
    if not (1 <= len(username) <= 64):
        raise ValueError("invalid username")
    if len(service) > 64 or len(tty) > 128 or len(rhost) > 256:
        raise ValueError("invalid metadata lengths")
    if not (100 <= deadline_ms <= 30000):
        raise ValueError("invalid deadline_ms")

    # return validated payload
    return AuthRequest(
        id=request_id,
        username=username,
        service=service,
        tty=tty,
        rhost=rhost,
        deadline_ms=deadline_ms,
    )


def _write_frame(conn: socket.socket, payload: dict) -> None:
    """
    Send response to the client.
    :param conn: the client connection
    :param payload: the response payload
    :return: None
    """
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(data) > MAX_PAYLOAD:
        raise ValueError("response payload too large")
    conn.sendall(struct.pack("!I", len(data)) + data)


def _handle_client(conn: socket.socket, peer: str) -> None:
    """
    Handle an incoming client connection.
    :param conn: the client connection
    :param peer: the peer address
    :return: None
    """
    try:
        # load & validate payload
        payload = _read_frame(conn)
        req = _validate_payload(payload)

        worker_timeout = max(0.1, (req.deadline_ms - 300) / 1000.0)

        # run auth
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lambda username: int(AuthSession().run(username)), req.username)
            try:
                code = future.result(timeout=worker_timeout)
            except TimeoutError:
                code = int(ExitCode.TIMEOUT_REACHED)
            except Exception:
                code = INTERNAL_ERROR_CODE

        # send response
        _write_frame(conn,
                     {
                         "v": PROTO_VERSION,
                         "type": "auth_response",
                         "request_id": req.id,
                         "result_code": code,
                         "detail": "ok" if code == 0 else "auth_failed",
                     }
                     )
    # fail-closed connection
    except Exception as e:
        try:
            _write_frame(conn,
                         {
                             "v": PROTO_VERSION,
                             "type": "auth_response",
                             "request_id": None,
                             "result_code": INTERNAL_ERROR_CODE,
                             "detail": "ok" if code == 0 else "auth_failed",
                         }
                         )
        except Exception:
            pass


def main() -> int:
    stop = threading.Event()

    # setup signal handling
    signal.signal(signal.SIGINT, lambda signum, _frame: stop.set())
    signal.signal(signal.SIGTERM, lambda signum, _frame: stop.set())

    # setup socket
    srv = _prepare_socket(SOCKET_PATH)

    # start listening
    try:
        while not stop.is_set():
            srv.settimeout(0.5)
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                _handle_client(conn, "local")
    # handle failure (fc)
    finally:
        try:
            srv.close()
        finally:
            try:
                os.unlink(SOCKET_PATH)
            except FileNotFoundError:
                pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
