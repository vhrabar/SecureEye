"""Authentication session extracted from legacy compare flow."""

from __future__ import annotations

import _thread as thread
import configparser
import cv2
import numpy as np
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

import paths_factory
import snapshot
from i18n import _
from recorders.video_capture import VideoCapture
from .detector_factory import create_detector, DetectorFactoryError
from .errors import ExitCode
from .frame_ops import apply_rotation_mode, darkness_percent, maybe_scale
from .matching import best_match, is_match
from .model_store import EmptyModelStore, ModelFileNotFound, ModelSchemaError, load_user_models
from .types import RuntimeStats
from .ui_bridge import AuthUiBridge


class AuthSession:
    """Run one end-to-end authentication attempt for a user."""

    def __init__(self, config_path: str | None = None, ui_bridge: AuthUiBridge | None = None):
        self.config_path = config_path or paths_factory.config_file_path()
        self.ui = ui_bridge
        self.timings: dict[str, float] = {"st": time.time()}
        self._cancel_event = threading.Event()
        self._state_lock = threading.Lock()
        self._video_capture: VideoCapture | None = None

    def cancel(self) -> None:
        """Request cooperative stop and release camera resources as soon as possible."""
        self._cancel_event.set()
        with self._state_lock:
            if self._video_capture is not None:
                try:
                    self._video_capture.release()
                except Exception:
                    pass

    def run(self, user: str) -> int:
        if not user:
            return int(ExitCode.ABORT)

        try:
            models, encodings = load_user_models(user)
        except (ModelFileNotFound, EmptyModelStore, ModelSchemaError):
            return int(ExitCode.NO_FACE_MODEL)

        config = configparser.ConfigParser()
        config.read(self.config_path)

        gtk_stdout = config.getboolean("debug", "gtk_stdout", fallback=False)
        self.ui = self.ui or AuthUiBridge(enabled_stdout=gtk_stdout)
        self.ui.start()

        try:
            return self._run_loop(config, models, encodings)
        finally:
            self.ui.close()

    def _run_loop(self, config, models, encodings) -> int:
        save_failed = config.getboolean("snapshots", "save_failed", fallback=False)
        save_successful = config.getboolean("snapshots", "save_successful", fallback=False)
        end_report = config.getboolean("debug", "end_report", fallback=False)
        timeout = config.getint("video", "timeout", fallback=4)
        dark_threshold = config.getfloat("video", "dark_threshold", fallback=60.0)
        rotate = config.getint("video", "rotate", fallback=0)
        video_certainty = config.getfloat("video", "certainty", fallback=3.5) / 10

        self._send_ui("M", _("Starting up..."))
        self.timings["in"] = time.time() - self.timings["st"]

        detector_bundle, detector_error = self._init_detector_async(config)
        if detector_error is not None:
            print(detector_error)
            return 1

        self.timings["ic"] = time.time()
        video_capture = VideoCapture(config)
        with self._state_lock:
            self._video_capture = video_capture
        self.timings["ic"] = time.time() - self.timings["ic"]

        exposure = config.getint("video", "exposure", fallback=-1)
        max_height = config.getfloat("video", "max_height", fallback=320.0)
        height = video_capture.internal.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1
        if rotate == 2:
            height = video_capture.internal.get(cv2.CAP_PROP_FRAME_WIDTH) or 1
        scaling_factor = (max_height / height) or 1

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
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
                        print(_("Average darkness: {avg}, Threshold: {threshold}").format(
                            avg=str(avg_darkness), threshold=str(dark_threshold)
                        ))
                        return int(ExitCode.TOO_DARK)
                    return int(ExitCode.TIMEOUT_REACHED)

                frame, gsframe = video_capture.read_frame()
                gsframe = clahe.apply(gsframe)

                if (save_failed or save_successful) and len(snapframes) < 3:
                    snapframes.append(frame)

                darkness, hist_total = darkness_percent(gsframe)
                if hist_total == 0 or darkness == 100:
                    stats.black_tries += 1
                    continue

                dark_running_total += darkness
                stats.valid_frames += 1

                if darkness > dark_threshold:
                    stats.dark_tries += 1
                    continue

                frame, gsframe = maybe_scale(frame, gsframe, scaling_factor)
                frame, gsframe = apply_rotation_mode(frame, gsframe, rotate, stats.frames)

                for face_location in detector_bundle.detector.detect(gsframe):
                    face_encoding = np.asarray(
                        detector_bundle.detector.encode(frame, face_location),
                        dtype=np.float32,
                    )
                    match_index, match = best_match(encodings, face_encoding)
                    stats.lowest_certainty = min(stats.lowest_certainty, match)

                    if not is_match(match, video_certainty):
                        continue

                    self.timings["tt"] = time.time() - self.timings["st"]
                    self.timings["fl"] = time.time() - self.timings["fr"]

                    if end_report:
                        self._print_end_report(models, match_index, match, stats, video_capture, frame, height)

                    if save_successful:
                        self._make_snapshot(_("SUCCESSFUL"), snapframes, stats)

                    stamp_code = self._run_rubberstamps_if_enabled(config, detector_bundle, video_capture, clahe)
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
                if self._video_capture is not None:
                    try:
                        self._video_capture.release()
                    except Exception:
                        pass
                    self._video_capture = None

    def _init_detector_async(self, config):
        holder: dict[str, Any] = {"bundle": None, "error": None}

        self.timings["ll"] = time.time()
        lock = thread.allocate_lock()
        lock.acquire()

        def _target():
            try:
                holder["bundle"] = create_detector(config)
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

    def _run_rubberstamps_if_enabled(self, config, detector_bundle, video_capture, clahe) -> int | None:
        if not config.getboolean("rubberstamps", "enabled", fallback=False):
            return None

        if detector_bundle.legacy_face_detector is None or detector_bundle.legacy_pose_predictor is None:
            print(_("Rubberstamps currently require the dlib detector backend"))
            return int(ExitCode.RUBBERSTAMP)

        try:
            import rubberstamps
        except ModuleNotFoundError as exc:  # pragma: no cover - fallback for package-style execution
            if getattr(exc, "name", "") != "rubberstamps":
                raise
            from secureEye.src import rubberstamps

        self._send_ui("S", "")
        try:
            rubberstamps.execute(config, None, {
                "video_capture": video_capture,
                "face_detector": detector_bundle.legacy_face_detector,
                "pose_predictor": detector_bundle.legacy_pose_predictor,
                "clahe": clahe,
            })
        except SystemExit as exc:
            return int(exc.code) if isinstance(exc.code, int) else int(ExitCode.RUBBERSTAMP)
        return None

    def _make_snapshot(self, state: str, snapframes: list[Any], stats: RuntimeStats) -> None:
        snapshot.generate(snapframes, [
            state + _(" LOGIN"),
            _("Date: ") + datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M:%S UTC"),
            _("Scan time: ") + str(round(time.time() - self.timings["fr"], 2)) + "s",
            _("Frames: ") + str(stats.frames) + " (" + str(
                round(stats.frames / (time.time() - self.timings["fr"]), 2)) + "FPS)",
            _("Hostname: ") + os.uname().nodename,
            _("Best certainty value: ") + str(round(stats.lowest_certainty * 10, 1)),
        ])

    def _ui_subtext(self, stats: RuntimeStats) -> str:
        ui_subtext = "Scanned " + str(stats.valid_frames - stats.dark_tries) + " frames"
        if stats.dark_tries > 1:
            ui_subtext += " (skipped " + str(stats.dark_tries) + " dark frames)"
        return ui_subtext

    def _send_ui(self, kind: str, message: str) -> None:
        if self.ui is not None:
            self.ui.send(kind, message)

    def _print_end_report(self, models, match_index, match, stats, video_capture, frame, height):
        def print_timing(label, key):
            print("  %s: %dms" % (label, round(self.timings[key] * 1000)))

        print(_("Time spent"))
        print_timing(_("Starting up"), "in")
        print(_("  Open cam + load libs: %dms") % (round(max(self.timings["ll"], self.timings["ic"]) * 1000, )))
        print_timing(_("  Opening the camera"), "ic")
        print_timing(_("  Importing recognition libs"), "ll")
        print_timing(_("Searching for known face"), "fl")
        print_timing(_("Total time"), "tt")

        print(_("\nResolution"))
        width = video_capture.fw or 1
        print(_("  Native: %dx%d") % (height, width))
        scale_height, scale_width = frame.shape[:2]
        print(_("  Used: %dx%d") % (scale_height, scale_width))

        print(_("\nFrames searched: %d (%.2f fps)") % (stats.frames, stats.frames / self.timings["fl"]))
        print(_("Black frames ignored: %d ") % (stats.black_tries,))
        print(_("Dark frames ignored: %d ") % (stats.dark_tries,))
        print(_("Certainty of winning frame: %.3f") % (match * 10,))

        if 0 <= match_index < len(models):
            print(_("Winning model: %d (\"%s\")") % (match_index, models[match_index].get("label", "?")))
        else:
            print(_("Winning model index: %d") % match_index)
