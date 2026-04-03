"""Config-driven detector entrypoint.

Keep backend imports lazy so optional dependencies are loaded only when selected.
"""

from .base import FaceDetector


class Detector(FaceDetector):
    def __init__(self, config):
        backend = config.get("core", "detector_backend", fallback="dlib").strip().lower()
        self.backend = backend

        if backend == "dlib":
            use_cnn = config.getboolean("core", "use_cnn", fallback=False)
            from .dlib_detector import DlibDetector

            self._detector = DlibDetector(cnn=use_cnn)
            return

        if backend == "mediapipe":
            from .mediapipe_detector import MediaPipeDetector

            self._detector = MediaPipeDetector()
            return

        raise RuntimeError(f"Unsupported detector backend: {backend}")

    def detect(self, frame):
        return self._detector.detect(frame)

    def encode(self, frame, face_box):
        return self._detector.encode(frame, face_box)


__all__ = ["Detector"]
