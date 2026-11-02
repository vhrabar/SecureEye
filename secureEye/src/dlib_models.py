import bz2
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.request import urlopen

import paths_factory

# Pinned so the checksums below stay valid.
_BASE_URL = "https://github.com/davisking/dlib-models/raw/fd81b6308a6a73d4ce08859eb2f4b628a21e27a2/"
_CHUNK = 1 << 16
_TIMEOUT = 30


@dataclass(frozen=True)
class DataFile:
    name: str
    # sha256 of the unpacked .dat file
    sha256: str

    @property
    def url(self) -> str:
        return _BASE_URL + self.name + ".bz2"


# Same order as paths_factory.models
FILES = (
    DataFile(
        "shape_predictor_5_face_landmarks.dat",
        "c4b1e9804792707d3a405c2c16a80a20269e6675021f64a41d30fffafbc41888",
    ),
    DataFile(
        "mmod_human_face_detector.dat",
        "be467b1a76f482693de3b0f6a1ff91d092319be71523d4d4b0628f6a53fcb87a",
    ),
    DataFile(
        "dlib_face_recognition_resnet_model_v1.dat",
        "55533b28a95800a551ba546ba62fe69625c7e95a7061c338adffead08719da30",
    ),
)


class FetchError(RuntimeError):
    """A data file could not be downloaded, unpacked or verified."""


def data_dir() -> Path:
    return Path(paths_factory.dlib_data_dir_path())


def missing() -> list[str]:
    """Names of the data files that are not in the data directory."""
    directory = data_dir()
    return [f.name for f in FILES if not (directory / f.name).is_file()]


def _download(data_file: DataFile, directory: Path) -> None:
    decompressor = bz2.BZ2Decompressor()
    digest = hashlib.sha256()

    # Unpack into a temporary file next to the target so the rename is atomic and a
    # broken download never leaves a half written .dat behind.
    fd, tmp_name = tempfile.mkstemp(prefix="." + data_file.name + ".", dir=directory)
    try:
        with os.fdopen(fd, "wb") as out, urlopen(data_file.url, timeout=_TIMEOUT) as response:
            while chunk := response.read(_CHUNK):
                data = decompressor.decompress(chunk)
                digest.update(data)
                out.write(data)
        if not decompressor.eof:
            raise FetchError(f"{data_file.name}: the download was cut short")
        if digest.hexdigest() != data_file.sha256:
            raise FetchError(f"{data_file.name}: checksum mismatch")
        os.chmod(tmp_name, 0o644)
        os.replace(tmp_name, directory / data_file.name)
    except FetchError:
        os.unlink(tmp_name)
        raise
    except Exception as exc:
        os.unlink(tmp_name)
        raise FetchError(f"{data_file.name}: {exc}") from exc


def fetch(progress: Optional[Callable[[str], None]] = None) -> list[str]:
    """Download the data files that are missing. Returns the names that were fetched."""
    directory = data_dir()
    directory.mkdir(mode=0o755, parents=True, exist_ok=True)

    wanted = set(missing())
    fetched = []
    for data_file in FILES:
        if data_file.name not in wanted:
            continue
        if progress is not None:
            progress(data_file.name)
        _download(data_file, directory)
        fetched.append(data_file.name)
    return fetched
