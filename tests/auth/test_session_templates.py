import json
import sys
from pathlib import Path

import pytest

# Path setup
SRC_DIR = str(Path(__file__).resolve().parents[2] / "secureEye" / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import paths_factory  # noqa: E402
from auth import template_store  # noqa: E402
from auth.errors import ExitCode  # noqa: E402
from auth.session import AuthSession  # noqa: E402

SFACE = "sface-2021dec"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A config file and an isolated models directory."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    monkeypatch.setattr(
        paths_factory, "user_model_path", lambda user: str(models_dir / f"{user}.dat")
    )

    def write_config(body: str) -> str:
        path = tmp_path / "config.ini"
        path.write_text(body.strip() + "\n", encoding="utf-8")
        return str(path)

    return type("Env", (), {"models_dir": models_dir, "write_config": staticmethod(write_config)})()


def _write_templates(models_dir: Path, user: str, model_id: str) -> None:
    payload = {
        "version": 2,
        "templates": [
            {
                "id": 0,
                "label": "Initial model",
                "created": 1,
                "model_id": model_id,
                "dim": 128,
                "data": [[0.1] * 128],
            }
        ],
    }
    (models_dir / f"{user}.dat").write_text(json.dumps(payload), encoding="utf-8")


def test_missing_models_report_no_face_model(env):
    config_path = env.write_config("[core]\npipeline = legacy")

    assert AuthSession(config_path).run("alice") == int(ExitCode.NO_FACE_MODEL)


def test_wrong_embedding_space_reports_mismatch(env, capsys):
    """The user has models, they are just unusable — that is not 'no models'."""
    _write_templates(env.models_dir, "alice", template_store.LEGACY_MODEL_ID)
    config_path = env.write_config(f"[core]\npipeline = onnx\n\n[recognition]\nmodel_id = {SFACE}")

    code = AuthSession(config_path).run("alice")

    assert code == int(ExitCode.TEMPLATE_MODEL_MISMATCH)
    assert code != int(ExitCode.NO_FACE_MODEL)
    # The reason has to reach the user; a silent failure is indistinguishable
    # from an ordinary non-match and no retry can fix it
    assert "re-enrollment is required" in capsys.readouterr().out


def test_mismatch_code_is_stable():
    """The value is part of the wire contract with pam/main.hh."""
    assert int(ExitCode.TEMPLATE_MODEL_MISMATCH) == 16


def test_empty_user_aborts(env):
    config_path = env.write_config("[core]\npipeline = legacy")

    assert AuthSession(config_path).run("") == int(ExitCode.ABORT)
