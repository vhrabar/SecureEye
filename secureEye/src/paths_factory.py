from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path, PurePath
from types import SimpleNamespace


def _load_generated_paths_module():
    generated = Path(__file__).resolve().with_name("paths.py")
    if not generated.is_file():
        return None

    spec = spec_from_file_location("secureeye_generated_paths", generated)
    if spec is None or spec.loader is None:
        return None

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _default_paths():
    # Source checkout defaults used when Meson-generated `paths.py` is unavailable.
    src_dir = Path(__file__).resolve().parent
    return SimpleNamespace(
        config_dir=src_dir,
        dlib_data_dir=src_dir / "dlib-data",
        user_models_dir=src_dir / "models",
        log_path=src_dir,
        data_dir=src_dir,
    )


paths = _load_generated_paths_module() or _default_paths()

models = [
    "shape_predictor_5_face_landmarks.dat",
    "mmod_human_face_detector.dat",
    "dlib_face_recognition_resnet_model_v1.dat",
]


def dlib_data_dir_path() -> str:
    return str(paths.dlib_data_dir)


def shape_predictor_5_face_landmarks_path() -> str:
    return str(paths.dlib_data_dir / models[0])


def mmod_human_face_detector_path() -> str:
    return str(paths.dlib_data_dir / models[1])


def dlib_face_recognition_resnet_model_v1_path() -> str:
    return str(paths.dlib_data_dir / models[2])


def user_model_path(user: str) -> str:
    return str(paths.user_models_dir / f"{user}.dat")


def config_file_path() -> str:
    return str(paths.config_dir / "config.ini")


def snapshots_dir_path() -> PurePath:
    return paths.log_path / "snapshots"


def snapshot_path(snapshot: str) -> str:
    return str(snapshots_dir_path() / snapshot)


def user_models_dir_path() -> PurePath:
    return paths.user_models_dir


def logo_path() -> str:
    return str(paths.data_dir / "logo.png")
