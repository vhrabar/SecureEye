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
from auth import template_store  # noqa: E402
from auth.capture import FrameState, FrameStream  # noqa: E402
from auth.detector_factory import PipelineBundle  # noqa: E402
from auth.recognition_probe import ProbeResult, RecognitionProbe  # noqa: E402

from .test_capture import (  # noqa: E402
    BLACK,
    BRIGHT,
    FAR,
    NEAR,
    SPACE,
    FakeCapture,
    FixedRecognizer,
    ScriptedDetector,
    _config,
)


class ExitingCapture(FakeCapture):
    """Like VideoCapture: a read from a released camera fails with sys.exit(14)."""

    def read_frame(self):
        time.sleep(0.01)
        if self.releases:
            sys.exit(14)
        return super().read_frame()


@pytest.fixture
def models_dir(tmp_path, monkeypatch):
    path = tmp_path / "models"
    path.mkdir()
    monkeypatch.setattr(paths_factory, "user_model_path", lambda user: str(path / f"{user}.dat"))
    template_store.append("alice", model_id=SPACE, label="me", embeddings=np.array([[1.0, 0.0]]))
    return path


def _probe(frames, faces, on_frame=None, duration_s=0.2, recognizer=None):
    capture = FakeCapture(frames)
    bundle = PipelineBundle(
        backend="fake",
        detector=ScriptedDetector(faces),
        recognizer=recognizer or FixedRecognizer(),
    )
    probe = RecognitionProbe(
        _config(),
        bundle,
        on_frame=on_frame,
        stream_factory=lambda config: FrameStream(config, capture_factory=lambda _c: capture),
        duration_s=duration_s,
    )
    return probe, capture


def test_probe_keeps_reporting_past_a_match(models_dir):
    reports = []
    probe, capture = _probe(
        frames=[BLACK, BRIGHT],
        faces=[[], [FAR], [NEAR]],
        on_frame=lambda report, _frame: reports.append(report),
    )

    outcome = probe.run("alice")

    assert outcome.result is ProbeResult.COMPLETED
    states = [r.state for r in reports]
    assert states[:4] == [FrameState.BLACK, FrameState.NO_FACE, FrameState.FACE, FrameState.MATCH]
    # it does not stop at the first match like a login does
    assert states[4:] and set(states[4:]) == {FrameState.MATCH}
    assert outcome.frames == len(reports)
    assert outcome.matched_frames == len(reports) - 3
    assert outcome.best_distance == pytest.approx(1.0)
    match = reports[3]
    assert match.distance == pytest.approx(1.0) and match.certainty == pytest.approx(3.5)
    assert capture.releases == 1


def test_probe_without_models(models_dir):
    probe, capture = _probe(frames=[BRIGHT], faces=[[NEAR]])

    assert probe.run("bob").result is ProbeResult.NO_MODELS
    assert capture.reads == 0


def test_probe_with_models_from_another_recognizer(models_dir):
    class OtherSpace(FixedRecognizer):
        @property
        def model_id(self):
            return "other-space"

    probe, _ = _probe(frames=[BRIGHT], faces=[[NEAR]], recognizer=OtherSpace())

    assert probe.run("alice").result is ProbeResult.MODEL_MISMATCH


def test_cancel_stops_the_probe_and_releases_the_camera(models_dir):
    probe, capture = _probe(frames=[BRIGHT], faces=[[NEAR]], duration_s=30)
    threading.Timer(0.1, probe.cancel).start()

    start = time.monotonic()
    outcome = probe.run("alice")

    assert outcome.result is ProbeResult.CANCELLED
    assert time.monotonic() - start < 2
    assert capture.releases == 1


def test_cancel_while_reading_is_cancelled_not_a_camera_error(models_dir):
    capture = ExitingCapture([BRIGHT])
    bundle = PipelineBundle(
        backend="fake", detector=ScriptedDetector([[]]), recognizer=FixedRecognizer()
    )
    probe = RecognitionProbe(
        _config(),
        bundle,
        stream_factory=lambda config: FrameStream(config, capture_factory=lambda _c: capture),
        duration_s=30,
    )
    threading.Timer(0.05, probe.cancel).start()

    assert probe.run("alice").result is ProbeResult.CANCELLED


def test_failing_observer_cancels_the_probe(models_dir):
    def observer(_report, _frame):
        raise BrokenPipeError("client went away")

    probe, capture = _probe(frames=[BRIGHT], faces=[[NEAR]], on_frame=observer, duration_s=30)

    outcome = probe.run("alice")

    assert outcome.result is ProbeResult.CANCELLED
    assert outcome.frames == 1
    assert capture.releases == 1
