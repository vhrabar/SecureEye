from typing import List, Tuple

import cv2
import mediapipe as mp
from numpy.typing import NDArray
from keras.models import load_model

from .base import FaceDetector
from .utils import preprocess_face


class MediaPipeDetector(FaceDetector):
    def __init__(self):
        self.facenet_model = load_model("facenet_keras.h5")
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
        x, y, w, h = face_box
        face_img = frame[y : y + h, x : x + w]
        face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        face_input = preprocess_face(face_img)
        embedding = self.facenet_model.predict(face_input)
        return embedding[0]
