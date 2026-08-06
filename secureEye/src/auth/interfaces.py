from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Face:
    bbox: tuple[int, int, int, int]
    landmarks: np.ndarray
    score: float


@dataclass
class LivenessResult:
    passed: bool
    score: float
    detail: str = ""


class LivenessCheck(ABC):
    @abstractmethod
    def check(self, frame, face: Face) -> LivenessResult: ...


class Detector(ABC):
    @abstractmethod
    def detect(self, frame) -> list[Face]:
        pass


@dataclass(frozen=True)
class Embedding:
    vector: np.ndarray
    model_id: str
    dim: int

    def cosine(self, other: "Embedding") -> float:
        if self.model_id != other.model_id:
            raise ValueError(f"embedding space mismatch: {self.model_id} vs {other.model_id}")
        return float(self.vector @ other.vector)


class Recognizer(ABC):
    @abstractmethod
    def embed(self, aligned_112: np.ndarray) -> Embedding:
        pass

    model_id: str
    dim: int
