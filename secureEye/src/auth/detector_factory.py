"""Pipeline backend factory for auth sessions."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from .interfaces import Detector, LivenessCheck, Recognizer


class DetectorFactoryError(RuntimeError):
    """Raised when a pipeline backend cannot be initialized."""


# cache built pipelines
_pipeline_cache: dict[tuple, PipelineBundle] = {}
_pipeline_cache_lock = threading.Lock()


def _cache_key(config) -> tuple:
    backend = config.get("core", "detector_backend", fallback="dlib").strip().lower()
    use_cnn = config.getboolean("core", "use_cnn", fallback=False)
    return (backend, use_cnn)


@dataclass
class PipelineBundle:
    """
    The stages one auth session runs, all behind the pipeline interfaces.

    ``legacy_face_detector`` / ``legacy_pose_predictor`` are the raw dlib
    handles rubberstamps still needs; ``None`` on other backends.
    """

    backend: str
    detector: Detector
    recognizer: Recognizer
    liveness: LivenessCheck | None = None
    legacy_face_detector: Any | None = None
    legacy_pose_predictor: Any | None = None


def _is_missing_module(exc: ModuleNotFoundError, *candidates: str) -> bool:
    return getattr(exc, "name", "") in candidates


def create_pipeline(config) -> PipelineBundle:
    """Return the pipeline for ``config``, building it once and caching it.

    The first call for a given backend configuration builds the backend; every
    subsequent call reuses the cached bundle.
    """
    key = _cache_key(config)
    with _pipeline_cache_lock:
        cached = _pipeline_cache.get(key)
        if cached is not None:
            return cached
        bundle = _build_pipeline(config)
        _pipeline_cache[key] = bundle
        return bundle


def _build_pipeline(config) -> PipelineBundle:
    """Create a pipeline from config.

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
        from .legacy.dlib_backend import DlibFaceDetector, DlibRecognizer

        use_cnn = config.getboolean("core", "use_cnn", fallback=False)
        dlib_detector = DlibDetector(cnn=use_cnn)
        return PipelineBundle(
            backend="dlib",
            detector=DlibFaceDetector(dlib_detector),
            recognizer=DlibRecognizer(dlib_detector),
            legacy_face_detector=dlib_detector.detector,
            legacy_pose_predictor=dlib_detector.pose_predictor,
        )

    if backend == "mediapipe":
        try:
            from detectors.mediapipe_detector import MediaPipeDetector
        except ModuleNotFoundError as exc:
            if not _is_missing_module(exc, "detectors", "detectors.mediapipe_detector"):
                raise
            from secureEye.src.detectors.mediapipe_detector import MediaPipeDetector
        from .legacy.mediapipe_backend import MediaPipeFaceDetector, MediaPipeRecognizer

        mp_detector = MediaPipeDetector()
        return PipelineBundle(
            backend="mediapipe",
            detector=MediaPipeFaceDetector(mp_detector),
            recognizer=MediaPipeRecognizer(mp_detector),
        )

    raise DetectorFactoryError(f"Unsupported detector backend: {backend}")
