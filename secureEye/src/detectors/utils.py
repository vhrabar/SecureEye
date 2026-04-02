import cv2
import numpy as np


def preprocess_face(face_img: np.ndarray, size=(160, 160)) -> np.ndarray:
    """
    Resize, convert color, and normalize a face for FaceNet.
    Returns a batch of shape (1, H, W, C)
    """
    face_resized = cv2.resize(face_img, size)
    face_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
    face_float = face_rgb.astype("float32")
    face_norm = (face_float - 127.5) / 128.0
    return np.expand_dims(face_norm, axis=0)
