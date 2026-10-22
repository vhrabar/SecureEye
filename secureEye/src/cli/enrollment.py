import builtins
import os
import sys

import paths_factory
from auth import template_store
from auth.detector_factory import DetectorFactoryError, PipelineBundle, create_pipeline
from auth.enrollment import EnrollResult, EnrollSession
from auth.interfaces import Embedding
from i18n import _

# Labels are stored in a comma-separated listing, and kept short for it
MAX_LABEL_LENGTH = 24


def load_pipeline(config) -> PipelineBundle:
    """Build the configured pipeline, exiting with guidance if it cannot load.

    Also refuses a pipeline whose recognizer does not produce the embedding
    space the config expects, since its templates would be stored mislabelled.
    """
    use_mediapipe = config.get("core", "detector_backend", fallback="dlib") == "mediapipe"

    try:
        bundle = create_pipeline(config)
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
    except DetectorFactoryError as exc:
        print(exc)
        sys.exit(1)

    expected = template_store.active_model_id(config)
    if bundle.recognizer.model_id != expected:
        print(
            _(
                "The configured recognizer produces {actual} models, but {expected} is active"
            ).format(actual=bundle.recognizer.model_id, expected=expected)
        )
        sys.exit(1)

    return bundle


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


def capture_embedding(config, bundle: PipelineBundle) -> Embedding:
    """Capture one face from the camera and return its embedding.

    Exits with an explanation when no usable face turns up.
    """
    print(_("\nPlease look straight into the camera"))

    # Give the user time to read
    outcome = EnrollSession(config, bundle).capture(settle_s=2)

    if outcome.result is EnrollResult.SUCCESS:
        assert outcome.embedding is not None
        return outcome.embedding

    if outcome.result is EnrollResult.BLACK_FRAMES:
        print(_("Camera saw only black frames - is IR emitter working?"))
    elif outcome.result is EnrollResult.TOO_DARK:
        print(_("All frames were too dark, please check dark_threshold in config"))
        print(
            _("Average darkness: {avg}, Threshold: {threshold}").format(
                avg=str(outcome.avg_darkness),
                threshold=str(config.getfloat("video", "dark_threshold", fallback=60)),
            )
        )
    elif outcome.result is EnrollResult.MULTIPLE_FACES:
        print(_("Multiple faces detected, aborting"))
    else:
        print(_("No face detected, aborting"))
    sys.exit(1)
