from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

#: A captured video frame, colour (H, W, 3) or grayscale (H, W).
Frame: TypeAlias = NDArray[np.uint8]

#: Facial landmarks as (N, 2) image coordinates
Landmarks: TypeAlias = NDArray[np.float32]

#: A face template in some recognizer's embedding space.
Vector: TypeAlias = NDArray[np.float32]


def _no_landmarks() -> Landmarks:
    return np.empty((0, 2), dtype=np.float32)


@dataclass(frozen=True)
class Face:
    """
    One detected face: its box, optional landmarks and detector confidence.
    """

    bbox: tuple[int, int, int, int]
    landmarks: Landmarks = field(default_factory=_no_landmarks, compare=False)
    score: float = 1.0

    def __post_init__(self) -> None:
        if self.landmarks.ndim != 2 or self.landmarks.shape[1] != 2:
            raise ValueError(f"landmarks must have shape (N, 2), got {self.landmarks.shape}")

    @property
    def has_landmarks(self) -> bool:
        return self.landmarks.shape[0] > 0


@dataclass
class LivenessResult:
    passed: bool
    score: float
    detail: str = ""


@dataclass(frozen=True, eq=False)
class Embedding:
    """
    An L2-normalized face template, tagged with the space it lives in.
    """

    vector: Vector
    model_id: str
    dim: int

    def __post_init__(self) -> None:
        if self.vector.ndim != 1:
            raise ValueError(f"embedding must be 1-D, got shape {self.vector.shape}")
        if self.vector.shape[0] != self.dim:
            raise ValueError(f"embedding has {self.vector.shape[0]} values, expected {self.dim}")

    @classmethod
    def normalized(cls, vector: NDArray[np.floating], model_id: str) -> "Embedding":
        """
        Build an :class:`Embedding` from a raw vector, L2-normalizing it.
        """
        flat = np.asarray(vector, dtype=np.float32).ravel()
        norm = float(np.linalg.norm(flat))
        if norm == 0.0:
            raise ValueError("cannot normalize a zero-length embedding")
        return cls(vector=flat / norm, model_id=model_id, dim=flat.shape[0])

    def cosine(self, other: "Embedding") -> float:
        """
        Cosine similarity in [-1, 1]
        """
        if self.model_id != other.model_id:
            raise ValueError(f"embedding space mismatch: {self.model_id} vs {other.model_id}")
        return float(np.clip(self.vector @ other.vector, -1.0, 1.0))


class Detector(ABC):
    """
    Locates faces in a frame. Does not recognize them.
    """

    @abstractmethod
    def detect(self, frame: Frame) -> list[Face]:
        """
        Return every face found in ``frame``, strongest first.
        """


class Recognizer(ABC):
    """
    Turns a detected face into a comparable template.
    """

    @property
    @abstractmethod
    def model_id(self) -> str:
        """
        Identifier of the embedding spac.
        """

    @property
    @abstractmethod
    def dim(self) -> int:
        """
        Length of the vectors produced by :meth:`embed`.
        """

    @abstractmethod
    def embed(self, frame: Frame, face: Face) -> Embedding:
        """
        Return an L2-normalized template for ``face`` as seen in ``frame``.
        """


class LivenessCheck(ABC):
    """
    Decides whether a detected face belongs to a live person.
    """

    @abstractmethod
    def check(self, frame: Frame, face: Face) -> LivenessResult: ...
