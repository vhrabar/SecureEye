import builtins
import bz2
import hashlib
import importlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SRC_DIR = str(Path(__file__).resolve().parents[1] / "secureEye" / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import dlib_models  # noqa: E402
import paths_factory  # noqa: E402

_CONTENT = {f.name: f"fake {f.name}".encode() * 1000 for f in dlib_models.FILES}


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    directory = tmp_path / "dlib-data"
    monkeypatch.setattr(paths_factory, "dlib_data_dir_path", lambda: str(directory))
    # Checksums of the fake payloads instead of the real files
    monkeypatch.setattr(
        dlib_models,
        "FILES",
        tuple(
            dlib_models.DataFile(f.name, hashlib.sha256(_CONTENT[f.name]).hexdigest())
            for f in dlib_models.FILES
        ),
    )
    return directory


@pytest.fixture
def served(monkeypatch):
    """Answer each data file URL with its bz2 compressed fake payload."""
    requested = []
    payloads = {}

    def fake_urlopen(url, timeout):
        requested.append(url)
        name = url.rsplit("/", 1)[1].removesuffix(".bz2")
        return io.BytesIO(payloads.get(name, bz2.compress(_CONTENT[name])))

    monkeypatch.setattr(dlib_models, "urlopen", fake_urlopen)
    return SimpleNamespace(requested=requested, payloads=payloads)


def test_all_missing_on_an_empty_directory(data_dir):
    assert dlib_models.missing() == [f.name for f in dlib_models.FILES]


def test_fetch_downloads_and_unpacks(data_dir, served):
    fetched = dlib_models.fetch()

    assert fetched == [f.name for f in dlib_models.FILES]
    assert dlib_models.missing() == []
    for f in dlib_models.FILES:
        path = data_dir / f.name
        assert path.read_bytes() == _CONTENT[f.name]
        assert path.stat().st_mode & 0o777 == 0o644
    assert all(
        url.startswith("https://github.com/davisking/dlib-models/") for url in served.requested
    )


def test_fetch_only_downloads_what_is_missing(data_dir, served):
    data_dir.mkdir()
    present = dlib_models.FILES[0].name
    (data_dir / present).write_bytes(b"already here")

    fetched = dlib_models.fetch()

    assert present not in fetched
    assert len(served.requested) == len(dlib_models.FILES) - 1
    assert (data_dir / present).read_bytes() == b"already here"


def test_checksum_mismatch_leaves_nothing_behind(data_dir, served):
    name = dlib_models.FILES[0].name
    served.payloads[name] = bz2.compress(b"tampered")

    with pytest.raises(dlib_models.FetchError, match="checksum"):
        dlib_models.fetch()

    assert list(data_dir.iterdir()) == []


def test_truncated_download_is_rejected(data_dir, served):
    name = dlib_models.FILES[0].name
    served.payloads[name] = bz2.compress(_CONTENT[name])[:-20]

    with pytest.raises(dlib_models.FetchError, match="cut short"):
        dlib_models.fetch()

    assert list(data_dir.iterdir()) == []


def test_network_error_is_a_fetch_error(data_dir, monkeypatch):
    def broken(url, timeout):
        raise OSError("no route to host")

    monkeypatch.setattr(dlib_models, "urlopen", broken)

    with pytest.raises(dlib_models.FetchError, match="no route to host"):
        dlib_models.fetch()


def test_real_checksums_match_the_paths_factory_names():
    # dlib_detector and the GUI use paths_factory.models; both lists must name the same files.
    assert [f.name for f in dlib_models.FILES] == paths_factory.models
    assert all(len(f.sha256) == 64 for f in dlib_models.FILES)


def _run_fetch_command(monkeypatch, json_mode):
    args = SimpleNamespace(arguments=[], y=True, plain=False, json=json_mode)
    monkeypatch.setattr(builtins, "secureEye_args", args, raising=False)
    monkeypatch.setattr(builtins, "secureEye_user", "alice", raising=False)
    sys.modules.pop("cli.fetch_models", None)
    importlib.import_module("cli.fetch_models")


def test_cli_json_reports_fetched_files(data_dir, served, monkeypatch, capsys):
    _run_fetch_command(monkeypatch, json_mode=True)

    reply = json.loads(capsys.readouterr().out)
    assert reply["ok"] is True
    assert reply["data"]["fetched"] == [f.name for f in dlib_models.FILES]
    assert reply["data"]["directory"] == str(data_dir)


def test_cli_json_when_already_present(data_dir, served, monkeypatch, capsys):
    dlib_models.fetch()
    served.requested.clear()

    _run_fetch_command(monkeypatch, json_mode=True)

    reply = json.loads(capsys.readouterr().out)
    assert reply == {"ok": True, "data": {"fetched": [], "directory": str(data_dir)}}
    assert served.requested == []


def test_cli_json_reports_failure(data_dir, served, monkeypatch, capsys):
    served.payloads[dlib_models.FILES[0].name] = bz2.compress(b"tampered")

    with pytest.raises(SystemExit) as exit_info:
        _run_fetch_command(monkeypatch, json_mode=True)

    assert exit_info.value.code == 1
    reply = json.loads(capsys.readouterr().out)
    assert reply["ok"] is False
    assert reply["error"]["code"] == "fetch_failed"
