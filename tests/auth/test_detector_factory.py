import sys
from configparser import ConfigParser
from pathlib import Path
from types import ModuleType

import pytest

# Path setup
SRC_DIR = str(Path(__file__).resolve().parents[2] / "secureEye" / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from auth import detector_factory  # noqa: E402
from auth.detector_factory import DetectorFactoryError, create_pipeline  # noqa: E402
from auth.interfaces import Detector, Recognizer  # noqa: E402
from auth.template_store import LEGACY_MODEL_IDS  # noqa: E402


@pytest.fixture(autouse=True)
def _empty_cache(monkeypatch):
    monkeypatch.setattr(detector_factory, "_pipeline_cache", {})


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


class FakeDlibDetector:
    def __init__(self, cnn=False):
        self.cnn = cnn
        self.detector = object()
        self.pose_predictor = object()


def _install_fake_dlib(monkeypatch):
    monkeypatch.setitem(sys.modules, "dlib", ModuleType("dlib"))
    monkeypatch.delitem(sys.modules, "auth.legacy.dlib_backend", raising=False)
    _install_detector_module(
        monkeypatch, "detectors.dlib_detector", "DlibDetector", FakeDlibDetector
    )


def test_dlib_builds_legacy_pipeline(monkeypatch):
    _install_fake_dlib(monkeypatch)

    bundle = create_pipeline(_make_config(backend="dlib", use_cnn=True))

    assert bundle.backend == "dlib"
    assert isinstance(bundle.detector, Detector)
    assert isinstance(bundle.recognizer, Recognizer)
    assert bundle.recognizer.model_id == LEGACY_MODEL_IDS["dlib"]
    assert bundle.liveness is None


def test_dlib_stages_share_one_backend_and_expose_legacy_handles(monkeypatch):
    _install_fake_dlib(monkeypatch)

    bundle = create_pipeline(_make_config(backend="dlib", use_cnn=True))

    backend = bundle.detector._backend
    assert backend.cnn is True
    assert bundle.recognizer._backend is backend
    assert bundle.legacy_face_detector is backend.detector
    assert bundle.legacy_pose_predictor is backend.pose_predictor


def test_mediapipe_builds_legacy_pipeline(monkeypatch):
    class FakeMediaPipeDetector:
        pass

    _install_detector_module(
        monkeypatch,
        "detectors.mediapipe_detector",
        "MediaPipeDetector",
        FakeMediaPipeDetector,
    )

    bundle = create_pipeline(_make_config(backend="mediapipe"))

    assert bundle.backend == "mediapipe"
    assert isinstance(bundle.detector, Detector)
    assert isinstance(bundle.recognizer, Recognizer)
    assert bundle.recognizer.model_id == LEGACY_MODEL_IDS["mediapipe"]
    assert bundle.legacy_face_detector is None
    assert bundle.legacy_pose_predictor is None


def test_pipeline_is_cached_per_config(monkeypatch):
    _install_fake_dlib(monkeypatch)

    first = create_pipeline(_make_config(backend="dlib"))

    assert create_pipeline(_make_config(backend="dlib")) is first
    assert create_pipeline(_make_config(backend="dlib", use_cnn=True)) is not first


def test_unsupported_backend_raises_factory_error():
    with pytest.raises(DetectorFactoryError, match="Unsupported detector backend"):
        create_pipeline(_make_config(backend="unknown"))
