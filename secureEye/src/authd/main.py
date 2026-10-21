import configparser
import os
import pwd
import signal
import socket
import struct
import sys
import syslog
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

import paths_factory
from auth import ExitCode, AuthSession
from auth.detector_factory import create_pipeline
from authd.camera import CameraArbiter, CameraUse
from authd.protocol import PROTO_VERSION, read_frame, validate_auth_request, write_frame

SOCKET_PATH = os.environ.get("SECUREEYE_AUTHD_SOCKET", "/run/secureeye/authd.sock")
INTERNAL_ERROR_CODE = 99

# time between the daemon's own worker deadline and the client's transport deadline
RESPONSE_MARGIN_MS = 700

# a client must deliver its whole request frame within this window
READ_TIMEOUT_S = 1.0
WRITE_TIMEOUT_S = 1.0

# concurrent connections; extra clients are closed immediately (PAM fails closed)
MAX_CLIENTS = 8

# how long shutdown waits for in-flight handlers before exiting
SHUTDOWN_GRACE_S = 2.0

# The camera can only be held by one session. It is released by the worker that ran the
# session, not by the handler, so a timed-out session keeps it until it has really let go.
_camera = CameraArbiter()


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
    # anyone may connect: screen lockers run PAM as the user, not as root. What a
    # client may ask for is checked per request against its SO_PEERCRED uid.
    os.chmod(socket_path, 0o666)
    sock.listen(64)
    return sock


def _peer_uid(conn: socket.socket) -> int:
    """
    Return the uid of the process on the other end of a unix socket.
    :param conn: the client connection
    :return: the uid the kernel recorded when the client connected
    """
    creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    _pid, uid, _gid = struct.unpack("3i", creds)
    return uid


def _may_authenticate(peer_uid: int, username: str) -> bool:
    """
    Root may authenticate anyone; everyone else only themselves.
    :param peer_uid: the client's uid
    :param username: the user the client wants authenticated
    :return: whether the request is allowed
    """
    if peer_uid == 0:
        return True
    try:
        return pwd.getpwnam(username).pw_uid == peer_uid
    except KeyError:
        return False


def _handle_client(conn: socket.socket) -> None:
    """
    Handle an incoming client connection.
    :param conn: the client connection
    :return: None
    """
    try:
        peer_uid = _peer_uid(conn)

        # load & validate payload
        payload = read_frame(conn, time.monotonic() + READ_TIMEOUT_S)
        req = validate_auth_request(payload)
        conn.settimeout(WRITE_TIMEOUT_S)

        if not _may_authenticate(peer_uid, req.username):
            syslog.syslog(
                syslog.LOG_WARNING,
                f"secureeye-authd: uid {peer_uid} may not authenticate {req.username!r}",
            )
            write_frame(
                conn,
                {
                    "v": PROTO_VERSION,
                    "type": "auth_response",
                    "request_id": req.id,
                    "result_code": INTERNAL_ERROR_CODE,
                    "detail": "forbidden",
                },
            )
            return

        worker_deadline = time.monotonic() + max(
            0.1, (req.deadline_ms - RESPONSE_MARGIN_MS) / 1000.0
        )
        code = _run_session(req.username, worker_deadline)

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


def _run_session(username: str, deadline: float) -> int:
    """
    Run one auth session while holding the camera, bounded by deadline.
    :param username: the user to authenticate
    :param deadline: time.monotonic() value by which a result code must be returned
    :return: the session's exit code
    """
    session = AuthSession()
    if not _camera.acquire(CameraUse.AUTH, session, deadline - time.monotonic()):
        return int(ExitCode.TIMEOUT_REACHED)

    # Run auth in a worker and do not block daemon shutdown waiting for timed-out requests.
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="secureeye-auth")
    try:
        future = pool.submit(session.run, username)
    except BaseException:
        _camera.release(session)
        pool.shutdown(wait=False)
        raise
    future.add_done_callback(lambda _future: _camera.release(session))
    try:
        return int(future.result(timeout=max(0.0, deadline - time.monotonic())))
    except FutureTimeoutError:
        session.cancel()
        future.cancel()
        return int(ExitCode.TIMEOUT_REACHED)
    except BaseException as exc:
        # Legacy code paths may call sys.exit(code); never let that kill authd.
        if isinstance(exc, SystemExit) and isinstance(exc.code, int):
            return int(exc.code)
        return INTERNAL_ERROR_CODE
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _serve_client(conn: socket.socket, slots: threading.BoundedSemaphore) -> None:
    """
    Handle one connection on its own thread, then free its slot.
    :param conn: the client connection
    :param slots: semaphore bounding concurrent connections
    :return: None
    """
    try:
        with conn:
            _handle_client(conn)
    finally:
        slots.release()


def serve(srv: socket.socket, stop: threading.Event) -> None:
    """
    Accept connections until stop is set, handling each on its own thread.
    :param srv: a bound, listening socket
    :param stop: event that ends the accept loop
    :return: None
    """
    slots = threading.BoundedSemaphore(MAX_CLIENTS)
    workers: set[threading.Thread] = set()
    srv.settimeout(0.5)
    try:
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if not slots.acquire(blocking=False):
                conn.close()
                continue
            worker = threading.Thread(
                target=_serve_client,
                args=(conn, slots),
                name="secureeye-client",
                daemon=True,
            )
            worker.start()
            workers = {w for w in workers if w.is_alive()}
            workers.add(worker)
    finally:
        grace_end = time.monotonic() + SHUTDOWN_GRACE_S
        for worker in workers:
            worker.join(max(0.0, grace_end - time.monotonic()))


def _warm_detector() -> None:
    """
    Build (and cache) the configured detector before serving requests.
    """
    try:
        config = configparser.ConfigParser()
        config.read(paths_factory.config_file_path())
        create_pipeline(config)
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
        serve(srv, stop)
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
