"""Detector backends package.

Keep imports lazy to avoid importing optional backend dependencies at package import time.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .dlib_detector import DlibDetector
    from .mediapipe_detector import MediaPipeDetector

__all__ = ["DlibDetector", "MediaPipeDetector"]
