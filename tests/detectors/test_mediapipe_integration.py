"""Optional integration checks that use the real mediapipe package."""

import importlib
import sys
from pathlib import Path

import numpy as np
import pytest

SRC_DIR = str(Path(__file__).resolve().parents[2] / "secureEye" / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

pytestmark = pytest.mark.mediapipe_integration

mp = pytest.importorskip("mediapipe")
pytest.importorskip("mediapipe.tasks.python")


def test_mediapipe_tasks_api_is_available():
    from mediapipe.tasks.python import BaseOptions, vision

    assert BaseOptions is not None
    assert hasattr(vision, "FaceDetectorOptions")
    assert hasattr(vision, "FaceLandmarkerOptions")
    assert hasattr(vision, "RunningMode")


def test_detector_module_imports_with_real_mediapipe():
    sys.modules.pop("detectors.mediapipe_detector", None)
    module = importlib.import_module("detectors.mediapipe_detector")

    assert module.mp is mp
    assert hasattr(module, "MediaPipeDetector")


def test_to_rgb_uses_opencv_color_conversion():
    module = importlib.import_module("detectors.mediapipe_detector")

    bgr = np.zeros((1, 1, 3), dtype=np.uint8)
    bgr[0, 0] = [255, 0, 0]
    rgb = module.MediaPipeDetector._to_rgb(bgr)

    assert tuple(rgb[0, 0]) == (0, 0, 255)
