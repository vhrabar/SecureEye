"""
Per-frame recognition: detect -> liveness -> recognize -> match.

Everything goes through the :class:`PipelineBundle` stages, so this module
never knows which backend is running.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass

from .detector_factory import PipelineBundle
from .interfaces import Face, Frame, LivenessResult
from .matching import best_match, is_match
from .template_store import Template, TemplateSet


@dataclass(frozen=True)
class FaceMatch:
    """
    The outcome for one detected face.

    ``row`` / ``distance`` refer to the nearest row of ``TemplateSet.matrix``;
    a face that failed liveness was never embedded, so it has ``row == -1``
    and an infinite distance.
    """

    face: Face
    row: int
    distance: float
    accepted: bool
    liveness: LivenessResult | None = None


class Pipeline:
    """
    Matches faces in frames against one user's templates.
    """

    def __init__(self, bundle: PipelineBundle, templates: TemplateSet, threshold: float) -> None:
        """
        :param bundle: the stages to run
        :param templates: the user's templates, in the recognizer's embedding space
        :param threshold: largest distance still accepted as a match
        """
        if templates.model_id != bundle.recognizer.model_id:
            raise ValueError(
                f"templates are in {templates.model_id}, "
                f"but the recognizer produces {bundle.recognizer.model_id}"
            )
        self.bundle = bundle
        self.templates = templates
        self.threshold = threshold

    def scan(self, frame: Frame, detect_frame: Frame | None = None) -> Iterator[FaceMatch]:
        """
        Detect faces and match them one by one, strongest detection first.

        Lazy, so a caller that stops at the first accepted face skips
        embedding the rest.

        :param frame: the frame faces are embedded from
        :param detect_frame: the frame to detect in, e.g. a contrast-enhanced
            grayscale copy; defaults to ``frame``
        """
        for face in self.detect(frame if detect_frame is None else detect_frame):
            yield self.match(frame, face)

    def detect(self, frame: Frame) -> list[Face]:
        """
        Detect faces without matching them, strongest detection first.

        :param frame: the frame to detect in
        """
        return list(self.bundle.detector.detect(frame))

    def match(self, frame: Frame, face: Face) -> FaceMatch:
        """
        Run liveness, embed ``face`` and compare it to the templates.
        """
        liveness = None
        if self.bundle.liveness is not None:
            liveness = self.bundle.liveness.check(frame, face)
            if not liveness.passed:
                return FaceMatch(face, row=-1, distance=math.inf, accepted=False, liveness=liveness)

        embedding = self.bundle.recognizer.embed(frame, face)
        row, distance = best_match(self.templates.matrix, embedding.vector)
        return FaceMatch(
            face,
            row=row,
            distance=distance,
            accepted=is_match(distance, self.threshold),
            liveness=liveness,
        )

    def owner_of(self, result: FaceMatch) -> Template | None:
        """
        Return the template ``result`` was matched against, if any.
        """
        return self.templates.owner_of(result.row)
