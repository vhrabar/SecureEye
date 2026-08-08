import sys
from configparser import ConfigParser
from pathlib import Path
from types import ModuleType

import pytest

# Path setup
SRC_DIR = str(Path(__file__).resolve().parents[2] / "secureEye" / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from auth.detector_factory import DetectorFactoryError, create_detector  # noqa: E402


def _make_config(*, backend: str, use_cnn: bool = False) -> ConfigParser:
    config = ConfigParser()
    config.read_dict(
        {
            "core": {
                "detector_backend": backend,
                "use_cnn": "true" if use_cnn else "false",
            }
        }
    )
    return config


def _install_detector_module(monkeypatch, module_name: str, class_name: str, cls):
    detectors_pkg = ModuleType("detectors")
    detectors_pkg.__path__ = []
    detector_module = ModuleType(module_name)
    setattr(detector_module, class_name, cls)

    monkeypatch.setitem(sys.modules, "detectors", detectors_pkg)
    monkeypatch.setitem(sys.modules, module_name, detector_module)


def test_dlib_initializes_and_populates_legacy_handles(monkeypatch):
    class FakeDlibDetector:
        def __init__(self, cnn=False):
            self.cnn = cnn
            self.detector = object()
            self.pose_predictor = object()

    _install_detector_module(
        monkeypatch, "detectors.dlib_detector", "DlibDetector", FakeDlibDetector
    )

    bundle = create_detector(_make_config(backend="dlib", use_cnn=True))

    assert bundle.backend == "dlib"
    assert bundle.detector.cnn is True
    assert bundle.legacy_face_detector is bundle.detector.detector
    assert bundle.legacy_pose_predictor is bundle.detector.pose_predictor


def test_mediapipe_initializes(monkeypatch):
    class FakeMediaPipeDetector:
        pass

    _install_detector_module(
        monkeypatch,
        "detectors.mediapipe_detector",
        "MediaPipeDetector",
        FakeMediaPipeDetector,
    )

    bundle = create_detector(_make_config(backend="mediapipe"))

    assert bundle.backend == "mediapipe"
    assert isinstance(bundle.detector, FakeMediaPipeDetector)
    assert bundle.legacy_face_detector is None
    assert bundle.legacy_pose_predictor is None


def test_unsupported_backend_raises_factory_error():
    with pytest.raises(DetectorFactoryError, match="Unsupported detector backend"):
        create_detector(_make_config(backend="unknown"))
