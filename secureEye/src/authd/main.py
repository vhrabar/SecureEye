import os
import signal
import socket
import sys
import threading
from dataclasses import dataclass

SOCKET_PATH = os.environ.get("SECUREEYE_AUTHD_SOCKET", "/run/secureeye/authd.sock")
PROTO_VERSION = 1
MAX_PAYLOAD = 4096
DEFAULT_DEADLINE_MS = 2500
INTERNAL_ERROR_CODE = 99


@dataclass
class AuthRequest:
    request_id: str
    username: str
    service: str
    tty: str
    rhost: str
    deadline_ms: int


def _prepare_socket(socket_path: str) -> socket.socket:
    raise NotImplementedError


def _handle_client(conn: socket.socket, peer: str) -> None:
    raise NotImplementedError


def main() -> int:
    stop = threading.Event()

    # setup signal handling
    signal.signal(signal.SIGINT, lambda signum, _frame: stop.set())

    signal.signal(signal.SIGTERM, lambda signum, _frame: stop.set())

    srv = _prepare_socket(SOCKET_PATH)
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
