import configparser
import os
import signal
import socket
import sys
import syslog
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

import paths_factory
from auth import ExitCode, AuthSession
from auth.detector_factory import create_detector
from authd.protocol import PROTO_VERSION, read_frame, validate_auth_request, write_frame

SOCKET_PATH = os.environ.get("SECUREEYE_AUTHD_SOCKET", "/run/secureeye/authd.sock")
INTERNAL_ERROR_CODE = 99

# time between the daemon's own worker deadline and the client's transport deadline
RESPONSE_MARGIN_MS = 700


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


def _handle_client(conn: socket.socket, peer: str) -> None:
    """
    Handle an incoming client connection.
    :param conn: the client connection
    :param peer: the peer address
    :return: None
    """
    try:
        # load & validate payload
        payload = read_frame(conn)
        req = validate_auth_request(payload)

        worker_timeout = max(0.1, (req.deadline_ms - RESPONSE_MARGIN_MS) / 1000.0)

        # Run auth in a worker and do not block daemon shutdown waiting for timed-out requests.
        session = AuthSession()
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="secureeye-auth")
        try:
            future = pool.submit(session.run, req.username)
            try:
                code = int(future.result(timeout=worker_timeout))
            except FutureTimeoutError:
                session.cancel()
                future.cancel()
                code = int(ExitCode.TIMEOUT_REACHED)
            except BaseException as exc:
                # Legacy code paths may call sys.exit(code); never let that kill authd.
                if isinstance(exc, SystemExit) and isinstance(exc.code, int):
                    code = int(exc.code)
                else:
                    code = INTERNAL_ERROR_CODE
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        # send response
        write_frame(
            conn,
            {
                "v": PROTO_VERSION,
                "type": "auth_response",
                "request_id": req.id,
                "result_code": code,
                "detail": "ok" if code == 0 else "auth_failed",
            },
        )
    # fail-closed connection
    except BaseException:
        try:
            write_frame(
                conn,
                {
                    "v": PROTO_VERSION,
                    "type": "auth_response",
                    "request_id": None,
                    "result_code": INTERNAL_ERROR_CODE,
                    "detail": "auth_failed",
                },
            )
        except Exception:
            pass


def _warm_detector() -> None:
    """
    Build (and cache) the configured detector before serving requests.
    """
    try:
        config = configparser.ConfigParser()
        config.read(paths_factory.config_file_path())
        create_detector(config)
    except Exception as exc:
        syslog.syslog(
            syslog.LOG_WARNING,
            f"secureeye-authd: detector warmup skipped: {exc}",
        )


def main() -> int:
    stop = threading.Event()

    # setup signal handling
    signal.signal(signal.SIGINT, lambda signum, _frame: stop.set())
    signal.signal(signal.SIGTERM, lambda signum, _frame: stop.set())

    _warm_detector()

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
