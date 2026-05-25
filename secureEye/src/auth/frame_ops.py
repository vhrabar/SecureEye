"""Frame preprocessing helpers used by compare flow."""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray


def darkness_percent(gsframe: NDArray[np.uint8]) -> tuple[float, float]:
    """Return (darkness_percent, histogram_total) based on the darkest 1/8 bin."""
    hist = cv2.calcHist([gsframe], [0], None, [8], [0, 256])
    hist_total = float(np.sum(hist))
    if hist_total == 0.0:
        return 100.0, 0.0
    darkness = float(hist[0] / hist_total * 100)
    return darkness, hist_total


def maybe_scale(frame: NDArray, gsframe: NDArray, scaling_factor: float) -> tuple[NDArray, NDArray]:
    """Scale color and grayscale frames if needed."""
    if scaling_factor == 1:
        return frame, gsframe

    frame = cv2.resize(frame, None, fx=scaling_factor, fy=scaling_factor, interpolation=cv2.INTER_AREA)
    gsframe = cv2.resize(gsframe, None, fx=scaling_factor, fy=scaling_factor, interpolation=cv2.INTER_AREA)
    return frame, gsframe


def apply_rotation_mode(
        frame: NDArray,
        gsframe: NDArray,
        rotate_mode: int,
        frame_number: int,
) -> tuple[NDArray, NDArray]:
    """Rotate frames according to SecureEye rotate config semantics."""
    if rotate_mode == 1:
        if frame_number % 3 == 1:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            gsframe = cv2.rotate(gsframe, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif frame_number % 3 == 2:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            gsframe = cv2.rotate(gsframe, cv2.ROTATE_90_CLOCKWISE)
    elif rotate_mode == 2:
        if frame_number % 2 == 0:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            gsframe = cv2.rotate(gsframe, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            gsframe = cv2.rotate(gsframe, cv2.ROTATE_90_CLOCKWISE)

    return frame, gsframe
