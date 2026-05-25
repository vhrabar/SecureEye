"""Distance-based face matching helpers."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def best_match(known_encodings: NDArray[np.float32], face_encoding: NDArray[np.float32]) -> tuple[int, float]:
    """Return (best_index, distance) for the nearest known encoding."""
    matches = np.linalg.norm(known_encodings - face_encoding, axis=1)
    match_index = int(np.argmin(matches))
    return match_index, float(matches[match_index])


def is_match(distance: float, threshold: float) -> bool:
    """Return whether a measured distance is accepted as a positive match."""
    return 0.0 < distance < threshold
