from typing import List, Tuple

import mediapipe as mp
import numpy as np
from numpy.typing import NDArray
from .base import FaceDetector


class MediaPipeDetector(FaceDetector):
    def __init__(self):
        self.mp_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=1, min_detection_confidence=0.5
        )

    def detect(self, frame: NDArray) -> List[Tuple[int, int, int, int]]:
        results = self.mp_detector.process(frame)
        boxes = []
        if results.detections:
            for det in results.detections:
                # Convert mediapipe box to (x, y, w, h) format
                bbox = det.location_data.relative_bounding_box
                h, w, _ = frame.shape
                boxes.append(
                    (
                        int(bbox.xmin * w),
                        int(bbox.ymin * h),
                        int(bbox.width * w),
                        int(bbox.height * h),
                    )
                )
        return boxes

    def encode(self, frame: NDArray, face_box: Tuple[int, int, int, int]) -> NDArray:
        return np.zeros(128)  # TODO: implement proper encooding
