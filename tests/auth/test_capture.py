import configparser
import json
import sys
import threading
from pathlib import Path

import cv2
import numpy as np
import pytest

# Path setup
SRC_DIR = str(Path(__file__).resolve().parents[2] / "secureEye" / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import paths_factory  # noqa: E402
from auth import session as session_module  # noqa: E402
from auth.capture import (  # noqa: E402
    FrameReport,
    FrameState,
    FrameStream,
    normalized_boxes,
)
from auth.detector_factory import PipelineBundle  # noqa: E402
from auth.errors import ExitCode  # noqa: E402
from auth.interfaces import Detector, Embedding, Face, Recognizer  # noqa: E402
from auth.session import AuthSession  # noqa: E402

SPACE = "test-space"
NATIVE_HEIGHT = 64

BLACK = np.zeros((NATIVE_HEIGHT, 48, 3), dtype=np.uint8)
BRIGHT = np.random.default_rng(0).integers(0, 256, (NATIVE_HEIGHT, 48, 3), dtype=np.uint8)

# boxes are in the scaled frame: max_height 32 halves the 64px native frame to 32x24
NEAR = Face((4, 8, 12, 16))
FAR = Face((0, 0, 6, 6))
VECTORS = {NEAR.bbox: [0.9, 0.0], FAR.bbox: [0.0, 1.0]}


class FakeInternal:
    def __init__(self):
        self.props = {}

    def get(self, prop):
        return NATIVE_HEIGHT

    def set(self, prop, value):
        self.props[prop] = value


class FakeCapture:
    """Plays back scripted frames; repeats the last one once the script runs out."""

    def __init__(self, frames):
        self.frames = list(frames)
        self.internal = FakeInternal()
        self.fw = 48
        self.reads = 0
        self.releases = 0

    def read_frame(self):
        frame = self.frames[min(self.reads, len(self.frames) - 1)]
        self.reads += 1
        return frame, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def release(self):
        self.releases += 1


class ScriptedDetector(Detector):
    """Returns the next list of faces on each call; repeats the last list afterwards."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def detect(self, frame):
        faces = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return list(faces)


class FixedRecognizer(Recognizer):
    @property
    def model_id(self):
        return SPACE

    @property
    def dim(self):
        return 2

    def embed(self, frame, face):
        return Embedding(np.asarray(VECTORS[face.bbox], np.float32), SPACE, 2)


def _config(dark_threshold=60, timeout=4):
    config = configparser.ConfigParser()
    config.read_string(
        f"""
[core]
pipeline = onnx

[recognition]
model_id = {SPACE}

[video]
timeout = {timeout}
dark_threshold = {dark_threshold}
max_height = 32
certainty = 3.5
"""
    )
    return config


# FrameStream


def test_stream_classifies_black_dark_and_usable_frames():
    capture = FakeCapture([BLACK, BRIGHT])
    stream = FrameStream(_config(), capture_factory=lambda _config: capture)

    black = stream.read()
    usable = stream.read()

    assert black.state is FrameState.BLACK and not black.usable
    assert usable.usable
    assert (black.index, usable.index) == (1, 2)


def test_stream_marks_frames_over_threshold_dark():
    stream = FrameStream(
        _config(dark_threshold=1), capture_factory=lambda _c: FakeCapture([BRIGHT])
    )

    captured = stream.read()

    assert captured.state is FrameState.DARK
    assert captured.darkness > 1


def test_stream_scales_usable_frames_only():
    stream = FrameStream(
        _config(dark_threshold=1), capture_factory=lambda _c: FakeCapture([BRIGHT])
    )
    dark = stream.read()
    assert dark.frame.shape[0] == NATIVE_HEIGHT

    stream = FrameStream(_config(), capture_factory=lambda _c: FakeCapture([BRIGHT]))
    usable = stream.read()
    assert usable.frame.shape[:2] == (32, 24)
    assert usable.gsframe.shape == (32, 24)
    assert usable.raw.shape[0] == NATIVE_HEIGHT


def test_stream_release_is_idempotent_and_thread_safe():
    capture = FakeCapture([BRIGHT])
    stream = FrameStream(_config(), capture_factory=lambda _c: capture)

    threads = [threading.Thread(target=stream.release) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert capture.releases == 1


def test_normalized_boxes_are_fractions_of_the_frame():
    frame = np.zeros((32, 24, 3), dtype=np.uint8)

    assert normalized_boxes([NEAR], frame) == ((4 / 24, 8 / 32, 12 / 24, 16 / 32),)
    assert normalized_boxes([], frame) == ()


def test_report_to_dict_is_json_ready():
    report = FrameReport(
        index=3,
        elapsed=0.12345,
        state=FrameState.FACE,
        darkness=12.345,
        dark_threshold=60.0,
        faces=((0.1, 0.2, 0.3, 0.4),),
        distance=4.1234,
        certainty=3.5,
    )

    data = json.loads(json.dumps(report.to_dict()))

    assert data == {
        "index": 3,
        "elapsed": 0.123,
        "state": "face",
        "darkness": 12.3,
        "dark_threshold": 60.0,
        "faces": [[0.1, 0.2, 0.3, 0.4]],
        "distance": 4.123,
        "certainty": 3.5,
    }


# AuthSession reports


@pytest.fixture
def session_env(tmp_path, monkeypatch):
    """Wire AuthSession to a fake camera and pipeline; returns a function that runs it."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    monkeypatch.setattr(
        paths_factory, "user_model_path", lambda user: str(models_dir / f"{user}.dat")
    )
    (models_dir / "alice.dat").write_text(
        json.dumps(
            {
                "version": 2,
                "templates": [
                    {
                        "id": 0,
                        "label": "me",
                        "created": 1,
                        "model_id": SPACE,
                        "dim": 2,
                        "data": [[1.0, 0.0]],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def run(frames, faces, on_frame=None, dark_threshold=60, timeout=4):
        config_path = tmp_path / "config.ini"
        with config_path.open("w", encoding="utf-8") as handle:
            _config(dark_threshold, timeout).write(handle)

        capture = FakeCapture(frames)
        bundle = PipelineBundle(
            backend="fake", detector=ScriptedDetector(faces), recognizer=FixedRecognizer()
        )
        monkeypatch.setattr(session_module, "create_pipeline", lambda _config: bundle)
        monkeypatch.setattr(
            session_module,
            "FrameStream",
            lambda config: FrameStream(config, capture_factory=lambda _c: capture),
        )
        code = AuthSession(str(config_path), on_frame=on_frame).run("alice")
        return code, capture

    return run


def test_session_reports_every_frame_until_match(session_env):
    reports = []

    code, capture = session_env(
        frames=[BLACK, BRIGHT, BRIGHT, BRIGHT],
        faces=[[], [FAR, NEAR], [NEAR]],
        on_frame=lambda report, frame: reports.append((report, frame.shape)),
    )

    assert code == int(ExitCode.SUCCESS)
    assert [r.state for r, _ in reports] == [
        FrameState.BLACK,
        FrameState.NO_FACE,
        FrameState.MATCH,
    ]
    # the second scripted list has two faces, but NEAR matches before MULTIPLE is reported
    match, shape = reports[-1]
    assert shape == (32, 24, 3)
    assert match.faces == normalized_boxes([FAR, NEAR], np.zeros(shape, np.uint8))
    assert match.distance == pytest.approx(1.0)
    assert match.certainty == pytest.approx(3.5)
    assert [r.index for r, _ in reports] == [1, 2, 3]
    assert capture.releases == 1


def test_session_reports_multiple_faces_without_a_match(session_env):
    reports = []

    session_env(
        frames=[BRIGHT, BRIGHT],
        faces=[[FAR, FAR], [NEAR]],
        on_frame=lambda report, _frame: reports.append(report),
    )

    multiple = reports[0]
    assert multiple.state is FrameState.MULTIPLE
    assert len(multiple.faces) == 2
    assert multiple.distance == pytest.approx(np.sqrt(2) * 10)
    assert reports[1].state is FrameState.MATCH


def test_session_reports_single_unmatched_face(session_env):
    reports = []

    session_env(
        frames=[BRIGHT],
        faces=[[FAR], [NEAR]],
        on_frame=lambda report, _frame: reports.append(report),
    )

    assert reports[0].state is FrameState.FACE
    assert reports[0].distance == pytest.approx(np.sqrt(2) * 10)


def test_session_reports_dark_frames_and_times_out_too_dark(session_env):
    reports = []

    code, capture = session_env(
        frames=[BRIGHT],
        faces=[[NEAR]],
        on_frame=lambda report, _frame: reports.append(report),
        dark_threshold=1,
        timeout=1,
    )

    assert code == int(ExitCode.TOO_DARK)
    assert reports and all(r.state is FrameState.DARK for r in reports)
    assert all(r.distance is None and r.faces == () for r in reports)
    assert capture.releases == 1


def test_failing_observer_cancels_the_session(session_env):
    def observer(_report, _frame):
        raise BrokenPipeError("client went away")

    code, capture = session_env(frames=[BRIGHT], faces=[[]], on_frame=observer)

    assert code == int(ExitCode.TIMEOUT_REACHED)
    assert capture.reads == 1
    assert capture.releases == 1


def test_session_without_observer_still_matches(session_env):
    code, capture = session_env(frames=[BRIGHT], faces=[[NEAR]])

    assert code == int(ExitCode.SUCCESS)
    assert capture.releases == 1


def test_darkness_percent_returns_plain_floats():
    """Regression: float() on calcHist's (1,) row raises on NumPy 2."""
    from auth.frame_ops import darkness_percent

    gray = np.zeros((10, 10), dtype=np.uint8)
    gray[:, 5:] = 200

    darkness, total = darkness_percent(gray)

    assert isinstance(darkness, float) and isinstance(total, float)
    assert darkness == pytest.approx(50.0)
    assert total == 100.0
