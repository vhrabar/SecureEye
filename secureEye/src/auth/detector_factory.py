"""Detector backend factory for auth sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class DetectorFactoryError(RuntimeError):
    """Raised when a detector backend cannot be initialized."""


@dataclass
class DetectorBundle:
    backend: str
    detector: Any
    legacy_face_detector: Any | None = None
    legacy_pose_predictor: Any | None = None


def _is_missing_module(exc: ModuleNotFoundError, *candidates: str) -> bool:
    return getattr(exc, "name", "") in candidates


def create_detector(config) -> DetectorBundle:
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
