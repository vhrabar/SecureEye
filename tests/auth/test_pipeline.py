import math
import sys
from pathlib import Path

import numpy as np
import pytest

# Path setup
SRC_DIR = str(Path(__file__).resolve().parents[2] / "secureEye" / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from auth.detector_factory import PipelineBundle  # noqa: E402
from auth.interfaces import (  # noqa: E402
    Detector,
    Embedding,
    Face,
    LivenessCheck,
    LivenessResult,
    Recognizer,
)
from auth.pipeline import Pipeline  # noqa: E402
from auth.template_store import Template, TemplateSet  # noqa: E402

SPACE = "test-space"
FRAME = np.zeros((4, 4, 3), dtype=np.uint8)
GRAY = np.zeros((4, 4), dtype=np.uint8)

NEAR = Face((0, 0, 10, 10))
FAR = Face((20, 20, 10, 10))


class FakeDetector(Detector):
    def __init__(self, faces):
        self.faces = faces
        self.frames = []

    def detect(self, frame):
        self.frames.append(frame)
        return list(self.faces)


class FakeRecognizer(Recognizer):
    """Embeds each face to a fixed vector, keyed by its box."""

    def __init__(self, vectors, model_id=SPACE):
        self.vectors = vectors
        self._model_id = model_id
        self.embedded = []

    @property
    def model_id(self):
        return self._model_id

    @property
    def dim(self):
        return 2

    def embed(self, frame, face):
        self.embedded.append(face)
        return Embedding(np.asarray(self.vectors[face.bbox], np.float32), self._model_id, 2)


class FakeLiveness(LivenessCheck):
    def __init__(self, live_boxes):
        self.live_boxes = live_boxes

    def check(self, frame, face):
        passed = face.bbox in self.live_boxes
        return LivenessResult(passed=passed, score=1.0 if passed else 0.0)


def _templates():
    """Two templates; matrix rows 0 and 1 belong to 'alice', row 2 to 'bob'."""
    alice = Template(1, "alice", 0, SPACE, np.array([[1, 0], [0.9, 0]], np.float32))
    bob = Template(2, "bob", 0, SPACE, np.array([[0, 1]], np.float32))
    matrix = np.vstack([alice.embeddings, bob.embeddings])
    return TemplateSet(SPACE, [alice, bob], matrix, np.array([0, 0, 1], np.intp))


def _pipeline(faces=(NEAR, FAR), liveness=None, model_id=SPACE, threshold=0.35):
    vectors = {NEAR.bbox: [0.9, 0.1], FAR.bbox: [-1, -1]}
    bundle = PipelineBundle(
        backend="fake",
        detector=FakeDetector(faces),
        recognizer=FakeRecognizer(vectors, model_id),
        liveness=liveness,
    )
    return Pipeline(bundle, _templates(), threshold)


def test_rejects_templates_from_another_space():
    with pytest.raises(ValueError, match="test-space"):
        _pipeline(model_id="other-space")


def test_match_accepts_nearest_template_within_threshold():
    pipeline = _pipeline()

    result = pipeline.match(FRAME, NEAR)

    assert result.accepted
    assert result.row == 1
    assert result.distance == pytest.approx(0.1)
    assert pipeline.owner_of(result).label == "alice"


def test_match_rejects_beyond_threshold():
    result = _pipeline().match(FRAME, FAR)

    assert not result.accepted
    assert result.distance > 0.35


def test_scan_detects_on_detect_frame_and_embeds_from_frame():
    pipeline = _pipeline()

    results = list(pipeline.scan(FRAME, GRAY))

    assert pipeline.bundle.detector.frames == [GRAY]
    assert [r.face for r in results] == [NEAR, FAR]
    assert [r.accepted for r in results] == [True, False]


def test_scan_defaults_to_detecting_on_frame():
    pipeline = _pipeline()

    list(pipeline.scan(FRAME))

    assert pipeline.bundle.detector.frames == [FRAME]


def test_scan_is_lazy_so_callers_can_stop_at_first_match():
    pipeline = _pipeline()

    first = next(pipeline.scan(FRAME))

    assert first.accepted
    assert pipeline.bundle.recognizer.embedded == [NEAR]


def test_failed_liveness_skips_embedding():
    pipeline = _pipeline(liveness=FakeLiveness(live_boxes=set()))

    result = pipeline.match(FRAME, NEAR)

    assert not result.accepted
    assert result.row == -1
    assert math.isinf(result.distance)
    assert result.liveness is not None and not result.liveness.passed
    assert pipeline.bundle.recognizer.embedded == []
    assert pipeline.owner_of(result) is None


def test_passed_liveness_is_reported_with_the_match():
    result = _pipeline(liveness=FakeLiveness(live_boxes={NEAR.bbox})).match(FRAME, NEAR)

    assert result.accepted
    assert result.liveness is not None and result.liveness.passed
