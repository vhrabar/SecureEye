import base64
import os
import pwd
import socket
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "secureEye" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import paths_factory  # noqa: E402
from auth import ExitCode, template_store  # noqa: E402
from auth.capture import FrameStream  # noqa: E402
from auth.detector_factory import PipelineBundle  # noqa: E402
from authd import main as authd_main  # noqa: E402
from authd import manage  # noqa: E402
from authd.camera import CameraArbiter, CameraUse  # noqa: E402
from authd.protocol import read_frame, write_frame  # noqa: E402

from ..auth.test_capture import (  # noqa: E402
    BLACK,
    BRIGHT,
    NEAR,
    SPACE,
    FakeCapture,
    FixedRecognizer,
    ScriptedDetector,
    _config,
)

ME = pwd.getpwuid(os.getuid()).pw_name


class SlowCapture(FakeCapture):
    """Paces reads like a real camera, so a session doesn't flood the socket."""

    def read_frame(self):
        time.sleep(0.01)
        return super().read_frame()


class QuickLogin:
    def run(self, user):
        return int(ExitCode.SUCCESS)

    def cancel(self):
        pass


@pytest.fixture
def daemon(monkeypatch, tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    monkeypatch.setattr(paths_factory, "user_model_path", lambda user: str(models / f"{user}.dat"))

    env = SimpleNamespace(
        models=models, frames=[BRIGHT], faces=[[NEAR]], captures=[], camera=CameraArbiter()
    )
    monkeypatch.setattr(authd_main, "_camera", env.camera)
    monkeypatch.setattr(authd_main, "AuthSession", QuickLogin)
    monkeypatch.setattr(manage, "_load_config", _config)
    monkeypatch.setattr(
        manage,
        "create_pipeline",
        lambda _config: PipelineBundle(
            backend="fake", detector=ScriptedDetector(env.faces), recognizer=FixedRecognizer()
        ),
    )

    def stream(config, transform=True):
        capture = SlowCapture(env.frames)
        env.captures.append(capture)
        return FrameStream(config, capture_factory=lambda _c: capture, transform=transform)

    monkeypatch.setattr(manage, "stream_factory", stream)

    env.path = str(tmp_path / "authd.sock")
    srv = authd_main._prepare_socket(env.path)
    stop = threading.Event()
    thread = threading.Thread(target=authd_main.serve, args=(srv, stop), daemon=True)
    thread.start()
    yield env
    stop.set()
    thread.join(5)
    srv.close()


def _open(path: str, payload: dict) -> socket.socket:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(path)
    write_frame(sock, {"v": 2, "request_id": "r1", "username": ME, **payload})
    return sock


def _until_result(sock: socket.socket) -> list[dict]:
    messages = []
    while True:
        message = read_frame(sock)
        messages.append(message)
        if message["type"] == "result":
            return messages


def _request(path: str, payload: dict) -> list[dict]:
    with _open(path, payload) as sock:
        return _until_result(sock)


def _result(path: str, payload: dict) -> dict:
    return _request(path, payload)[-1]


def _add_model(label: str) -> None:
    template_store.append(ME, model_id=SPACE, label=label, embeddings=np.array([[1.0, 0.0]]))


def _wait_for_free_camera(camera: CameraArbiter, timeout: float = 2.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if camera.holder() is None:
            return True
        time.sleep(0.02)
    return False


# model requests


def test_list_without_models_is_empty(daemon):
    result = _result(daemon.path, {"type": "models_list"})
    assert result["result"] == "success"
    assert result["data"] == {"user": ME, "models": []}
    assert result["v"] == 2 and result["request_id"] == "r1"


def test_remove_one_then_the_last(daemon):
    _add_model("desk")
    _add_model("window")

    result = _result(daemon.path, {"type": "models_remove", "model": 0})
    assert (result["result"], result["data"]) == ("success", {"removed": 0, "remaining": 1})

    listed = _result(daemon.path, {"type": "models_list"})["data"]["models"]
    assert [(m["id"], m["label"], m["model_id"]) for m in listed] == [(1, "window", SPACE)]

    assert _result(daemon.path, {"type": "models_remove", "model": 0})["result"] == (
        "model_not_found"
    )
    assert _result(daemon.path, {"type": "models_remove", "model": 1})["result"] == "success"
    assert not (daemon.models / f"{ME}.dat").exists()


def test_clear(daemon):
    _add_model("desk")
    _add_model("window")

    result = _result(daemon.path, {"type": "models_clear"})
    assert (result["result"], result["data"]) == ("success", {"removed": 2})
    assert _result(daemon.path, {"type": "models_clear"})["result"] == "no_models"


def test_unreadable_model_file(daemon):
    (daemon.models / f"{ME}.dat").write_text("not json", encoding="utf-8")

    assert _result(daemon.path, {"type": "models_list"})["result"] == "model_file_invalid"
    # clearing is the way out of a broken file
    assert _result(daemon.path, {"type": "models_clear"})["result"] == "success"


def test_invalid_request(daemon):
    result = _result(daemon.path, {"type": "enroll"})  # no label
    assert result["result"] == "invalid_request"
    assert result["request_id"] == "r1"


@pytest.mark.skipif(os.getuid() == 0, reason="root may manage anyone")
def test_user_cannot_manage_someone_else(daemon):
    for payload in (
        {"type": "models_list"},
        {"type": "models_clear"},
        {"type": "enroll", "label": "x"},
    ):
        result = _result(daemon.path, {**payload, "username": "root"})
        assert result["result"] == "forbidden"
    assert daemon.captures == []


# camera sessions


def test_enroll_streams_frames_and_saves_the_model(daemon):
    daemon.faces[:] = [[], [NEAR]]

    messages = _request(daemon.path, {"type": "enroll", "label": "desk", "preview": True})

    assert messages[0]["type"] == "started"
    frames = [m for m in messages if m["type"] == "frame"]
    assert [f["report"]["state"] for f in frames] == ["no_face", "face"]
    jpeg = base64.b64decode(frames[0]["preview"])
    assert jpeg[:2] == b"\xff\xd8"

    result = messages[-1]
    assert result["result"] == "success"
    assert result["data"]["model"] == 0
    assert result["data"]["label"] == "desk"
    assert result["data"]["model_id"] == SPACE
    assert [t.label for t in template_store.load_all(ME)] == ["desk"]
    assert daemon.captures[0].releases == 1
    assert daemon.camera.holder() is None


def test_black_frames_carry_no_preview(daemon):
    # an IR camera with its emitter on every other frame
    daemon.frames[:] = [BRIGHT, BLACK, BRIGHT, BLACK]
    daemon.faces[:] = [[], [NEAR]]

    messages = _request(daemon.path, {"type": "enroll", "label": "desk", "preview": True})

    frames = [(m["report"]["state"], "preview" in m) for m in messages if m["type"] == "frame"]
    assert [state for state, _ in frames] == ["no_face", "black", "face"]
    assert ("black", True) not in frames
    assert frames[0] == ("no_face", True)


def test_enroll_without_preview_sends_no_images(daemon):
    messages = _request(daemon.path, {"type": "enroll", "label": "desk"})
    assert all("preview" not in m for m in messages)
    assert messages[-1]["result"] == "success"


def test_enroll_failure_writes_nothing(daemon):
    daemon.faces[:] = [[NEAR, NEAR]]

    result = _result(daemon.path, {"type": "enroll", "label": "desk"})

    assert result["result"] == "multiple_faces"
    assert not (daemon.models / f"{ME}.dat").exists()


def test_test_session_reports_distances(daemon):
    _add_model("desk")

    messages = _request(daemon.path, {"type": "test", "duration_ms": 1000})

    frames = [m["report"] for m in messages if m["type"] == "frame"]
    assert frames and {f["state"] for f in frames} == {"match"}
    assert frames[0]["distance"] == pytest.approx(1.0)
    result = messages[-1]
    assert result["result"] == "completed"
    assert result["data"]["matched_frames"] == len(frames)
    assert result["data"]["best_distance"] == pytest.approx(1.0)


def test_cancel_message_stops_the_session(daemon):
    _add_model("desk")
    with _open(daemon.path, {"type": "test", "duration_ms": 60000}) as sock:
        assert read_frame(sock)["type"] == "started"
        start = time.monotonic()
        write_frame(sock, {"v": 2, "type": "cancel", "request_id": "r1"})
        result = _until_result(sock)[-1]

    assert result["result"] == "cancelled"
    assert time.monotonic() - start < 1
    assert daemon.camera.holder() is None


def test_dead_client_releases_the_camera(daemon):
    _add_model("desk")
    sock = _open(daemon.path, {"type": "test", "duration_ms": 60000})
    assert read_frame(sock)["type"] == "started"
    assert daemon.camera.holder() is CameraUse.MANAGE

    sock.close()

    assert _wait_for_free_camera(daemon.camera)
    assert daemon.captures[0].releases == 1


def test_login_preempts_a_management_session(daemon):
    _add_model("desk")
    messages = []
    with _open(daemon.path, {"type": "test", "duration_ms": 60000}) as sock:
        assert read_frame(sock)["type"] == "started"
        reader = threading.Thread(target=lambda: messages.extend(_until_result(sock)))
        reader.start()

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as login:
            login.settimeout(5)
            login.connect(daemon.path)
            write_frame(
                login,
                {
                    "v": 1,
                    "type": "auth_request",
                    "request_id": "pam",
                    "username": ME,
                    "deadline_ms": 2500,
                },
            )
            assert read_frame(login)["result_code"] == 0

        reader.join(5)

    assert messages[-1]["result"] == "preempted"


def test_missing_camera(daemon, monkeypatch):
    def no_camera(config, transform=True):
        sys.exit(int(ExitCode.INVALID_DEVICE))

    monkeypatch.setattr(manage, "stream_factory", no_camera)

    messages = _request(daemon.path, {"type": "enroll", "label": "desk"})

    assert messages[-1]["result"] == "invalid_device"
    assert daemon.camera.holder() is None


def test_busy_camera(daemon, monkeypatch):
    monkeypatch.setattr(manage, "CAMERA_WAIT_S", 0.2)
    login = QuickLogin()
    assert daemon.camera.acquire(CameraUse.AUTH, login, 1)
    try:
        result = _result(daemon.path, {"type": "test"})
    finally:
        daemon.camera.release(login)

    assert result["result"] == "busy"
    assert daemon.captures == []


def test_preview_is_downscaled_jpeg():
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    jpeg = base64.b64decode(manage.encode_preview(frame))

    decoded = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == (180, 320, 3)
