"""Live recognition test: match every frame against a user's templates without logging in."""

from __future__ import annotations

import enum
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import template_store
from .capture import FrameObserver, FrameReport, FrameState, FrameStream, normalized_boxes
from .detector_factory import PipelineBundle
from .interfaces import Face
from .pipeline import Pipeline
from .template_store import TemplateSpaceMismatch, TemplateStoreError

# How long a probe runs unless it is cancelled first
DEFAULT_DURATION_S = 15.0


class ProbeResult(enum.Enum):
    COMPLETED = "completed"  # ran for the whole duration
    NO_MODELS = "no_models"
    MODEL_MISMATCH = "model_mismatch"  # templates are from another recognizer
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ProbeOutcome:
    result: ProbeResult
    frames: int = 0
    matched_frames: int = 0
    # closest distance seen, on the config.ini certainty scale
    best_distance: float | None = None


class RecognitionProbe:
    """
    Report the match distance of every frame for a while, so a user can see how well their
    templates work and tune ``certainty``. Unlike :class:`AuthSession` it never stops at a
    match and has no side effects: no snapshots, rubberstamps or login result.
    """

    def __init__(
        self,
        config,
        bundle: PipelineBundle,
        on_frame: FrameObserver | None = None,
        stream_factory: Callable[..., Any] = FrameStream,
        duration_s: float = DEFAULT_DURATION_S,
    ) -> None:
        """
        :param config: the parsed config.ini
        :param bundle: the pipeline to match with
        :param on_frame: called with a FrameReport for every frame read; an observer that
            raises cancels the probe
        :param stream_factory: builds the FrameStream; tests pass a fake camera through it
        :param duration_s: how long to keep reading frames
        """
        self.config = config
        self.bundle = bundle
        self.on_frame = on_frame
        self.duration_s = duration_s
        self._stream_factory = stream_factory
        self._cancel_event = threading.Event()
        self._state_lock = threading.Lock()
        self._stream: FrameStream | None = None

    def cancel(self) -> None:
        """Request a stop and release the camera as soon as possible. Safe from any thread."""
        self._cancel_event.set()
        with self._state_lock:
            if self._stream is not None:
                self._stream.release()

    def run(self, user: str) -> ProbeOutcome:  # noqa: C901
        """
        Match frames against ``user``'s templates until the duration runs out.
        :param user: whose templates to match against
        :return: the outcome
        """
        try:
            templates = template_store.load(
                user, model_id=template_store.active_model_id(self.config)
            )
        except TemplateSpaceMismatch:
            return ProbeOutcome(ProbeResult.MODEL_MISMATCH)
        except TemplateStoreError:
            return ProbeOutcome(ProbeResult.NO_MODELS)

        certainty = self.config.getfloat("video", "certainty", fallback=3.5) / 10
        try:
            pipeline = Pipeline(self.bundle, templates, certainty)
        except ValueError:
            return ProbeOutcome(ProbeResult.MODEL_MISMATCH)

        stream = self._stream_factory(self.config)
        with self._state_lock:
            self._stream = stream
        # cancel() may have run before the stream existed
        if self._cancel_event.is_set():
            stream.release()

        started = time.time()
        frames = 0
        matched_frames = 0
        best: float | None = None

        try:
            while time.time() - started < self.duration_s:
                if self._cancel_event.is_set():
                    break
                try:
                    captured = stream.read()
                # VideoCapture still calls sys.exit() when a read fails
                except (Exception, SystemExit):
                    # reading a camera that cancel() just released
                    if self._cancel_event.is_set():
                        break
                    raise
                frames += 1

                if not captured.usable:
                    self._report(captured, captured.state, started)
                    continue

                faces = pipeline.detect(captured.gsframe)
                frame_best: float | None = None
                accepted = False
                for face in faces:
                    result = pipeline.match(captured.frame, face)
                    if result.row >= 0:
                        frame_best = (
                            result.distance
                            if frame_best is None
                            else min(frame_best, result.distance)
                        )
                    accepted = accepted or result.accepted

                if accepted:
                    state = FrameState.MATCH
                    matched_frames += 1
                elif not faces:
                    state = FrameState.NO_FACE
                else:
                    state = FrameState.MULTIPLE if len(faces) > 1 else FrameState.FACE
                if frame_best is not None:
                    best = frame_best if best is None else min(best, frame_best)

                self._report(captured, state, started, faces, frame_best, certainty)

            result = ProbeResult.CANCELLED if self._cancel_event.is_set() else ProbeResult.COMPLETED
            return ProbeOutcome(
                result,
                frames=frames,
                matched_frames=matched_frames,
                best_distance=None if best is None else best * 10,
            )
        finally:
            with self._state_lock:
                self._stream = None
            stream.release()

    def _report(
        self,
        captured,
        state: FrameState,
        started: float,
        faces: list[Face] | None = None,
        distance: float | None = None,
        certainty: float | None = None,
    ) -> None:
        if self.on_frame is None:
            return
        report = FrameReport(
            index=captured.index,
            elapsed=time.time() - started,
            state=state,
            darkness=captured.darkness,
            dark_threshold=self.config.getfloat("video", "dark_threshold", fallback=60.0),
            faces=normalized_boxes(faces or [], captured.frame),
            # Pipeline works on certainty / 10; report on the config.ini scale
            distance=None if distance is None else distance * 10,
            certainty=None if certainty is None else certainty * 10,
        )
        try:
            self.on_frame(report, captured.frame)
        except Exception:
            self.cancel()
