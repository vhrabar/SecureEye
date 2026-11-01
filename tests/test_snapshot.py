import sys
from pathlib import Path, PurePath

import cv2
import numpy as np

SRC_DIR = str(Path(__file__).resolve().parents[1] / "secureEye" / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import paths_factory  # noqa: E402
import snapshot  # noqa: E402


def _frames(count):
    return [np.full((240, 320, 3), 90, np.uint8) for _ in range(count)]


def test_snapshot_without_the_logo_file(tmp_path, monkeypatch):
    # logo.png is no longer installed; a snapshot (and the login saving it) must not fail over it
    monkeypatch.setattr(paths_factory, "logo_path", lambda: str(tmp_path / "missing.png"))
    monkeypatch.setattr(
        paths_factory, "snapshots_dir_path", lambda: PurePath(tmp_path / "snapshots")
    )
    monkeypatch.setattr(
        paths_factory, "snapshot_path", lambda name: str(tmp_path / "snapshots" / name)
    )

    path = snapshot.generate(_frames(2), ["FAILED LOGIN", "Frames: 2"])

    image = cv2.imread(path)
    assert image is not None
    assert image.shape[1] == 640


def test_logo_is_left_out_where_it_does_not_fit(tmp_path, monkeypatch):
    logo = tmp_path / "logo.png"
    cv2.imwrite(str(logo), np.full((57, 180, 3), 255, np.uint8))
    monkeypatch.setattr(paths_factory, "logo_path", lambda: str(logo))
    monkeypatch.setattr(
        paths_factory, "snapshots_dir_path", lambda: PurePath(tmp_path / "snapshots")
    )
    monkeypatch.setattr(
        paths_factory, "snapshot_path", lambda name: str(tmp_path / "snapshots" / name)
    )

    assert cv2.imread(snapshot.generate(_frames(2), ["one line"])) is not None


def test_snapshot_with_a_logo(tmp_path, monkeypatch):
    logo = tmp_path / "logo.png"
    cv2.imwrite(str(logo), np.full((57, 180, 3), 255, np.uint8))
    monkeypatch.setattr(paths_factory, "logo_path", lambda: str(logo))
    monkeypatch.setattr(
        paths_factory, "snapshots_dir_path", lambda: PurePath(tmp_path / "snapshots")
    )
    monkeypatch.setattr(
        paths_factory, "snapshot_path", lambda name: str(tmp_path / "snapshots" / name)
    )

    # the six lines AuthSession writes leave room for the logo below the frames
    path = snapshot.generate(_frames(2), ["SUCCESSFUL LOGIN"] + ["line"] * 5)

    image = cv2.imread(path)
    # the logo sits bottom right, below the frames
    assert image[240 + 20 + 28, 640 - 210 + 90].mean() > 200
