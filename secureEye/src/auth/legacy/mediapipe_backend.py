"""
The MediaPipe detect+encode path behind the :class:`Detector` / :class:`Recognizer` seam.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..interfaces import Detector, Embedding, Face, Frame, Recognizer
from ..template_store import LEGACY_MODEL_IDS

#: Length of a MediaPipe landmark embedding.
MEDIAPIPE_EMBEDDING_DIM = 128


class MediaPipeFaceDetector(Detector):
    """
    MediaPipe BlazeFace detection. Boxes are already ``(x, y, w, h)``.
    """

    def __init__(self, backend: Any) -> None:
        """
        :param backend: a loaded ``MediaPipeDetector``
        """
        self._backend = backend

    def detect(self, frame: Frame) -> list[Face]:
        return [
            Face(bbox=(int(x), int(y), int(w), int(h)))
            for x, y, w, h in self._backend.detect(frame)
        ]


class MediaPipeRecognizer(Recognizer):
    """
    MediaPipe landmark embeddings, kept raw like the stored templates.
    """

    def __init__(self, backend: Any) -> None:
        """
        :param backend: a loaded ``MediaPipeDetector``
        """
        self._backend = backend

    @property
    def model_id(self) -> str:
        return LEGACY_MODEL_IDS["mediapipe"]

    @property
    def dim(self) -> int:
        return MEDIAPIPE_EMBEDDING_DIM

    def embed(self, frame: Frame, face: Face) -> Embedding:
        vector = np.asarray(self._backend.encode(frame, face.bbox), dtype=np.float32).ravel()
        return Embedding(vector=vector, model_id=self.model_id, dim=self.dim)
