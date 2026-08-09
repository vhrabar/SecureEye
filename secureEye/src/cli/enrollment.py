import builtins
import os
import sys
import time

import numpy as np

import paths_factory
from i18n import _
from recorders.video_capture import VideoCapture

# Frames to look at before giving up
MAX_FRAMES = 60

# Labels are stored in a comma-separated listing, and kept short for it
MAX_LABEL_LENGTH = 24


def load_detector(config):
    """Build the configured detector, exiting with guidance if it cannot load."""
    use_mediapipe = config.get("core", "detector_backend", fallback="dlib") == "mediapipe"

    try:
        try:
            from detectors import Detector
        except ModuleNotFoundError as exc:
            if getattr(exc, "name", "") != "detectors":
                raise
            from secureEye.src.detectors import Detector

        return Detector(config)
    except ImportError as err:
        print(err)
        if use_mediapipe:
            print(_("\nCan't import the mediapipe module, check the output of"))
            print("pip3 show mediapipe")
        else:
            print(_("\nCan't import the dlib module, check the output of"))
            print("pip3 show dlib")
        sys.exit(1)
    except FileNotFoundError:
        print(_("Data files have not been downloaded, please run the following commands:"))
        print("\n\tcd " + paths_factory.dlib_data_dir_path())
        print("\tsudo ./install.sh\n")
        sys.exit(1)


def ensure_models_dir():
    """Create the models folder if this is the first enrollment on the system."""
    if not os.path.exists(paths_factory.user_models_dir_path()):
        print(_("No face model folder found, creating one"))
        os.makedirs(paths_factory.user_models_dir_path())


def ask_label(default: str) -> str:
    """Return the label for a new model, asking the user unless -y was passed."""
    label = default

    if builtins.secureEye_args.y:
        print(_('Using default label "%s" because of -y flag') % (label,))
    else:
        label_in = input(_("Enter a label for this new model [{}]: ").format(label))

        # Set the custom label (if any) and limit its length
        if label_in != "":
            label = label_in[:MAX_LABEL_LENGTH]

    # Remove illegal characters
    if "," in label:
        print(_('NOTICE: Removing illegal character "," from model name'))
        label = label.replace(",", "")

    return label


def capture_encoding(config, detector) -> np.ndarray:
    """Capture one face from the camera and return its encoding.

    Exits with an explanation when no usable face turns up.
    """
    # OpenCV has to be imported after dlib / mediapipe, so keep it in here
    import cv2

    video_capture = VideoCapture(config)

    print(_("\nPlease look straight into the camera"))

    # Give the user time to read
    time.sleep(2)

    # Count the number of read frames
    frames = 0
    # Count the number of illuminated read frames
    valid_frames = 0
    # Count the number of illuminated frames that
    # were rejected for being too dark
    dark_tries = 0
    # Track the running darkness total
    dark_running_total = 0
    face_locations = None
    frame = None

    dark_threshold = config.getfloat("video", "dark_threshold", fallback=60)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    # Loop through frames till we hit a timeout
    while frames < MAX_FRAMES:
        frames += 1
        # Grab a single frame of video
        frame, gsframe = video_capture.read_frame()
        gsframe = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gsframe = clahe.apply(gsframe)

        # Create a histogram of the image with 8 values
        hist = cv2.calcHist([gsframe], [0], None, [8], [0, 256])
        # All values combined for percentage calculation
        hist_total = np.sum(hist)

        # Calculate frame darkness
        darkness = hist[0] / hist_total * 100

        # If the image is fully black due to a bad camera read,
        # skip to the next frame
        if (hist_total == 0) or (darkness == 100):
            continue

        # Include this frame in calculating our average session brightness
        dark_running_total += darkness
        valid_frames += 1

        # If the image exceeds darkness threshold due to subject distance,
        # skip to the next frame
        if darkness > dark_threshold:
            dark_tries += 1
            continue

        # Get all faces from that frame as encodings
        face_locations = detector.detect(gsframe)

        # If we've found at least one, we can continue
        if face_locations:
            break

    video_capture.release()

    # If we've found no faces, try to determine why
    if not face_locations:
        if valid_frames == 0:
            print(_("Camera saw only black frames - is IR emitter working?"))
        elif valid_frames == dark_tries:
            print(_("All frames were too dark, please check dark_threshold in config"))
            print(
                _("Average darkness: {avg}, Threshold: {threshold}").format(
                    avg=str(dark_running_total / valid_frames), threshold=str(dark_threshold)
                )
            )
        else:
            print(_("No face detected, aborting"))
        sys.exit(1)

    # If more than 1 faces are detected we can't know which one belongs to the user
    if len(face_locations) > 1:
        print(_("Multiple faces detected, aborting"))
        sys.exit(1)

    return np.array(detector.encode(frame, face_locations[0]))
