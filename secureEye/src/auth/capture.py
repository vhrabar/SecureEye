"""Camera frame acquisition and per-frame status reports shared by auth and enrollment sessions."""

from __future__ import annotations

import enum
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import cv2

from recorders.video_capture import VideoCapture
from .frame_ops import apply_rotation_mode, darkness_percent, maybe_scale
from .interfaces import Face, Frame


class FrameState(enum.Enum):
    BLACK = "black"  # bad read or IR emitter off; not even counted as a valid frame
    DARK = "dark"  # above dark_threshold, skipped before detection
    NO_FACE = "no_face"
    MULTIPLE = "multiple"
    FACE = "face"  # exactly one face, not (or not yet) accepted
    MATCH = "match"  # a face was accepted against the user's templates


@dataclass(frozen=True)
class CapturedFrame:
    """
    One frame read from the camera.

    ``frame`` / ``gsframe`` are scaled and rotated only when ``usable``; for black and dark
    frames they are the raw colour frame and its contrast-enhanced grayscale copy.
    """

    index: int
    raw: Frame
    frame: Frame
    gsframe: Frame
    darkness: float
    state: FrameState | None  # BLACK or DARK, None when the frame is usable

    @property
    def usable(self) -> bool:
        return self.state is None


@dataclass(frozen=True)
class FrameReport:
    """
    What a session saw in one frame, for live feedback in the GUI.

    ``faces`` are ``(x, y, width, height)`` boxes normalised to 0..1 of the reported frame, so
    they can be drawn over a preview of any size. ``distance`` and ``certainty`` use the
    ``[video] certainty`` scale from config.ini (lower is a closer match).
    """

    index: int
    elapsed: float
    state: FrameState
    darkness: float
    dark_threshold: float
    faces: tuple[tuple[float, float, float, float], ...] = ()
    distance: float | None = None
    certainty: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "elapsed": round(self.elapsed, 3),
            "state": self.state.value,
            "darkness": round(self.darkness, 1),
            "dark_threshold": self.dark_threshold,
            "faces": [[round(v, 4) for v in box] for box in self.faces],
            "distance": None if self.distance is None else round(self.distance, 3),
            "certainty": self.certainty,
        }


#: Called once per frame with the report and the frame it describes. Runs on the session thread.
FrameObserver = Callable[[FrameReport, Frame], None]


def normalized_boxes(
    faces: Sequence[Face], frame: Frame
) -> tuple[tuple[float, float, float, float], ...]:
    """
    Convert pixel face boxes to 0..1 fractions of ``frame``.
    :param faces: detected faces, boxes in ``frame`` pixels
    :param frame: the frame the faces were detected in
    :return: one ``(x, y, width, height)`` tuple per face
    """
    height, width = frame.shape[:2]
    if not width or not height:
        return ()
    return tuple(
        (x / width, y / height, w / width, h / height) for x, y, w, h in (f.bbox for f in faces)
    )


class FrameStream:
    """
    Owns the camera for one session and turns raw reads into :class:`CapturedFrame` objects.

    ``release()`` may be called from another thread to abort a session; the camera is let go
    at most once.
    """

    def __init__(
        self,
        config,
        capture_factory: Callable[[Any], Any] = VideoCapture,
        transform: bool = True,
    ) -> None:
        """
        :param config: the parsed config.ini
        :param capture_factory: builds the camera reader; tests pass a fake
        :param transform: scale and rotate usable frames as configured; enrollment turns this
            off and works on the native frame
        """
        self.dark_threshold = config.getfloat("video", "dark_threshold", fallback=60.0)
        self._rotate = config.getint("video", "rotate", fallback=0)
        self._transform = transform
        self._index = 0
        self._lock = threading.Lock()
        self._released = False

        self.video_capture = capture_factory(config)
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        max_height = config.getfloat("video", "max_height", fallback=320.0)
        prop = cv2.CAP_PROP_FRAME_WIDTH if self._rotate == 2 else cv2.CAP_PROP_FRAME_HEIGHT
        self.native_height = self.video_capture.internal.get(prop) or 1
        self._scaling_factor = (max_height / self.native_height) or 1

    def read(self) -> CapturedFrame:
        """
        Read and preprocess the next frame.
        :return: the captured frame
        """
        self._index += 1
        raw, gsframe = self.video_capture.read_frame()
        gsframe = self.clahe.apply(gsframe)

        darkness, hist_total = darkness_percent(gsframe)
        if hist_total == 0 or darkness == 100:
            return CapturedFrame(self._index, raw, raw, gsframe, darkness, FrameState.BLACK)
        if darkness > self.dark_threshold:
            return CapturedFrame(self._index, raw, raw, gsframe, darkness, FrameState.DARK)

        frame = raw
        if self._transform:
            frame, gsframe = maybe_scale(frame, gsframe, self._scaling_factor)
            frame, gsframe = apply_rotation_mode(frame, gsframe, self._rotate, self._index)
        return CapturedFrame(self._index, raw, frame, gsframe, darkness, None)

    def release(self) -> None:
        """
        Let go of the camera. Safe to call more than once and from any thread.
        :return: None
        """
        with self._lock:
            if self._released:
                return
            self._released = True
        try:
            self.video_capture.release()
        except Exception:
            pass
