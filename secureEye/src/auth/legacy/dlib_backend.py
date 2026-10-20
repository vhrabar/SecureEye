"""
The dlib detect+encode path behind the :class:`Detector` / :class:`Recognizer` seam.

Both adapters wrap one already-loaded ``DlibDetector`` so the dlib models are
loaded once. Removed together with dlib at sunset.
"""

from __future__ import annotations

from typing import Any

import dlib
import numpy as np

from ..interfaces import Detector, Embedding, Face, Frame, Recognizer
from ..template_store import LEGACY_MODEL_ID

#: Length of a dlib ResNet face descriptor.
DLIB_DESCRIPTOR_DIM = 128


class DlibFaceDetector(Detector):
    """
    dlib HOG or CNN (MMOD) face detection.

    Faces carry no landmarks: dlib's 5-point shape is not the eyes/nose/mouth
    layout alignment expects, and :class:`DlibRecognizer` computes it itself.
    """

    def __init__(self, backend: Any) -> None:
        """
        :param backend: a loaded ``DlibDetector``
        """
        self._backend = backend

    def detect(self, frame: Frame) -> list[Face]:
        faces = []
        for found in self._backend.detector(frame, 1):
            # The CNN detector wraps the box with a confidence; HOG returns it bare.
            rect = getattr(found, "rect", found)
            score = float(getattr(found, "confidence", 1.0))
            faces.append(Face(bbox=_rect_to_bbox(rect), score=score))
        faces.sort(key=lambda face: face.score, reverse=True)
        return faces


class DlibRecognizer(Recognizer):
    """
    dlib ResNet face descriptors.

    Embeddings keep dlib's raw descriptor instead of L2-normalizing it: stored
    legacy templates and ``[video] certainty`` are calibrated on Euclidean
    distance between raw descriptors.
    """

    def __init__(self, backend: Any) -> None:
        """
        :param backend: a loaded ``DlibDetector``
        """
        self._backend = backend

    @property
    def model_id(self) -> str:
        return LEGACY_MODEL_ID

    @property
    def dim(self) -> int:
        return DLIB_DESCRIPTOR_DIM

    def embed(self, frame: Frame, face: Face) -> Embedding:
        shape = self._backend.pose_predictor(frame, _bbox_to_rect(face.bbox))
        descriptor = self._backend.face_encoder.compute_face_descriptor(frame, shape, 1)
        vector = np.asarray(descriptor, dtype=np.float32).ravel()
        return Embedding(vector=vector, model_id=self.model_id, dim=self.dim)


def _rect_to_bbox(rect: Any) -> tuple[int, int, int, int]:
    return (int(rect.left()), int(rect.top()), int(rect.width()), int(rect.height()))


def _bbox_to_rect(bbox: tuple[int, int, int, int]) -> Any:
    # dlib rectangles are inclusive on both ends: width() == right - left + 1.
    x, y, w, h = bbox
    return dlib.rectangle(x, y, x + w - 1, y + h - 1)
