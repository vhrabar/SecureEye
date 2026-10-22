"""
Management requests from the GUI
"""

import base64
import configparser
import select
import socket
import syslog
import threading
import time
from typing import Any

import cv2

import paths_factory
from auth import ExitCode, template_store
from auth.capture import FrameReport, FrameStream
from auth.detector_factory import create_pipeline
from auth.enrollment import EnrollOutcome, EnrollResult, EnrollSession
from auth.interfaces import Frame
from auth.recognition_probe import ProbeOutcome, RecognitionProbe
from authd.access import may_act_for
from authd.camera import CameraArbiter, CameraUse
from authd.protocol import (
    MANAGE_VERSION,
    MAX_EVENT_PAYLOAD,
    ManageRequest,
    ProtocolError,
    read_frame,
    validate_manage_request,
    write_frame,
)

# how long a camera session waits for the camera (or another model write) before "busy"
CAMERA_WAIT_S = 5.0
MODELS_WAIT_S = 5.0

# previews: at most one every PREVIEW_INTERVAL_S, no wider than PREVIEW_MAX_WIDTH
PREVIEW_INTERVAL_S = 0.1
PREVIEW_MAX_WIDTH = 320
PREVIEW_JPEG_QUALITY = 70

# how often the watcher checks for a cancel message or a vanished client
WATCH_POLL_S = 0.2

# builds the camera for sessions; tests swap in a fake one
stream_factory: Any = FrameStream

# One writer at a time for model files: remove/clear must not race an enrollment's
# read-modify-write of the same file.
_models_lock = threading.Lock()


def handle(conn: socket.socket, uid: int, payload: dict, camera: CameraArbiter) -> None:
    """
    Answer one v2 request. Never raises; every failure becomes a ``result`` message.
    :param conn: the client connection, with its write timeout already set
    :param uid: the client's SO_PEERCRED uid
    :param payload: the request frame
    :param camera: the daemon's camera arbiter
    :return: None
    """
    raw_id = payload.get("request_id")
    request_id = raw_id if isinstance(raw_id, str) and len(raw_id) <= 64 else None
    try:
        req = validate_manage_request(payload)
    except ProtocolError:
        _try_result(conn, request_id, "invalid_request")
        return

    if not may_act_for(uid, req.username):
        syslog.syslog(
            syslog.LOG_WARNING,
            f"secureeye-authd: uid {uid} may not manage {req.username!r}",
        )
        _try_result(conn, req.id, "forbidden")
        return

    try:
        if req.type in ("enroll", "test"):
            _camera_session(conn, req, camera)
        else:
            _models_request(conn, req)
    except SystemExit as exc:
        # VideoCapture still exits with INVALID_DEVICE when the camera can't be opened
        result = "invalid_device" if exc.code == int(ExitCode.INVALID_DEVICE) else "internal_error"
        _try_result(conn, req.id, result)
    except Exception as exc:
        syslog.syslog(syslog.LOG_ERR, f"secureeye-authd: {req.type} failed: {exc!r}")
        _try_result(conn, req.id, "internal_error")


def _models_request(conn: socket.socket, req: ManageRequest) -> None:
    if req.type == "models_list":
        try:
            templates = template_store.load_all(req.username)
        except (template_store.TemplateFileNotFound, template_store.EmptyTemplateStore):
            templates = []
        except template_store.TemplateSchemaError:
            _result(conn, req.id, "model_file_invalid")
            return
        models = [
            {"id": t.id, "label": t.label, "time": t.created, "model_id": t.model_id}
            for t in templates
        ]
        _result(conn, req.id, "success", {"user": req.username, "models": models})
        return

    if not _models_lock.acquire(timeout=MODELS_WAIT_S):
        _result(conn, req.id, "busy")
        return
    try:
        result, data = _change_models(req)
    finally:
        _models_lock.release()
    _result(conn, req.id, result, data)


def _change_models(req: ManageRequest) -> tuple[str, dict | None]:
    try:
        templates = template_store.load_all(req.username)
    except (template_store.TemplateFileNotFound, template_store.EmptyTemplateStore):
        return "no_models", None
    except template_store.TemplateSchemaError:
        if req.type != "models_clear":
            return "model_file_invalid", None
        # clearing is how a user gets rid of an unreadable file
        templates = []

    if req.type == "models_clear":
        template_store.delete(req.username)
        return "success", {"removed": len(templates)}

    target = template_store.find(templates, req.model)
    if target is None:
        return "model_not_found", None
    remaining = [t for t in templates if t is not target]
    if remaining:
        template_store.save(req.username, remaining)
    else:
        template_store.delete(req.username)
    return "success", {"removed": target.id, "remaining": len(remaining)}


class _Holder:
    """What the camera arbiter holds: remembers whether a login took the camera away."""

    def __init__(self, session) -> None:
        self.session = session
        self.preempted = False

    def cancel(self) -> None:
        self.preempted = True
        self.session.cancel()


def _camera_session(conn: socket.socket, req: ManageRequest, camera: CameraArbiter) -> None:
    config = _load_config()
    bundle = create_pipeline(config)
    on_frame = _FrameSender(conn, req)

    if req.type == "enroll":
        session: Any = EnrollSession(
            config, bundle, on_frame=on_frame, stream_factory=stream_factory
        )
        # held for the whole enrollment so a remove cannot interleave with its write
        if not _models_lock.acquire(timeout=MODELS_WAIT_S):
            _result(conn, req.id, "busy")
            return
    else:
        session = RecognitionProbe(
            config,
            bundle,
            on_frame=on_frame,
            stream_factory=stream_factory,
            duration_s=req.duration_ms / 1000,
        )

    holder = _Holder(session)
    done = threading.Event()
    watcher = threading.Thread(
        target=_watch_client, args=(conn, session, done), name="secureeye-watch", daemon=True
    )
    try:
        if not camera.acquire(CameraUse.MANAGE, holder, CAMERA_WAIT_S):
            _result(conn, req.id, "busy")
            return
        try:
            _send(conn, {"type": "started", "request_id": req.id})
            watcher.start()
            if req.type == "enroll":
                outcome = session.run(req.username, req.label, replace=req.replace)
            else:
                outcome = session.run(req.username)
        finally:
            done.set()
            # run() has released the camera by the time it returns
            camera.release(holder)
    finally:
        if req.type == "enroll":
            _models_lock.release()

    watcher.join(WATCH_POLL_S * 2)
    result, data = _session_result(outcome)
    if result == "cancelled" and holder.preempted:
        result = "preempted"
    _result(conn, req.id, result, data)


def _session_result(outcome: EnrollOutcome | ProbeOutcome) -> tuple[str, dict]:
    if isinstance(outcome, ProbeOutcome):
        return outcome.result.value, {
            "frames": outcome.frames,
            "matched_frames": outcome.matched_frames,
            "best_distance": None
            if outcome.best_distance is None
            else round(outcome.best_distance, 3),
        }
    data: dict[str, Any] = {
        "valid_frames": outcome.valid_frames,
        "dark_tries": outcome.dark_tries,
        "avg_darkness": round(outcome.avg_darkness, 1),
    }
    if outcome.result is EnrollResult.SUCCESS and outcome.template is not None:
        data.update(
            model=outcome.template.id,
            label=outcome.template.label,
            model_id=outcome.template.model_id,
        )
    return outcome.result.value, data


class _FrameSender:
    """The sessions' on_frame observer: one ``frame`` event per frame, previews rate-limited."""

    def __init__(self, conn: socket.socket, req: ManageRequest) -> None:
        self.conn = conn
        self.req = req
        self._last_preview = 0.0

    def __call__(self, report: FrameReport, frame: Frame) -> None:
        event: dict[str, Any] = {
            "type": "frame",
            "request_id": self.req.id,
            "report": report.to_dict(),
        }
        now = time.monotonic()
        if self.req.preview and now - self._last_preview >= PREVIEW_INTERVAL_S:
            preview = encode_preview(frame)
            # leave room for the report; an oversized preview is dropped, not fatal
            if preview is not None and len(preview) <= MAX_EVENT_PAYLOAD - 2048:
                event["preview"] = preview
                self._last_preview = now
        # raising here (client gone, write timeout) cancels the session
        _send(self.conn, event)


def encode_preview(frame: Frame) -> str | None:
    """
    Downscale a frame and encode it as base64 JPEG.
    :param frame: a colour or grayscale frame
    :return: the encoded preview, or None if encoding failed
    """
    height, width = frame.shape[:2]
    if width > PREVIEW_MAX_WIDTH:
        size = (PREVIEW_MAX_WIDTH, max(1, round(height * PREVIEW_MAX_WIDTH / width)))
        frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_JPEG_QUALITY])
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _watch_client(conn: socket.socket, session, done: threading.Event) -> None:
    """
    Cancel the session when the client asks to or goes away.

    Only polls and reads, so it never touches the socket timeout the session's writes use.
    """
    while not done.is_set():
        try:
            readable, _, _ = select.select([conn], [], [], WATCH_POLL_S)
            if not readable:
                continue
            message = read_frame(conn)
        except Exception:
            # EOF, a reset or garbage: the client is gone or broken either way
            session.cancel()
            return
        if message.get("type") == "cancel":
            session.cancel()
            return


def _load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(paths_factory.config_file_path())
    return config


def _send(conn: socket.socket, event: dict) -> None:
    write_frame(conn, {"v": MANAGE_VERSION, **event}, max_payload=MAX_EVENT_PAYLOAD)


def _result(conn: socket.socket, request_id: str | None, result: str, data: dict | None = None):
    message: dict[str, Any] = {"type": "result", "request_id": request_id, "result": result}
    if data is not None:
        message["data"] = data
    _send(conn, message)


def _try_result(conn: socket.socket, request_id: str | None, result: str) -> None:
    try:
        _result(conn, request_id, result)
    except Exception:
        pass
