"""Tests for MediaPipeDetector."""

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


def _install_fake_mediapipe(monkeypatch):
    class _ImageFormat:
        SRGB = "srgb"

    class _Image:
        def __init__(self, image_format, data):
            self.image_format = image_format
            self.data = data

    mp_module = ModuleType("mediapipe")
    mp_module.Image = _Image
    mp_module.ImageFormat = _ImageFormat

    tasks_module = ModuleType("mediapipe.tasks")
    tasks_python_module = ModuleType("mediapipe.tasks.python")
    tasks_python_module.BaseOptions = type("BaseOptions", (), {})
    tasks_python_module.vision = ModuleType("mediapipe.tasks.python.vision")

    monkeypatch.setitem(sys.modules, "mediapipe", mp_module)
    monkeypatch.setitem(sys.modules, "mediapipe.tasks", tasks_module)
    monkeypatch.setitem(sys.modules, "mediapipe.tasks.python", tasks_python_module)
    monkeypatch.setitem(sys.modules, "mediapipe.tasks.python.vision", tasks_python_module.vision)


@pytest.fixture
def detector_module(monkeypatch):
    _install_fake_mediapipe(monkeypatch)
    sys.modules.pop("detectors.mediapipe_detector", None)
    return importlib.import_module("detectors.mediapipe_detector")


def test_detect_returns_clamped_boxes(detector_module):
    detector = detector_module.MediaPipeDetector.__new__(detector_module.MediaPipeDetector)
    detector.mp_detector = SimpleNamespace(
        detect=lambda _img: SimpleNamespace(
            detections=[
                SimpleNamespace(
                    bounding_box=SimpleNamespace(origin_x=-4, origin_y=10, width=100, height=100)
                )
            ]
        )
    )

    frame = np.zeros((50, 60, 3), dtype=np.uint8)
    assert detector.detect(frame) == [(0, 10, 60, 40)]


def test_detect_returns_empty_when_no_detections(detector_module):
    detector = detector_module.MediaPipeDetector.__new__(detector_module.MediaPipeDetector)
    detector.mp_detector = SimpleNamespace(detect=lambda _img: SimpleNamespace(detections=[]))

    frame = np.zeros((20, 30, 3), dtype=np.uint8)
    assert detector.detect(frame) == []


def test_encode_returns_zero_embedding_when_no_landmarks(detector_module):
    detector = detector_module.MediaPipeDetector.__new__(detector_module.MediaPipeDetector)
    detector.mp_landmarker = SimpleNamespace(detect=lambda _img: SimpleNamespace(face_landmarks=[]))

    frame = np.zeros((40, 40, 3), dtype=np.uint8)
    embedding = detector.encode(frame, (5, 5, 10, 10))

    assert embedding.shape == (detector_module.EMBEDDING_SIZE,)
    assert np.allclose(embedding, 0)


def test_encode_returns_normalized_embedding_with_landmarks(detector_module):
    detector = detector_module.MediaPipeDetector.__new__(detector_module.MediaPipeDetector)
    landmarks = [SimpleNamespace(x=i / 10.0, y=i / 20.0, z=i / 30.0) for i in range(12)]
    detector.mp_landmarker = SimpleNamespace(
        detect=lambda _img: SimpleNamespace(face_landmarks=[landmarks])
    )

    frame = np.zeros((40, 40, 3), dtype=np.uint8)
    embedding = detector.encode(frame, (2, 2, 20, 20))

    assert embedding.shape == (detector_module.EMBEDDING_SIZE,)
    assert np.isclose(np.linalg.norm(embedding), 1.0, atol=1e-5)


def test_landmarks_to_embedding_handles_constant_input(detector_module):
    landmarks = [SimpleNamespace(x=1.0, y=1.0, z=1.0) for _ in range(5)]
    embedding = detector_module.MediaPipeDetector._landmarks_to_embedding(landmarks)

    assert embedding.shape == (detector_module.EMBEDDING_SIZE,)
    assert np.all(np.isfinite(embedding))
