"""Capturing a new face template from the camera, usable from the CLI and from authd."""

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
from .interfaces import Embedding, Face, Frame

# Frames to look at before giving up
MAX_FRAMES = 60


class EnrollResult(enum.Enum):
    SUCCESS = "success"
    NO_FACE = "no_face"  # usable frames, but nobody in them
    MULTIPLE_FACES = "multiple_faces"  # can't tell which face belongs to the user
    TOO_DARK = "too_dark"  # every lit frame was over dark_threshold
    BLACK_FRAMES = "black_frames"  # nothing but black reads, e.g. IR emitter off
    MODEL_MISMATCH = "model_mismatch"  # recognizer doesn't produce the configured space
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class EnrollOutcome:
    result: EnrollResult
    embedding: Embedding | None = None
    template: template_store.Template | None = None
    valid_frames: int = 0
    dark_tries: int = 0
    avg_darkness: float = 0.0


class EnrollSession:
    """
    Capture one face and, through :meth:`run`, store it as a template.

    Nothing is written unless the whole capture succeeds, and the template store writes
    atomically, so a cancelled or failed enrollment never leaves a partial model behind.
    """

    def __init__(
        self,
        config,
        bundle: PipelineBundle,
        on_frame: FrameObserver | None = None,
        stream_factory: Callable[..., Any] = FrameStream,
        max_frames: int = MAX_FRAMES,
    ) -> None:
        """
        :param config: the parsed config.ini
        :param bundle: the pipeline whose detector and recognizer produce the template
        :param on_frame: called with a FrameReport for every frame read; an observer that
            raises cancels the session
        :param stream_factory: builds the FrameStream; tests pass a fake camera through it
        :param max_frames: frames to read before giving up
        """
        self.config = config
        self.bundle = bundle
        self.on_frame = on_frame
        self.max_frames = max_frames
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

    def run(self, user: str, label: str, replace: bool = False) -> EnrollOutcome:
        """
        Capture a face and save it as a template for ``user``.
        :param user: the user to enroll
        :param label: the label of the new template
        :param replace: replace the user's templates in the active space (re-enroll) instead
            of adding one
        :return: the outcome; ``template`` is set only on success
        """
        model_id = template_store.active_model_id(self.config)
        if self.bundle.recognizer.model_id != model_id:
            return EnrollOutcome(EnrollResult.MODEL_MISMATCH)

        outcome = self.capture()
        if outcome.result is not EnrollResult.SUCCESS:
            return outcome
        # a cancel that lands after the capture still must not write anything
        if self._cancel_event.is_set():
            return EnrollOutcome(EnrollResult.CANCELLED)

        assert outcome.embedding is not None
        store = template_store.replace_space if replace else template_store.append
        template = store(user, model_id=model_id, label=label, embeddings=outcome.embedding.vector)
        return EnrollOutcome(
            EnrollResult.SUCCESS,
            embedding=outcome.embedding,
            template=template,
            valid_frames=outcome.valid_frames,
            dark_tries=outcome.dark_tries,
            avg_darkness=outcome.avg_darkness,
        )

    def capture(self, settle_s: float = 0.0) -> EnrollOutcome:  # noqa: C901
        """
        Read frames until exactly one face shows up, and embed it. Writes nothing.
        :param settle_s: time to wait after opening the camera, e.g. for the user to get ready
        :return: the outcome; ``embedding`` is set only on success
        """
        stream = self._stream_factory(self.config, transform=False)
        with self._state_lock:
            self._stream = stream
        # cancel() may have run before the stream existed
        if self._cancel_event.is_set():
            stream.release()

        started = time.time()
        valid_frames = 0
        dark_tries = 0
        dark_total = 0.0
        faces: list[Face] = []
        frame: Frame | None = None

        try:
            if settle_s > 0 and self._cancel_event.wait(settle_s):
                return EnrollOutcome(EnrollResult.CANCELLED)

            for _ in range(self.max_frames):
                if self._cancel_event.is_set():
                    return EnrollOutcome(EnrollResult.CANCELLED)

                try:
                    captured = stream.read()
                # VideoCapture still calls sys.exit() when a read fails
                except (Exception, SystemExit):
                    # reading a camera that cancel() just released
                    if self._cancel_event.is_set():
                        return EnrollOutcome(EnrollResult.CANCELLED)
                    raise
                frame = captured.frame

                if captured.state is FrameState.BLACK:
                    self._report(captured.index, FrameState.BLACK, captured, started, [])
                    continue

                dark_total += captured.darkness
                valid_frames += 1

                if captured.state is FrameState.DARK:
                    dark_tries += 1
                    self._report(captured.index, FrameState.DARK, captured, started, [])
                    continue

                faces = list(self.bundle.detector.detect(captured.gsframe))
                if not faces:
                    state = FrameState.NO_FACE
                elif len(faces) > 1:
                    state = FrameState.MULTIPLE
                else:
                    state = FrameState.FACE
                self._report(captured.index, state, captured, started, faces)

                if faces:
                    break

            if self._cancel_event.is_set():
                return EnrollOutcome(EnrollResult.CANCELLED)

            stats = {
                "valid_frames": valid_frames,
                "dark_tries": dark_tries,
                "avg_darkness": dark_total / valid_frames if valid_frames else 0.0,
            }
            if not faces:
                if valid_frames == 0:
                    return EnrollOutcome(EnrollResult.BLACK_FRAMES, **stats)
                if valid_frames == dark_tries:
                    return EnrollOutcome(EnrollResult.TOO_DARK, **stats)
                return EnrollOutcome(EnrollResult.NO_FACE, **stats)
            if len(faces) > 1:
                return EnrollOutcome(EnrollResult.MULTIPLE_FACES, **stats)

            assert frame is not None
            embedding = self.bundle.recognizer.embed(frame, faces[0])
            return EnrollOutcome(EnrollResult.SUCCESS, embedding=embedding, **stats)
        finally:
            with self._state_lock:
                self._stream = None
            stream.release()

    def _report(
        self,
        index: int,
        state: FrameState,
        captured,
        started: float,
        faces: list[Face],
    ) -> None:
        if self.on_frame is None:
            return
        report = FrameReport(
            index=index,
            elapsed=time.time() - started,
            state=state,
            darkness=captured.darkness,
            dark_threshold=self.config.getfloat("video", "dark_threshold", fallback=60.0),
            faces=normalized_boxes(faces, captured.frame),
        )
        try:
            self.on_frame(report, captured.frame)
        except Exception:
            self.cancel()
