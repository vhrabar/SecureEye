import configparser
import json
import os
import stat
import sys
from pathlib import Path

import numpy as np
import pytest

# Path setup
SRC_DIR = str(Path(__file__).resolve().parents[2] / "secureEye" / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from auth import template_store  # noqa: E402
from auth.template_store import (  # noqa: E402
    LEGACY_MODEL_ID,
    STORE_VERSION,
    EmptyTemplateStore,
    TemplateFileNotFound,
    TemplateSchemaError,
    TemplateSpaceMismatch,
)

SFACE = "sface-2021dec"


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point the store at a temporary models directory."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    monkeypatch.setattr(
        template_store.paths_factory,
        "user_model_path",
        lambda user: str(models_dir / f"{user}.dat"),
    )
    return models_dir


def _vector(fill: float, dim: int = 128) -> list[float]:
    return [fill] * dim


def _write_raw(store_dir: Path, user: str, payload) -> Path:
    path = store_dir / f"{user}.dat"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _legacy_file(store_dir: Path, user: str = "ada"):
    return _write_raw(
        store_dir,
        user,
        [{"time": 1700000000, "label": "Initial model", "id": 0, "data": [_vector(0.5)]}],
    )


class TestLegacyFiles:
    def test_bare_list_still_loads(self, store):
        _legacy_file(store)

        templates = template_store.load("ada", model_id=LEGACY_MODEL_ID)

        assert len(templates) == 1
        assert templates.templates[0].label == "Initial model"
        assert templates.templates[0].created == 1700000000
        assert templates.matrix.shape == (1, 128)

    def test_untagged_templates_adopt_the_requested_space(self, store):
        """A v1 file carries no tag, so its space is unknown, not wrong."""
        _legacy_file(store)

        templates = template_store.load("ada", model_id=SFACE)

        assert templates.model_id == SFACE
        assert len(templates) == 1

    def test_load_all_reports_untagged_as_legacy(self, store):
        _legacy_file(store)

        assert template_store.load_all("ada")[0].model_id == LEGACY_MODEL_ID


class TestSpaceFiltering:
    def test_mixed_spaces_filter_to_the_active_one(self, store):
        _write_raw(
            store,
            "ada",
            {
                "version": STORE_VERSION,
                "templates": [
                    {
                        "id": 0,
                        "label": "old",
                        "created": 1,
                        "model_id": LEGACY_MODEL_ID,
                        "data": [_vector(0.1)],
                    },
                    {
                        "id": 1,
                        "label": "new",
                        "created": 2,
                        "model_id": SFACE,
                        "data": [_vector(0.2)],
                    },
                ],
            },
        )

        assert [t.label for t in template_store.load("ada", model_id=SFACE).templates] == ["new"]
        assert len(template_store.load_all("ada")) == 2

    def test_wrong_space_raises_instead_of_mis_scoring(self, store):
        _write_raw(
            store,
            "ada",
            {
                "version": STORE_VERSION,
                "templates": [
                    {
                        "id": 0,
                        "label": "old",
                        "created": 1,
                        "model_id": LEGACY_MODEL_ID,
                        "data": [_vector(0.1)],
                    }
                ],
            },
        )

        with pytest.raises(TemplateSpaceMismatch, match="re-enrollment is required"):
            template_store.load("ada", model_id=SFACE)

    def test_mismatch_message_names_both_spaces(self, store):
        _write_raw(
            store,
            "ada",
            {
                "version": STORE_VERSION,
                "templates": [
                    {
                        "id": 0,
                        "label": "old",
                        "created": 1,
                        "model_id": LEGACY_MODEL_ID,
                        "data": [_vector(0.1)],
                    }
                ],
            },
        )

        with pytest.raises(TemplateSpaceMismatch) as excinfo:
            template_store.load("ada", model_id=SFACE)

        assert LEGACY_MODEL_ID in str(excinfo.value)
        assert SFACE in str(excinfo.value)


class TestOwners:
    def test_rows_map_back_to_their_template(self, store):
        _write_raw(
            store,
            "ada",
            {
                "version": STORE_VERSION,
                "templates": [
                    {
                        "id": 0,
                        "label": "first",
                        "created": 1,
                        "model_id": SFACE,
                        "data": [_vector(0.1), _vector(0.2)],
                    },
                    {
                        "id": 7,
                        "label": "second",
                        "created": 2,
                        "model_id": SFACE,
                        "data": [_vector(0.3)],
                    },
                ],
            },
        )

        templates = template_store.load("ada", model_id=SFACE)

        assert templates.matrix.shape == (3, 128)
        assert [templates.owner_of(row).label for row in range(3)] == [
            "first",
            "first",
            "second",
        ]
        assert templates.owner_of(3) is None
        assert templates.owner_of(-1) is None


class TestSchemaValidation:
    def test_missing_file(self, store):
        with pytest.raises(TemplateFileNotFound):
            template_store.load("ghost", model_id=SFACE)

    def test_empty_list(self, store):
        _write_raw(store, "ada", [])

        with pytest.raises(EmptyTemplateStore):
            template_store.load("ada", model_id=SFACE)

    def test_malformed_json(self, store):
        (store / "ada.dat").write_text("{not json", encoding="utf-8")

        with pytest.raises(TemplateSchemaError, match="not valid JSON"):
            template_store.load("ada", model_id=SFACE)

    def test_unknown_version(self, store):
        _write_raw(store, "ada", {"version": 99, "templates": []})

        with pytest.raises(TemplateSchemaError, match="Unsupported template store version"):
            template_store.load("ada", model_id=SFACE)

    def test_non_finite_values(self, store):
        _write_raw(
            store, "ada", [{"time": 1, "label": "x", "id": 0, "data": [[float("nan")] * 128]}]
        )

        with pytest.raises(TemplateSchemaError, match="invalid values"):
            template_store.load("ada", model_id=SFACE)

    def test_ragged_encodings_within_a_template(self, store):
        _write_raw(
            store,
            "ada",
            [{"time": 1, "label": "x", "id": 0, "data": [_vector(0.1, 128), _vector(0.1, 64)]}],
        )

        with pytest.raises(TemplateSchemaError, match="Inconsistent encoding dimension"):
            template_store.load("ada", model_id=SFACE)

    def test_declared_dim_must_match_the_data(self, store):
        _write_raw(
            store,
            "ada",
            {
                "version": STORE_VERSION,
                "templates": [
                    {
                        "id": 0,
                        "label": "x",
                        "created": 1,
                        "model_id": SFACE,
                        "dim": 512,
                        "data": [_vector(0.1)],
                    }
                ],
            },
        )

        with pytest.raises(TemplateSchemaError, match="declares dim 512"):
            template_store.load("ada", model_id=SFACE)

    def test_dimensions_must_agree_across_templates(self, store):
        _write_raw(
            store,
            "ada",
            {
                "version": STORE_VERSION,
                "templates": [
                    {
                        "id": 0,
                        "label": "a",
                        "created": 1,
                        "model_id": SFACE,
                        "data": [_vector(0.1, 128)],
                    },
                    {
                        "id": 1,
                        "label": "b",
                        "created": 2,
                        "model_id": SFACE,
                        "data": [_vector(0.1, 64)],
                    },
                ],
            },
        )

        with pytest.raises(TemplateSchemaError, match="Inconsistent encoding dimension"):
            template_store.load("ada", model_id=SFACE)


class TestWriting:
    def test_append_round_trips(self, store):
        template_store.append(
            "ada", model_id=SFACE, label="Initial model", embeddings=np.full(128, 0.5)
        )

        templates = template_store.load("ada", model_id=SFACE)

        assert len(templates) == 1
        assert templates.templates[0].id == 0
        assert templates.templates[0].label == "Initial model"
        assert templates.templates[0].model_id == SFACE
        assert np.allclose(templates.matrix, 0.5)

    def test_append_writes_the_versioned_envelope(self, store):
        template_store.append("ada", model_id=SFACE, label="x", embeddings=np.zeros(128) + 0.1)

        payload = json.loads((store / "ada.dat").read_text(encoding="utf-8"))

        assert payload["version"] == STORE_VERSION
        assert payload["templates"][0]["model_id"] == SFACE
        assert payload["templates"][0]["dim"] == 128

    def test_ids_keep_climbing(self, store):
        template_store.append("ada", model_id=SFACE, label="a", embeddings=np.zeros(128) + 0.1)
        template_store.append("ada", model_id=SFACE, label="b", embeddings=np.zeros(128) + 0.2)

        assert [t.id for t in template_store.load_all("ada")] == [0, 1]

    def test_append_preserves_other_spaces(self, store):
        """Re-enrolling under a new model must not strip the rollback path."""
        _legacy_file(store)

        template_store.append("ada", model_id=SFACE, label="new", embeddings=np.zeros(128) + 0.2)

        assert len(template_store.load_all("ada")) == 2
        assert len(template_store.load("ada", model_id=LEGACY_MODEL_ID)) == 1
        assert len(template_store.load("ada", model_id=SFACE)) == 1

    def test_append_rejects_non_finite_encodings(self, store):
        with pytest.raises(TemplateSchemaError, match="non-finite"):
            template_store.append("ada", model_id=SFACE, label="x", embeddings=np.full(128, np.inf))

    def test_written_file_is_owner_only(self, store):
        template_store.append("ada", model_id=SFACE, label="x", embeddings=np.zeros(128) + 0.1)

        mode = stat.S_IMODE(os.stat(store / "ada.dat").st_mode)

        assert mode == 0o600

    def test_failed_write_leaves_the_old_file_intact(self, store, monkeypatch):
        template_store.append("ada", model_id=SFACE, label="keep", embeddings=np.zeros(128) + 0.1)
        original = (store / "ada.dat").read_bytes()

        def _boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(template_store.json, "dump", _boom)

        with pytest.raises(OSError):
            template_store.append("ada", model_id=SFACE, label="lost", embeddings=np.zeros(128))

        assert (store / "ada.dat").read_bytes() == original
        # The temporary file must not be left behind either
        assert list(store.iterdir()) == [store / "ada.dat"]

    def test_save_replaces_the_whole_set(self, store):
        template_store.append("ada", model_id=SFACE, label="a", embeddings=np.zeros(128) + 0.1)
        template_store.append("ada", model_id=SFACE, label="b", embeddings=np.zeros(128) + 0.2)

        remaining = [t for t in template_store.load_all("ada") if t.label == "b"]
        template_store.save("ada", remaining)

        assert [t.label for t in template_store.load_all("ada")] == ["b"]

    def test_delete_removes_the_file(self, store):
        template_store.append("ada", model_id=SFACE, label="a", embeddings=np.zeros(128) + 0.1)

        template_store.delete("ada")

        assert not (store / "ada.dat").exists()
        with pytest.raises(TemplateFileNotFound):
            template_store.delete("ada")


class TestHelpers:
    def test_next_id_and_find(self, store):
        _legacy_file(store)
        templates = template_store.load_all("ada")

        assert template_store.next_id(templates) == 1
        assert template_store.next_id([]) == 0
        assert template_store.find(templates, 0).label == "Initial model"
        assert template_store.find(templates, 99) is None


class TestActiveModelId:
    def _config(self, **sections) -> configparser.ConfigParser:
        config = configparser.ConfigParser()
        config.read_dict(sections)
        return config

    def test_defaults_to_legacy_dlib(self):
        assert template_store.active_model_id(self._config()) == LEGACY_MODEL_ID

    def test_mediapipe_is_its_own_space(self):
        """MediaPipe encodes landmarks, dlib encodes a ResNet vector -- both 128-d."""
        config = self._config(core={"detector_backend": "mediapipe"})

        assert template_store.active_model_id(config) == "mediapipe-landmarks-v1"

    def test_onnx_pipeline_reads_the_recognition_section(self):
        config = self._config(core={"pipeline": "onnx"}, recognition={"model_id": SFACE})

        assert template_store.active_model_id(config) == SFACE

    def test_unknown_legacy_backend_gets_a_distinct_id(self):
        config = self._config(core={"detector_backend": "somethingelse"})

        assert template_store.active_model_id(config) == "legacy-somethingelse"


class TestLegacyShim:
    def test_load_user_models_returns_the_old_shape(self, store):
        from auth.model_store import load_user_models

        _legacy_file(store)
        models, encodings = load_user_models("ada")

        assert models[0]["label"] == "Initial model"
        assert models[0]["time"] == 1700000000
        assert encodings.shape == (1, 128)

    def test_space_mismatch_surfaces_as_empty(self, store):
        from auth.model_store import EmptyModelStore, load_user_models

        _write_raw(
            store,
            "ada",
            {
                "version": STORE_VERSION,
                "templates": [
                    {
                        "id": 0,
                        "label": "new",
                        "created": 1,
                        "model_id": SFACE,
                        "data": [_vector(0.1)],
                    }
                ],
            },
        )

        with pytest.raises(EmptyModelStore):
            load_user_models("ada")
