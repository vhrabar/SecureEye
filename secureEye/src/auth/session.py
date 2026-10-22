from __future__ import annotations

import _thread as thread
import configparser
import cv2
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

import paths_factory
import snapshot
from i18n import _
from . import template_store
from .capture import FrameObserver, FrameReport, FrameState, FrameStream, normalized_boxes
from .detector_factory import create_pipeline, DetectorFactoryError
from .errors import ExitCode
from .pipeline import FaceMatch, Pipeline
from .template_store import TemplateSet, TemplateSpaceMismatch, TemplateStoreError
from .interfaces import Face, Frame
from .types import RuntimeStats
from .ui_bridge import AuthUiBridge


class AuthSession:
    """Run one end-to-end authentication attempt for a user."""

    def __init__(
        self,
        config_path: str | None = None,
        ui_bridge: AuthUiBridge | None = None,
        on_frame: FrameObserver | None = None,
    ):
        """
        :param config_path: config.ini to read, defaults to the installed one
        :param ui_bridge: receiver for the legacy M/S status text
        :param on_frame: called with a FrameReport for every frame read; an observer that
            raises cancels the session (e.g. because its client went away)
        """
        self.config_path = config_path or paths_factory.config_file_path()
        self.ui = ui_bridge
        self.on_frame = on_frame
        self.timings: dict[str, float] = {"st": time.time()}
        self._cancel_event = threading.Event()
        self._state_lock = threading.Lock()
        self._stream: FrameStream | None = None

    def cancel(self) -> None:
        """Request cooperative stop and release camera resources as soon as possible."""
        self._cancel_event.set()
        with self._state_lock:
            if self._stream is not None:
                self._stream.release()

    def run(self, user: str) -> int:
        if not user:
            return int(ExitCode.ABORT)

        config = configparser.ConfigParser()
        config.read(self.config_path)

        # The templates have to match the embedding space of the active
        # pipeline, so the config decides which ones we can even load.
        try:
            templates = template_store.load(user, model_id=template_store.active_model_id(config))
        except TemplateSpaceMismatch as exc:
            # Distinct from "no models": the user has models, they are just
            # unusable here, and only re-enrolling fixes that.
            print(str(exc))
            return int(ExitCode.TEMPLATE_MODEL_MISMATCH)
        except TemplateStoreError:
            return int(ExitCode.NO_FACE_MODEL)

        gtk_stdout = config.getboolean("debug", "gtk_stdout", fallback=False)
        self.ui = self.ui or AuthUiBridge(enabled_stdout=gtk_stdout)
        self.ui.start()

        try:
            return self._run_loop(config, templates)
        finally:
            self.ui.close()

    def _run_loop(self, config, templates: TemplateSet) -> int:  # noqa: C901
        save_failed = config.getboolean("snapshots", "save_failed", fallback=False)
        save_successful = config.getboolean("snapshots", "save_successful", fallback=False)
        end_report = config.getboolean("debug", "end_report", fallback=False)
        timeout = config.getint("video", "timeout", fallback=4)
        video_certainty = config.getfloat("video", "certainty", fallback=3.5) / 10

        self._send_ui("M", _("Starting up..."))
        self.timings["in"] = time.time() - self.timings["st"]

        detector_bundle, detector_error = self._init_detector_async(config)
        if detector_error is not None:
            print(detector_error)
            return 1

        try:
            pipeline = Pipeline(detector_bundle, templates, video_certainty)
        except ValueError as exc:
            print(str(exc))
            return int(ExitCode.TEMPLATE_MODEL_MISMATCH)

        self.timings["ic"] = time.time()
        stream = FrameStream(config)
        with self._state_lock:
            self._stream = stream
        # cancel() may have run before the stream existed
        if self._cancel_event.is_set():
            stream.release()
        self.timings["ic"] = time.time() - self.timings["ic"]
        video_capture = stream.video_capture
        dark_threshold = stream.dark_threshold

        exposure = config.getint("video", "exposure", fallback=-1)
        self._send_ui("M", _("Identifying you..."))

        stats = RuntimeStats()
        snapframes: list[Any] = []
        dark_running_total = 0.0
        self.timings["fr"] = time.time()

        try:
            while True:
                if self._cancel_event.is_set():
                    return int(ExitCode.TIMEOUT_REACHED)

                stats.frames += 1
                self._send_ui("S", self._ui_subtext(stats))

                if time.time() - self.timings["fr"] > timeout:
                    if save_failed:
                        self._make_snapshot(_("FAILED"), snapframes, stats)

                    if stats.dark_tries == stats.valid_frames:
                        print(_("All frames were too dark, please check dark_threshold in config"))
                        avg_darkness = dark_running_total / max(1, stats.valid_frames)
                        print(
                            _("Average darkness: {avg}, Threshold: {threshold}").format(
                                avg=str(avg_darkness), threshold=str(dark_threshold)
                            )
                        )
                        return int(ExitCode.TOO_DARK)
                    return int(ExitCode.TIMEOUT_REACHED)

                captured = stream.read()
                frame = captured.frame

                if (save_failed or save_successful) and len(snapframes) < 3:
                    snapframes.append(captured.raw)

                if captured.state is FrameState.BLACK:
                    stats.black_tries += 1
                    self._report(captured.index, FrameState.BLACK, captured.darkness, stream, frame)
                    continue

                dark_running_total += captured.darkness
                stats.valid_frames += 1

                if captured.state is FrameState.DARK:
                    stats.dark_tries += 1
                    self._report(captured.index, FrameState.DARK, captured.darkness, stream, frame)
                    continue

                faces = pipeline.detect(captured.gsframe)
                accepted: FaceMatch | None = None
                best: float | None = None
                for face in faces:
                    result = pipeline.match(frame, face)
                    if result.row >= 0:
                        stats.lowest_certainty = min(stats.lowest_certainty, result.distance)
                        best = result.distance if best is None else min(best, result.distance)
                    if result.accepted:
                        accepted = result
                        break

                self._report(
                    captured.index,
                    self._face_state(faces, accepted),
                    captured.darkness,
                    stream,
                    frame,
                    faces=faces,
                    distance=best,
                    certainty=video_certainty,
                )

                if accepted is not None:
                    self.timings["tt"] = time.time() - self.timings["st"]
                    self.timings["fl"] = time.time() - self.timings["fr"]

                    if end_report:
                        self._print_end_report(
                            templates,
                            accepted.row,
                            accepted.distance,
                            stats,
                            video_capture,
                            frame,
                            stream.native_height,
                        )

                    if save_successful:
                        self._make_snapshot(_("SUCCESSFUL"), snapframes, stats)

                    stamp_code = self._run_rubberstamps_if_enabled(
                        config, detector_bundle, video_capture, stream.clahe
                    )
                    if stamp_code is not None:
                        return stamp_code

                    return int(ExitCode.SUCCESS)

                if exposure != -1:
                    # Some devices apply manual exposure only after first reads; set it each frame for reliability.
                    video_capture.internal.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1.0)
                    video_capture.internal.set(cv2.CAP_PROP_EXPOSURE, float(exposure))

            return int(ExitCode.ABORT)
        finally:
            with self._state_lock:
                self._stream = None
            stream.release()

    @staticmethod
    def _face_state(faces: list[Face], accepted: FaceMatch | None) -> FrameState:
        if accepted is not None:
            return FrameState.MATCH
        if not faces:
            return FrameState.NO_FACE
        return FrameState.MULTIPLE if len(faces) > 1 else FrameState.FACE

    def _report(
        self,
        index: int,
        state: FrameState,
        darkness: float,
        stream: FrameStream,
        frame: Frame,
        faces: list[Face] | None = None,
        distance: float | None = None,
        certainty: float | None = None,
    ) -> None:
        if self.on_frame is None:
            return
        report = FrameReport(
            index=index,
            elapsed=time.time() - self.timings["fr"],
            state=state,
            darkness=darkness,
            dark_threshold=stream.dark_threshold,
            faces=normalized_boxes(faces or [], frame),
            # Pipeline works on certainty / 10; report on the config.ini scale
            distance=None if distance is None else distance * 10,
            certainty=None if certainty is None else certainty * 10,
        )
        try:
            self.on_frame(report, frame)
        except Exception:
            self.cancel()

    def _init_detector_async(self, config):
        holder: dict[str, Any] = {"bundle": None, "error": None}

        self.timings["ll"] = time.time()
        lock = thread.allocate_lock()
        lock.acquire()

        def _target():
            try:
                holder["bundle"] = create_pipeline(config)
                self.timings["ll"] = time.time() - self.timings["ll"]
            except FileNotFoundError:
                print(_("Data files have not been downloaded, please run the following commands:"))
                print("\n\tcd " + paths_factory.dlib_data_dir_path())
                print("\tsudo ./install.sh\n")
                holder["error"] = _("Missing dlib data files")
            except DetectorFactoryError as exc:
                holder["error"] = str(exc)
            except Exception as exc:  # pragma: no cover - defensive catch from worker thread
                holder["error"] = str(exc)
            finally:
                lock.release()

        thread.start_new_thread(_target, ())
        lock.acquire()
        lock.release()

        return holder["bundle"], holder["error"]

    def _run_rubberstamps_if_enabled(
        self, config, detector_bundle, video_capture, clahe
    ) -> int | None:
        if not config.getboolean("rubberstamps", "enabled", fallback=False):
            return None

        if (
            detector_bundle.legacy_face_detector is None
            or detector_bundle.legacy_pose_predictor is None
        ):
            print(_("Rubberstamps currently require the dlib detector backend"))
            return int(ExitCode.RUBBERSTAMP)

        try:
            import rubberstamps
        except (
            ModuleNotFoundError
        ) as exc:  # pragma: no cover - fallback for package-style execution
            if getattr(exc, "name", "") != "rubberstamps":
                raise
            from secureEye.src import rubberstamps

        self._send_ui("S", "")
        try:
            rubberstamps.execute(
                config,
                None,
                {
                    "video_capture": video_capture,
                    "face_detector": detector_bundle.legacy_face_detector,
                    "pose_predictor": detector_bundle.legacy_pose_predictor,
                    "clahe": clahe,
                },
            )
        except SystemExit as exc:
            return int(exc.code) if isinstance(exc.code, int) else int(ExitCode.RUBBERSTAMP)
        return None

    def _make_snapshot(self, state: str, snapframes: list[Any], stats: RuntimeStats) -> None:
        snapshot.generate(
            snapframes,
            [
                state + _(" LOGIN"),
                _("Date: ") + datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M:%S UTC"),
                _("Scan time: ") + str(round(time.time() - self.timings["fr"], 2)) + "s",
                _("Frames: ")
                + str(stats.frames)
                + " ("
                + str(round(stats.frames / (time.time() - self.timings["fr"]), 2))
                + "FPS)",
                _("Hostname: ") + os.uname().nodename,
                _("Best certainty value: ") + str(round(stats.lowest_certainty * 10, 1)),
            ],
        )

    def _ui_subtext(self, stats: RuntimeStats) -> str:
        ui_subtext = "Scanned " + str(stats.valid_frames - stats.dark_tries) + " frames"
        if stats.dark_tries > 1:
            ui_subtext += " (skipped " + str(stats.dark_tries) + " dark frames)"
        return ui_subtext

    def _send_ui(self, kind: str, message: str) -> None:
        if self.ui is not None:
            self.ui.send(kind, message)

    def _print_end_report(
        self, templates: TemplateSet, match_index, match, stats, video_capture, frame, height
    ):
        def print_timing(label, key):
            print("  %s: %dms" % (label, round(self.timings[key] * 1000)))

        print(_("Time spent"))
        print_timing(_("Starting up"), "in")
        print(
            _("  Open cam + load libs: %dms")
            % (
                round(
                    max(self.timings["ll"], self.timings["ic"]) * 1000,
                )
            )
        )
        print_timing(_("  Opening the camera"), "ic")
        print_timing(_("  Importing recognition libs"), "ll")
        print_timing(_("Searching for known face"), "fl")
        print_timing(_("Total time"), "tt")

        print(_("\nResolution"))
        width = video_capture.fw or 1
        print(_("  Native: %dx%d") % (height, width))
        scale_height, scale_width = frame.shape[:2]
        print(_("  Used: %dx%d") % (scale_height, scale_width))

        print(
            _("\nFrames searched: %d (%.2f fps)")
            % (stats.frames, stats.frames / self.timings["fl"])
        )
        print(_("Black frames ignored: %d ") % (stats.black_tries,))
        print(_("Dark frames ignored: %d ") % (stats.dark_tries,))
        print(_("Certainty of winning frame: %.3f") % (match * 10,))

        # match_index addresses a row of the stacked matrix, not a template.
        owner = templates.owner_of(match_index)
        if owner is not None:
            print(_('Winning model: %d ("%s")') % (owner.id, owner.label or "?"))
        else:
            print(_("Winning model index: %d") % match_index)
