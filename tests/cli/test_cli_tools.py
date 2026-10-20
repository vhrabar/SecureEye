import builtins
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "secureEye" / "src"


@pytest.fixture(autouse=True)
def _src_path():
    src = str(SRC_DIR)
    if src not in sys.path:
        sys.path.insert(0, src)


@pytest.fixture
def cli_env(monkeypatch, tmp_path):
    import paths_factory

    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[core]
disabled = false

[video]
certainty = 3.5
dark_threshold = 60
exposure = -1
recording_plugin = opencv
""".strip()
        + "\n",
        encoding="utf-8",
    )

    models_dir = tmp_path / "models"
    models_dir.mkdir()

    monkeypatch.setattr(paths_factory, "config_file_path", lambda: str(config_path))
    monkeypatch.setattr(paths_factory, "user_models_dir_path", lambda: models_dir)
    monkeypatch.setattr(
        paths_factory, "user_model_path", lambda user: str(models_dir / f"{user}.dat")
    )
    monkeypatch.setattr(paths_factory, "dlib_data_dir_path", lambda: str(tmp_path / "dlib-data"))

    args = SimpleNamespace(arguments=[], y=True, plain=False)
    monkeypatch.setattr(builtins, "secureEye_args", args, raising=False)
    monkeypatch.setattr(builtins, "secureEye_user", "alice", raising=False)

    return SimpleNamespace(
        args=args,
        config_path=config_path,
        models_dir=models_dir,
        model_path=models_dir / "alice.dat",
    )


def _run_cli_module(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_disable_updates_core_flag(cli_env, capsys):
    cli_env.args.arguments = ["1"]

    _run_cli_module("cli.disable")

    updated = cli_env.config_path.read_text(encoding="utf-8")
    assert "disabled = true" in updated
    assert "disabled" in capsys.readouterr().out.lower()


def test_set_updates_config_value(cli_env, capsys):
    cli_env.args.arguments = ["certainty", "4.2"]

    _run_cli_module("cli.set")

    updated = cli_env.config_path.read_text(encoding="utf-8")
    assert "certainty = 4.2" in updated
    assert "config option updated" in capsys.readouterr().out.lower()


def test_list_plain_outputs_models(cli_env, capsys):
    payload = [
        {"id": 0, "time": 1700000000, "label": "first", "data": [[0.1, 0.2]]},
        {"id": 1, "time": 1700000100, "label": "second", "data": [[0.2, 0.3]]},
    ]
    cli_env.model_path.write_text(json.dumps(payload), encoding="utf-8")
    cli_env.args.plain = True

    _run_cli_module("cli.list")

    out = capsys.readouterr().out
    assert "first" in out
    assert "second" in out
    assert "0," in out
    assert "1," in out


def test_remove_keeps_other_models(cli_env, capsys):
    payload = [
        {"id": 0, "time": 1700000000, "label": "first", "data": [[0.1, 0.2]]},
        {"id": 1, "time": 1700000100, "label": "second", "data": [[0.2, 0.3]]},
    ]
    cli_env.model_path.write_text(json.dumps(payload), encoding="utf-8")
    cli_env.args.arguments = ["0"]
    cli_env.args.y = True

    _run_cli_module("cli.remove")

    # Removal rewrites the file in the versioned envelope
    saved = json.loads(cli_env.model_path.read_text(encoding="utf-8"))
    assert saved["version"] == 2
    assert len(saved["templates"]) == 1
    assert saved["templates"][0]["id"] == 1
    assert "removed model 0" in capsys.readouterr().out.lower()


def test_clear_deletes_model_file(cli_env, capsys):
    cli_env.model_path.write_text("[]", encoding="utf-8")
    cli_env.args.y = True

    _run_cli_module("cli.clear")

    assert not cli_env.model_path.exists()
    assert "models cleared" in capsys.readouterr().out.lower()


@pytest.fixture
def fake_camera(monkeypatch):
    """Stand in for the detector and the capture loop of a re-enroll run."""
    import cli.enrollment
    from auth import template_store
    from auth.interfaces import Embedding

    captured = np.full(128, 0.7, dtype=np.float32)

    def capture_embedding(config, _bundle):
        return Embedding(captured, template_store.active_model_id(config), 128)

    monkeypatch.setattr(cli.enrollment, "load_pipeline", lambda _config: object())
    monkeypatch.setattr(cli.enrollment, "ensure_models_dir", lambda: None)
    monkeypatch.setattr(cli.enrollment, "ask_label", lambda default: default)
    monkeypatch.setattr(cli.enrollment, "capture_embedding", capture_embedding)
    return captured


def _templates(*entries):
    return {
        "version": 2,
        "templates": [
            {
                "id": index,
                "label": label,
                "created": 1700000000 + index,
                "model_id": model_id,
                "dim": 2,
                "data": [[0.1, 0.2]],
            }
            for index, (label, model_id) in enumerate(entries)
        ],
    }


def test_re_enroll_replaces_models_of_the_active_space(cli_env, fake_camera, capsys):
    cli_env.model_path.write_text(
        json.dumps(_templates(("old", "dlib-resnet-v1"), ("older", "dlib-resnet-v1"))),
        encoding="utf-8",
    )

    _run_cli_module("cli.re_enroll")

    saved = json.loads(cli_env.model_path.read_text(encoding="utf-8"))
    assert [t["label"] for t in saved["templates"]] == ["Model #2"]
    assert saved["templates"][0]["model_id"] == "dlib-resnet-v1"
    assert "re-enrolled" in capsys.readouterr().out.lower()


def test_re_enroll_keeps_models_of_other_spaces(cli_env, fake_camera, monkeypatch):
    """The old space stays put; it is the rollback path."""
    cli_env.config_path.write_text(
        "[core]\npipeline = onnx\n\n[recognition]\nmodel_id = sface-2021dec\n", encoding="utf-8"
    )
    cli_env.model_path.write_text(
        json.dumps(_templates(("legacy", "dlib-resnet-v1"), ("stale", "sface-2021dec"))),
        encoding="utf-8",
    )

    _run_cli_module("cli.re_enroll")

    saved = json.loads(cli_env.model_path.read_text(encoding="utf-8"))
    by_space = {t["model_id"]: t["label"] for t in saved["templates"]}
    assert by_space["dlib-resnet-v1"] == "legacy"
    assert by_space["sface-2021dec"] == "Model #2"


def test_re_enroll_without_models_points_at_add(cli_env, fake_camera, capsys):
    with pytest.raises(SystemExit) as excinfo:
        _run_cli_module("cli.re_enroll")

    assert excinfo.value.code == 1
    assert "no face model known" in capsys.readouterr().out.lower()


def test_re_enroll_aborts_when_declined(cli_env, fake_camera, monkeypatch, capsys):
    payload = _templates(("old", "dlib-resnet-v1"))
    cli_env.model_path.write_text(json.dumps(payload), encoding="utf-8")
    cli_env.args.y = False
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    with pytest.raises(SystemExit) as excinfo:
        _run_cli_module("cli.re_enroll")

    assert excinfo.value.code == 1
    # Declining must not have cost the user their existing models
    assert json.loads(cli_env.model_path.read_text(encoding="utf-8")) == payload


def test_config_prints_error_when_no_editor(cli_env, monkeypatch, capsys):
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)

    _run_cli_module("cli.config")

    out = capsys.readouterr().out.lower()
    assert "could not find a suitable text editor" in out


def test_snap_generates_snapshot(cli_env, monkeypatch, capsys):
    class FakeCapture:
        def __init__(self, _config):
            self.reads = 0

        def read_frame(self):
            self.reads += 1
            frame = np.zeros((2, 2, 3), dtype=np.uint8)
            gsframe = np.zeros((2, 2), dtype=np.uint8)
            return frame, gsframe

    calls = {}

    def fake_generate(frames, lines):
        calls["frames"] = frames
        calls["lines"] = lines
        return "/tmp/snap.jpg"

    monkeypatch.setattr("recorders.video_capture.VideoCapture", FakeCapture)
    monkeypatch.setattr("snapshot.generate", fake_generate)

    _run_cli_module("cli.snap")

    out = capsys.readouterr().out
    assert "generated snapshot saved as" in out.lower()
    assert "/tmp/snap.jpg" in out
    assert len(calls["frames"]) == 4


def _json_reply(capsys):
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    assert len(lines) == 1, out
    return json.loads(lines[0])


def test_list_json_reports_models(cli_env, capsys):
    payload = [{"id": 0, "time": 1700000000, "label": "first", "data": [[0.1], [0.2]]}]
    cli_env.model_path.write_text(json.dumps(payload), encoding="utf-8")
    cli_env.args.json = True

    with pytest.raises(SystemExit) as exit_info:
        _run_cli_module("cli.list")

    assert exit_info.value.code == 0
    assert _json_reply(capsys) == {
        "ok": True,
        "data": {
            "user": "alice",
            "models": [
                {
                    "id": 0,
                    "label": "first",
                    "time": 1700000000,
                    "encodings": 2,
                    "model_id": "dlib-resnet-v1",
                }
            ],
        },
    }


def test_list_json_without_models_is_empty(cli_env, capsys):
    cli_env.args.json = True

    with pytest.raises(SystemExit) as exit_info:
        _run_cli_module("cli.list")

    assert exit_info.value.code == 0
    assert _json_reply(capsys) == {"ok": True, "data": {"user": "alice", "models": []}}


def test_list_json_reports_corrupt_model_file(cli_env, capsys):
    cli_env.model_path.write_text("{not json", encoding="utf-8")
    cli_env.args.json = True

    with pytest.raises(SystemExit):
        _run_cli_module("cli.list")

    reply = _json_reply(capsys)
    assert reply["ok"] is False
    assert reply["error"]["code"] == "model_file_invalid"
    assert str(cli_env.model_path) in reply["error"]["message"]


def test_remove_json_unknown_id(cli_env, capsys):
    cli_env.model_path.write_text(
        json.dumps([{"id": 0, "time": 0, "label": "a", "data": [[0.1]]}]), encoding="utf-8"
    )
    cli_env.args.arguments = ["7"]
    cli_env.args.json = True

    with pytest.raises(SystemExit):
        _run_cli_module("cli.remove")

    assert _json_reply(capsys)["error"]["code"] == "model_not_found"


def test_remove_json_reports_removed_model(cli_env, capsys):
    payload = [
        {"id": 0, "time": 0, "label": "a", "data": [[0.1]]},
        {"id": 1, "time": 0, "label": "b", "data": [[0.2]]},
    ]
    cli_env.model_path.write_text(json.dumps(payload), encoding="utf-8")
    cli_env.args.arguments = ["1"]
    cli_env.args.json = True

    _run_cli_module("cli.remove")

    assert _json_reply(capsys) == {"ok": True, "data": {"removed": 1, "remaining": 1}}


def test_clear_json_without_models_is_noop(cli_env, capsys):
    cli_env.args.json = True

    with pytest.raises(SystemExit) as exit_info:
        _run_cli_module("cli.clear")

    assert exit_info.value.code == 0
    assert _json_reply(capsys) == {"ok": True, "data": {"cleared": False}}


def test_disable_json_already_set_is_noop(cli_env, capsys):
    cli_env.args.arguments = ["0"]
    cli_env.args.json = True

    with pytest.raises(SystemExit) as exit_info:
        _run_cli_module("cli.disable")

    assert exit_info.value.code == 0
    assert _json_reply(capsys) == {"ok": True, "data": {"disabled": False, "changed": False}}


def test_set_json_rejects_unknown_option(cli_env, capsys):
    cli_env.args.arguments = ["nope", "1"]
    cli_env.args.json = True

    with pytest.raises(SystemExit):
        _run_cli_module("cli.set")

    assert _json_reply(capsys)["error"]["code"] == "unknown_option"


def test_set_rejects_line_breaks(cli_env, capsys):
    cli_env.args.arguments = ["certainty", "4\n[core]\ndisabled = true"]
    cli_env.args.json = True

    with pytest.raises(SystemExit):
        _run_cli_module("cli.set")

    assert _json_reply(capsys)["error"]["code"] == "invalid_value"
    assert (
        "disabled = true" not in cli_env.config_path.read_text(encoding="utf-8").split("[core]")[0]
    )


def test_set_json_reports_new_value(cli_env, capsys):
    cli_env.args.arguments = ["certainty", "4.2"]
    cli_env.args.json = True

    _run_cli_module("cli.set")

    assert _json_reply(capsys) == {"ok": True, "data": {"updated": {"certainty": "4.2"}}}


def test_set_updates_several_values_at_once(cli_env, capsys):
    cli_env.args.arguments = ["certainty", "4.2", "exposure", "-1", "dark_threshold", "50"]
    cli_env.args.json = True

    _run_cli_module("cli.set")

    updated = cli_env.config_path.read_text(encoding="utf-8")
    assert "certainty = 4.2" in updated
    assert "dark_threshold = 50" in updated
    assert "exposure = -1" in updated
    assert "[video]" in updated
    assert _json_reply(capsys)["data"]["updated"]["dark_threshold"] == "50"


def test_set_writes_nothing_when_one_key_is_unknown(cli_env, capsys):
    before = cli_env.config_path.read_text(encoding="utf-8")
    cli_env.args.arguments = ["certainty", "4.2", "nope", "1"]
    cli_env.args.json = True

    with pytest.raises(SystemExit):
        _run_cli_module("cli.set")

    assert _json_reply(capsys)["error"]["code"] == "unknown_option"
    assert cli_env.config_path.read_text(encoding="utf-8") == before


def test_set_rejects_odd_argument_count(cli_env, capsys):
    cli_env.args.arguments = ["certainty", "4.2", "exposure"]
    cli_env.args.json = True

    with pytest.raises(SystemExit):
        _run_cli_module("cli.set")

    assert _json_reply(capsys)["error"]["code"] == "missing_argument"


def _bundle_producing(model_id):
    return SimpleNamespace(recognizer=SimpleNamespace(model_id=model_id))


def _config(text=""):
    from configparser import ConfigParser

    config = ConfigParser()
    config.read_string(text)
    return config


def test_load_pipeline_returns_bundle_of_the_active_space(monkeypatch):
    import cli.enrollment

    bundle = _bundle_producing("dlib-resnet-v1")
    monkeypatch.setattr(cli.enrollment, "create_pipeline", lambda _config: bundle)

    assert cli.enrollment.load_pipeline(_config()) is bundle


def test_load_pipeline_refuses_a_recognizer_from_another_space(monkeypatch, capsys):
    """Enrolling would store dlib vectors stamped with the configured ONNX space."""
    import cli.enrollment

    monkeypatch.setattr(
        cli.enrollment, "create_pipeline", lambda _config: _bundle_producing("dlib-resnet-v1")
    )

    with pytest.raises(SystemExit) as excinfo:
        cli.enrollment.load_pipeline(_config("[core]\npipeline = onnx\n"))

    assert excinfo.value.code == 1
    out = capsys.readouterr().out
    assert "dlib-resnet-v1" in out and "sface-2021dec" in out


def test_load_pipeline_reports_factory_errors(monkeypatch, capsys):
    import cli.enrollment
    from auth.detector_factory import DetectorFactoryError

    def fail(_config):
        raise DetectorFactoryError("Unsupported detector backend: nope")

    monkeypatch.setattr(cli.enrollment, "create_pipeline", fail)

    with pytest.raises(SystemExit) as excinfo:
        cli.enrollment.load_pipeline(_config())

    assert excinfo.value.code == 1
    assert "Unsupported detector backend" in capsys.readouterr().out
