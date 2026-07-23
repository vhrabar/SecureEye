"""Detector backend factory for auth sessions."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


class DetectorFactoryError(RuntimeError):
    """Raised when a detector backend cannot be initialized."""


# cache build detector
_detector_cache: dict[tuple, DetectorBundle] = {}
_detector_cache_lock = threading.Lock()


def _cache_key(config) -> tuple:
    backend = config.get("core", "detector_backend", fallback="dlib").strip().lower()
    use_cnn = config.getboolean("core", "use_cnn", fallback=False)
    return (backend, use_cnn)


@dataclass
class DetectorBundle:
    backend: str
    detector: Any
    legacy_face_detector: Any | None = None
    legacy_pose_predictor: Any | None = None


def _is_missing_module(exc: ModuleNotFoundError, *candidates: str) -> bool:
    return getattr(exc, "name", "") in candidates


def create_detector(config) -> DetectorBundle:
    """Return a detector backend for ``config``, building it once and caching it.

    The first call for a given backend configuration builds the backend; every
    subsequent call reuses the cached bundle.
    """
    key = _cache_key(config)
    with _detector_cache_lock:
        cached = _detector_cache.get(key)
        if cached is not None:
            return cached
        bundle = _build_detector(config)
        _detector_cache[key] = bundle
        return bundle


def _build_detector(config) -> DetectorBundle:
    """Create a detector backend from config.

    Supported values for [core] detector_backend:
    - dlib (default)
    - mediapipe
    """
    backend = config.get("core", "detector_backend", fallback="dlib").strip().lower()

    if backend == "dlib":
        try:
            from detectors.dlib_detector import DlibDetector
        except ModuleNotFoundError as exc:
            if not _is_missing_module(exc, "detectors", "detectors.dlib_detector"):
                raise
            from secureEye.src.detectors.dlib_detector import DlibDetector

        use_cnn = config.getboolean("core", "use_cnn", fallback=False)
        detector = DlibDetector(cnn=use_cnn)
        return DetectorBundle(
            backend="dlib",
            detector=detector,
            legacy_face_detector=detector.detector,
            legacy_pose_predictor=detector.pose_predictor,
        )

    if backend == "mediapipe":
        try:
            from detectors.mediapipe_detector import MediaPipeDetector
        except ModuleNotFoundError as exc:
            if not _is_missing_module(exc, "detectors", "detectors.mediapipe_detector"):
                raise
            from secureEye.src.detectors.mediapipe_detector import MediaPipeDetector

        detector = MediaPipeDetector()
        return DetectorBundle(backend="mediapipe", detector=detector)

    raise DetectorFactoryError(f"Unsupported detector backend: {backend}")
