import json
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

# Path setup
SRC_DIR = str(Path(__file__).resolve().parents[2] / "secureEye" / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import paths_factory  # noqa: E402
from auth.capture import FrameState, FrameStream  # noqa: E402
from auth.detector_factory import PipelineBundle  # noqa: E402
from auth.enrollment import EnrollOutcome, EnrollResult, EnrollSession  # noqa: E402

from .test_capture import (  # noqa: E402
    BLACK,
    BRIGHT,
    FAR,
    NATIVE_HEIGHT,
    NEAR,
    SPACE,
    FakeCapture,
    FixedRecognizer,
    ScriptedDetector,
    _config,
)


@pytest.fixture
def models_dir(tmp_path, monkeypatch):
    path = tmp_path / "models"
    path.mkdir()
    monkeypatch.setattr(paths_factory, "user_model_path", lambda user: str(path / f"{user}.dat"))
    return path


def _session(frames, faces, on_frame=None, dark_threshold=60, max_frames=10, recognizer=None):
    capture = FakeCapture(frames)
    bundle = PipelineBundle(
        backend="fake",
        detector=ScriptedDetector(faces),
        recognizer=recognizer or FixedRecognizer(),
    )
    session = EnrollSession(
        _config(dark_threshold),
        bundle,
        on_frame=on_frame,
        stream_factory=lambda config, transform: FrameStream(
            config, capture_factory=lambda _c: capture, transform=transform
        ),
        max_frames=max_frames,
    )
    return session, capture


# capture()


def test_capture_returns_embedding_of_the_single_face():
    reports = []
    session, capture = _session(
        frames=[BLACK, BRIGHT, BRIGHT],
        faces=[[], [NEAR]],
        on_frame=lambda report, frame: reports.append((report.state, frame.shape)),
    )

    outcome = session.capture()

    assert outcome.result is EnrollResult.SUCCESS
    np.testing.assert_allclose(outcome.embedding.vector, [0.9, 0.0])
    assert [state for state, _ in reports] == [
        FrameState.BLACK,
        FrameState.NO_FACE,
        FrameState.FACE,
    ]
    # enrollment works on the native frame, not the scaled one auth uses
    assert reports[-1][1] == (NATIVE_HEIGHT, 48, 3)
    assert capture.releases == 1


def test_capture_rejects_multiple_faces():
    session, capture = _session(frames=[BRIGHT], faces=[[NEAR, FAR]])

    outcome = session.capture()

    assert outcome.result is EnrollResult.MULTIPLE_FACES
    assert outcome.embedding is None
    assert capture.releases == 1


def test_capture_without_face_gives_up_after_max_frames():
    session, capture = _session(frames=[BRIGHT], faces=[[]], max_frames=5)

    outcome = session.capture()

    assert outcome.result is EnrollResult.NO_FACE
    assert outcome.valid_frames == 5
    assert capture.reads == 5


def test_capture_with_only_black_frames():
    session, _ = _session(frames=[BLACK], faces=[[NEAR]], max_frames=3)

    outcome = session.capture()

    assert outcome.result is EnrollResult.BLACK_FRAMES
    assert outcome.valid_frames == 0


def test_capture_with_only_dark_frames():
    reports = []
    session, _ = _session(
        frames=[BRIGHT],
        faces=[[NEAR]],
        dark_threshold=1,
        max_frames=3,
        on_frame=lambda report, _frame: reports.append(report),
    )

    outcome = session.capture()

    assert outcome.result is EnrollResult.TOO_DARK
    assert outcome.dark_tries == outcome.valid_frames == 3
    assert outcome.avg_darkness > 1
    assert [r.state for r in reports] == [FrameState.DARK] * 3


def test_cancel_during_settle_returns_quickly_and_releases_camera():
    session, capture = _session(frames=[BRIGHT], faces=[[NEAR]])
    threading.Timer(0.1, session.cancel).start()

    start = time.monotonic()
    outcome = session.capture(settle_s=5)

    assert outcome.result is EnrollResult.CANCELLED
    assert time.monotonic() - start < 2
    assert capture.reads == 0
    assert capture.releases == 1


def test_failing_observer_cancels_capture():
    def observer(_report, _frame):
        raise BrokenPipeError("client went away")

    session, capture = _session(frames=[BRIGHT], faces=[[NEAR]], on_frame=observer)

    assert session.capture().result is EnrollResult.CANCELLED
    assert capture.releases == 1


# run()


def _saved(models_dir):
    return json.loads((models_dir / "alice.dat").read_text(encoding="utf-8"))


def test_run_appends_a_template(models_dir):
    session, _ = _session(frames=[BRIGHT], faces=[[NEAR]])

    outcome = session.run("alice", "desk")

    assert outcome.result is EnrollResult.SUCCESS
    assert outcome.template.label == "desk"
    saved = _saved(models_dir)
    assert [(t["label"], t["model_id"]) for t in saved["templates"]] == [("desk", SPACE)]

    second, _ = _session(frames=[BRIGHT], faces=[[NEAR]])
    second.run("alice", "window")
    assert [t["label"] for t in _saved(models_dir)["templates"]] == ["desk", "window"]


def test_run_replace_swaps_the_active_space(models_dir):
    _session(frames=[BRIGHT], faces=[[NEAR]])[0].run("alice", "old")

    session, _ = _session(frames=[BRIGHT], faces=[[NEAR]])
    session.run("alice", "new", replace=True)

    assert [t["label"] for t in _saved(models_dir)["templates"]] == ["new"]


def test_failed_capture_writes_nothing(models_dir):
    session, _ = _session(frames=[BRIGHT], faces=[[NEAR, FAR]])

    assert session.run("alice", "x").result is EnrollResult.MULTIPLE_FACES
    assert not (models_dir / "alice.dat").exists()


def test_cancel_after_capture_writes_nothing(models_dir, monkeypatch):
    session, _ = _session(frames=[BRIGHT], faces=[[NEAR]])
    real_capture = session.capture

    def capture_then_cancel(*args, **kwargs):
        outcome = real_capture(*args, **kwargs)
        session.cancel()
        return outcome

    monkeypatch.setattr(session, "capture", capture_then_cancel)

    assert session.run("alice", "x").result is EnrollResult.CANCELLED
    assert not (models_dir / "alice.dat").exists()


def test_run_refuses_a_recognizer_from_another_space(models_dir):
    class OtherSpace(FixedRecognizer):
        @property
        def model_id(self):
            return "other-space"

    session, capture = _session(frames=[BRIGHT], faces=[[NEAR]], recognizer=OtherSpace())

    assert session.run("alice", "x") == EnrollOutcome(EnrollResult.MODEL_MISMATCH)
    assert capture.reads == 0
    assert not (models_dir / "alice.dat").exists()
