import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

# Path setup
SRC_DIR = str(Path(__file__).resolve().parents[2] / "secureEye" / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from auth.interfaces import Detector, Face, Recognizer  # noqa: E402
from auth.template_store import LEGACY_MODEL_ID  # noqa: E402


class FakeRect:
    """Mimics dlib.rectangle: inclusive corners, width() == right - left + 1."""

    def __init__(self, left, top, right, bottom):
        self.corners = (left, top, right, bottom)

    def left(self):
        return self.corners[0]

    def top(self):
        return self.corners[1]

    def width(self):
        return self.corners[2] - self.corners[0] + 1

    def height(self):
        return self.corners[3] - self.corners[1] + 1


@pytest.fixture
def dlib_backend(monkeypatch):
    fake_dlib = ModuleType("dlib")
    fake_dlib.rectangle = FakeRect
    monkeypatch.setitem(sys.modules, "dlib", fake_dlib)
    monkeypatch.delitem(sys.modules, "auth.legacy.dlib_backend", raising=False)

    # import_module, not `from auth.legacy import ...`: the package attribute may
    # still hold a module bound to another test's fake dlib.
    return importlib.import_module("auth.legacy.dlib_backend")


def _backend(found=(), descriptor=None):
    calls = {}

    def pose_predictor(frame, rect):
        calls["rect"] = rect
        return "shape"

    def compute_face_descriptor(frame, shape, upsample):
        calls["descriptor_args"] = (shape, upsample)
        return descriptor

    backend = SimpleNamespace(
        detector=lambda frame, upsample: list(found),
        pose_predictor=pose_predictor,
        face_encoder=SimpleNamespace(compute_face_descriptor=compute_face_descriptor),
    )
    return backend, calls


FRAME = np.zeros((480, 640), dtype=np.uint8)


class TestDlibFaceDetector:
    def test_is_a_detector(self, dlib_backend):
        backend, _ = _backend()
        assert isinstance(dlib_backend.DlibFaceDetector(backend), Detector)

    def test_hog_rects_become_xywh_faces(self, dlib_backend):
        backend, _ = _backend(found=[FakeRect(10, 20, 109, 139)])

        faces = dlib_backend.DlibFaceDetector(backend).detect(FRAME)

        assert faces == [Face((10, 20, 100, 120), score=1.0)]
        assert not faces[0].has_landmarks

    def test_cnn_detections_keep_confidence_strongest_first(self, dlib_backend):
        weak = SimpleNamespace(rect=FakeRect(0, 0, 9, 9), confidence=0.4)
        strong = SimpleNamespace(rect=FakeRect(50, 50, 59, 59), confidence=0.9)
        backend, _ = _backend(found=[weak, strong])

        faces = dlib_backend.DlibFaceDetector(backend).detect(FRAME)

        assert [face.bbox for face in faces] == [(50, 50, 10, 10), (0, 0, 10, 10)]
        assert [face.score for face in faces] == pytest.approx([0.9, 0.4])

    def test_no_faces(self, dlib_backend):
        backend, _ = _backend()
        assert dlib_backend.DlibFaceDetector(backend).detect(FRAME) == []


class TestDlibRecognizer:
    def test_identifies_legacy_space(self, dlib_backend):
        backend, _ = _backend()
        recognizer = dlib_backend.DlibRecognizer(backend)

        assert isinstance(recognizer, Recognizer)
        assert recognizer.model_id == LEGACY_MODEL_ID
        assert recognizer.dim == 128

    def test_embed_keeps_raw_descriptor(self, dlib_backend):
        """Legacy thresholds are Euclidean on raw descriptors; normalizing would shift them."""
        descriptor = [0.5] * 128
        backend, calls = _backend(descriptor=descriptor)

        embedding = dlib_backend.DlibRecognizer(backend).embed(FRAME, Face((10, 20, 100, 120)))

        assert embedding.model_id == LEGACY_MODEL_ID
        assert embedding.dim == 128
        assert embedding.vector.dtype == np.float32
        np.testing.assert_array_equal(embedding.vector, np.full(128, 0.5, dtype=np.float32))
        assert calls["descriptor_args"] == ("shape", 1)

    def test_bbox_round_trips_to_the_detected_rect(self, dlib_backend):
        rect = FakeRect(10, 20, 109, 139)
        backend, calls = _backend(found=[rect], descriptor=[0.1] * 128)

        face = dlib_backend.DlibFaceDetector(backend).detect(FRAME)[0]
        dlib_backend.DlibRecognizer(backend).embed(FRAME, face)

        assert calls["rect"].corners == rect.corners

    def test_wrong_descriptor_length_is_rejected(self, dlib_backend):
        backend, _ = _backend(descriptor=[0.1] * 64)

        with pytest.raises(ValueError):
            dlib_backend.DlibRecognizer(backend).embed(FRAME, Face((0, 0, 10, 10)))
