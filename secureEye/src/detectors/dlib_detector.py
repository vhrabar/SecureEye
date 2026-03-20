from typing import Tuple, List

import dlib
import numpy as np
from numpy.typing import NDArray
from .base import FaceDetector


class DlibDetector(FaceDetector):
    def __init__(self, cnn=False):
        if cnn:
            self.detector = dlib.cnn_face_detection_model_v1("mmod_human_face_detector.dat")
        else:
            self.detector = dlib.get_frontal_face_detector()
        self.pose_predictor = dlib.shape_predictor("shape_predictor_5_face_landmarks.dat")
        self.face_encoder = dlib.face_recognition_model_v1(
            "dlib_face_recognition_resnet_model_v1.dat"
        )

    def detect(self, frame: NDArray) -> List[Tuple[int, int, int, int]]:
        faces = self.detector(frame, 1)
        return [f.rect if hasattr(f, "rect") else f for f in faces]

    def encode(self, frame: NDArray, face_box: Tuple[int, int, int, int]) -> NDArray:
        shape = self.pose_predictor(frame, face_box)
        return np.array(self.face_encoder.compute_face_descriptor(frame, shape, 1))
