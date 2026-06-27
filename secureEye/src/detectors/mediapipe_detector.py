from pathlib import Path
from typing import List, Tuple
from urllib.request import urlopen

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision
from numpy.typing import NDArray

from .base import FaceDetector

FACE_DETECTOR_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
)
FACE_LANDMARKER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/latest/face_landmarker.task"
)
EMBEDDING_SIZE = 128


class MediaPipeDetector(FaceDetector):
    def __init__(self):
        model_dir = Path.home() / ".cache" / "secureeye" / "mediapipe"
        detector_model_path = self._ensure_model(
            FACE_DETECTOR_MODEL_URL,
            model_dir / "blaze_face_short_range.tflite",
        )
        landmarker_model_path = self._ensure_model(
            FACE_LANDMARKER_MODEL_URL,
            model_dir / "face_landmarker.task",
        )

        detector_options = vision.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=str(detector_model_path)),
            running_mode=vision.RunningMode.IMAGE,
            min_detection_confidence=0.5,
        )
        self.mp_detector = vision.FaceDetector.create_from_options(detector_options)

        landmarker_options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(landmarker_model_path)),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
        )
        self.mp_landmarker = vision.FaceLandmarker.create_from_options(landmarker_options)

    @staticmethod
    def _ensure_model(url: str, destination: Path) -> Path:
        if destination.is_file():
            return destination

        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urlopen(url, timeout=20) as response:
                destination.write_bytes(response.read())
        except Exception as exc:  # pragma: no cover - network-dependent path
            raise RuntimeError(f"Failed to download MediaPipe model from {url}: {exc}") from exc
        return destination

    @staticmethod
    def _to_rgb(frame: NDArray) -> NDArray[np.uint8]:
        if frame.ndim == 2:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    @staticmethod
    def _landmarks_to_embedding(landmarks) -> NDArray[np.float32]:
        raw = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float32).reshape(-1)
        raw = raw - np.mean(raw)
        std = float(np.std(raw))
        if std > 0:
            raw = raw / std

        if raw.size == EMBEDDING_SIZE:
            embedding = raw.astype(np.float32)
        else:
            src = np.linspace(0, raw.size - 1, num=raw.size, dtype=np.float32)
            dst = np.linspace(0, raw.size - 1, num=EMBEDDING_SIZE, dtype=np.float32)
            embedding = np.interp(dst, src, raw).astype(np.float32)

        norm = float(np.linalg.norm(embedding))
        if norm > 0:
            embedding = embedding / norm
        return embedding.astype(np.float32, copy=False)

    def detect(self, frame: NDArray) -> List[Tuple[int, int, int, int]]:
        frame_h, frame_w = frame.shape[:2]
        rgb_frame = self._to_rgb(frame)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        results = self.mp_detector.detect(image)
        boxes = []
        if results.detections:
            for det in results.detections:
                bbox = det.bounding_box
                x = max(0, int(bbox.origin_x))
                y = max(0, int(bbox.origin_y))
                w = max(0, min(int(bbox.width), frame_w - x))
                h = max(0, min(int(bbox.height), frame_h - y))
                if w > 0 and h > 0:
                    boxes.append((x, y, w, h))
        return boxes

    def encode(self, frame: NDArray, face_box: Tuple[int, int, int, int]) -> NDArray:
        x, y, w, h = face_box
        frame_h, frame_w = frame.shape[:2]
        x1, y1 = max(0, int(x)), max(0, int(y))
        x2, y2 = min(frame_w, x1 + max(0, int(w))), min(frame_h, y1 + max(0, int(h)))
        if x2 <= x1 or y2 <= y1:
            return np.zeros((EMBEDDING_SIZE,), dtype=np.float32)

        face_img = frame[y1:y2, x1:x2]
        if face_img.size == 0:
            return np.zeros((EMBEDDING_SIZE,), dtype=np.float32)

        rgb_face = self._to_rgb(face_img)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_face)
        result = self.mp_landmarker.detect(image)
        if not result.face_landmarks:
            return np.zeros((EMBEDDING_SIZE,), dtype=np.float32)

        return self._landmarks_to_embedding(result.face_landmarks[0])
