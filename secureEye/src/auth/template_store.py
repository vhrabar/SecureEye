from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from numpy.typing import NDArray

import paths_factory

#: Schema version written by this module.
STORE_VERSION = 2

#: Embedding space of the legacy dlib ResNet recognizer.
LEGACY_MODEL_ID = "dlib-resnet-v1"

#: Embedding space per legacy ``[core] detector_backend``.
LEGACY_MODEL_IDS = {
    "dlib": LEGACY_MODEL_ID,
    "mediapipe": "mediapipe-landmarks-v1",
}

_FILE_MODE = 0o600


class TemplateStoreError(Exception):
    """Base class for template store errors."""


class TemplateFileNotFound(TemplateStoreError):
    """Raised when no template file exists for the user."""


class EmptyTemplateStore(TemplateStoreError):
    """Raised when the template file exists but holds no usable templates."""


class TemplateSchemaError(TemplateStoreError):
    """Raised when the stored JSON shape is invalid."""


class TemplateSpaceMismatch(TemplateStoreError):
    """Raised when a user has templates, but none in the active embedding space."""


@dataclass(frozen=True)
class Template:
    """One enrolled model: its metadata and the vectors captured for it."""

    id: int
    label: str
    created: int
    model_id: str
    embeddings: NDArray[np.float32]

    @property
    def dim(self) -> int:
        return int(self.embeddings.shape[1])


@dataclass(frozen=True)
class TemplateSet:
    """Every template of one user that lives in a single embedding space."""

    model_id: str
    templates: list[Template]
    #: All vectors stacked as (N, dim) for nearest-neighbour matching.
    matrix: NDArray[np.float32]
    #: Row index into ``matrix`` -> index into ``templates``.
    owners: NDArray[np.intp]

    def __len__(self) -> int:
        return len(self.templates)

    def owner_of(self, row: int) -> Template | None:
        """
        Return the template a matrix row came from, or ``None`` if out of range.
        :param row: the row index
        :return: the template, or ``None``
        """
        if 0 <= row < self.owners.shape[0]:
            return self.templates[int(self.owners[row])]
        return None


def active_model_id(config) -> str:
    """
    Return the embedding space implied by ``config``.

    :param config: the config to read
    :return: the embedding space ID
    """
    pipeline = config.get("core", "pipeline", fallback="legacy").strip().lower()
    if pipeline != "legacy":
        return config.get("recognition", "model_id", fallback="sface-2021dec").strip()

    backend = config.get("core", "detector_backend", fallback="dlib").strip().lower()
    return LEGACY_MODEL_IDS.get(backend, f"legacy-{backend}")


def load(user: str, *, model_id: str) -> TemplateSet:
    """Load the templates of ``user`` that live in ``model_id``'s space.

    :param user: the user to load the templates for
    :param model_id: the embedding space to load the templates for
    :return: the template set for given user and space
    """
    templates = _parse(_read_payload(_path_for(user)), default_model_id=model_id)
    matching = [template for template in templates if template.model_id == model_id]

    if not matching:
        known = ", ".join(sorted({template.model_id for template in templates}))
        raise TemplateSpaceMismatch(
            f"Face models for {user} were made with {known}, "
            f"but {model_id} is active; re-enrollment is required"
        )

    matrix, owners = _stack(matching)
    return TemplateSet(model_id=model_id, templates=matching, matrix=matrix, owners=owners)


def load_all(user: str) -> list[Template]:
    """
    Load every template of ``user``, whatever space it belongs to.

    :param user: the user to load the templates for
    :return: the list of templates for givven user
    """
    return _parse(_read_payload(_path_for(user)), default_model_id=LEGACY_MODEL_ID)


def save(user: str, templates: Sequence[Template]) -> None:
    """
    Write ``templates`` as the complete template set of ``user``.
    :param user: the user to save the template set for
    :param templates: the templates to save
    :return: None
    """
    path = _path_for(user)
    payload = {
        "version": STORE_VERSION,
        "templates": [_serialize(template) for template in templates],
    }
    _write_json(path, payload)


def delete(user: str) -> None:
    """
    Remove the template file of ``user`` entirely.
    :param user: the user to delete the template file for
    :return: None
    """
    try:
        os.remove(_path_for(user))
    except FileNotFoundError as exc:
        raise TemplateFileNotFound(f"Template file not found: {_path_for(user)}") from exc


def append(
    user: str,
    *,
    model_id: str,
    label: str,
    embeddings: Any,
    created: int | None = None,
) -> Template:
    """
    Add one template to ``user``'s set and persist it. Returns the new template.
    :param user: the user to add the template to
    :param model_id: the embedding space of the template
    :param label: the label of the template
    :param embeddings: the encodings of the template
    :param created: the time the template was created, or ``None`` for now
    :return: the new template
    """
    vectors = np.atleast_2d(np.asarray(embeddings, dtype=np.float32))
    if vectors.ndim != 2 or vectors.shape[0] == 0 or vectors.shape[1] == 0:
        raise TemplateSchemaError(f"Expected a non-empty (n, dim) array, got {vectors.shape}")
    if not np.all(np.isfinite(vectors)):
        raise TemplateSchemaError("Encoding contains non-finite values")

    try:
        existing = load_all(user)
    except (TemplateFileNotFound, EmptyTemplateStore):
        existing = []

    template = Template(
        id=next_id(existing),
        label=label,
        created=int(time.time()) if created is None else created,
        model_id=model_id,
        embeddings=vectors,
    )
    save(user, [*existing, template])
    return template


def next_id(templates: Sequence[Template]) -> int:
    """
    Return the id to give the next template. IDs may have gaps; the last is the max.
    :param templates: the existing templates
    :return: the next id to use
    """
    return templates[-1].id + 1 if templates else 0


def find(templates: Iterable[Template], template_id: int) -> Template | None:
    """
    Return the template with ``template_id``, or ``None``.
    :param templates: the templates to search
    :param template_id: the id to search for
    :return: the template, or ``None``
    """
    for template in templates:
        if template.id == template_id:
            return template
    return None


def _path_for(user: str) -> Path:
    return Path(paths_factory.user_model_path(user))


def _read_payload(path: Path) -> Any:
    """
    Read the JSON payload from ``path``.
    :param path: the file to read
    :return: the JSON payload
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise TemplateFileNotFound(f"Template file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TemplateSchemaError(f"Template file is not valid JSON: {path}") from exc


def _parse(payload: Any, *, default_model_id: str) -> list[Template]:
    """
    Parse raw JSON payload into a list of templates.
    :param payload: the JSON payload
    :param default_model_id: the default model ID to use if none is specified in the payload
    :return: the parsed templates
    """
    if isinstance(payload, list):
        entries: Any = payload
    elif isinstance(payload, dict):
        version = payload.get("version")
        if version != STORE_VERSION:
            raise TemplateSchemaError(f"Unsupported template store version: {version!r}")
        entries = payload.get("templates")
        if not isinstance(entries, list):
            raise TemplateSchemaError("Template file must have a list field 'templates'")
    else:
        raise TemplateSchemaError("Template file must contain a JSON object or list")

    if not entries:
        raise EmptyTemplateStore("No face models found")

    return [_parse_template(index, entry, default_model_id) for index, entry in enumerate(entries)]


def _parse_template(index: int, entry: Any, default_model_id: str) -> Template:
    """
    Parse one template from the payload.
    :param index: the index of the template in the payload
    :param entry: the template object
    :param default_model_id: the default model ID to use if none is specified in the payload
    """
    if not isinstance(entry, dict):
        raise TemplateSchemaError(f"Face model at index {index} is not an object")

    data = entry.get("data")
    if not isinstance(data, list):
        raise TemplateSchemaError(f"Face model at index {index} missing list field 'data'")

    vectors = _parse_vectors(index, data)

    declared_dim = entry.get("dim")
    if isinstance(declared_dim, int) and declared_dim != vectors.shape[1]:
        raise TemplateSchemaError(
            f"Face model at index {index} declares dim {declared_dim}, holds {vectors.shape[1]}"
        )

    model_id = entry.get("model_id")
    if model_id is not None and not isinstance(model_id, str):
        raise TemplateSchemaError(f"Face model at index {index} has a non-string 'model_id'")

    return Template(
        id=int(entry.get("id", index)),
        label=str(entry.get("label", "")),
        created=int(entry.get("created", entry.get("time", 0))),
        model_id=model_id or default_model_id,
        embeddings=np.vstack(vectors).astype(np.float32, copy=False),
    )


def _parse_vectors(index: int, data: list[Any]) -> NDArray[np.float32]:
    """
    Validate one template's encodings and stack them into a (n, dim) array.
    :param index: the index of the template in the payload
    :param data: the list of encodings
    :return: the stacked encodings as a (n, dim) array
    """
    vectors: list[NDArray[np.float32]] = []
    expected_dim: int | None = None

    for position, vector in enumerate(data):
        arr = np.asarray(vector, dtype=np.float32)
        where = f"model[{index}]['data'][{position}]"
        if arr.ndim != 1:
            raise TemplateSchemaError(f"Encoding at {where} is not 1D")
        if arr.size == 0:
            raise TemplateSchemaError(f"Encoding at {where} is empty")
        if not np.all(np.isfinite(arr)):
            raise TemplateSchemaError(f"Encoding at {where} has invalid values")
        if expected_dim is None:
            expected_dim = int(arr.size)
        elif expected_dim != int(arr.size):
            raise TemplateSchemaError(
                f"Inconsistent encoding dimension: expected {expected_dim}, got {arr.size}"
            )
        vectors.append(arr)

    if not vectors:
        raise TemplateSchemaError(f"Face model at index {index} has no encodings")

    return np.vstack(vectors).astype(np.float32, copy=False)


def _stack(templates: Sequence[Template]) -> tuple[NDArray[np.float32], NDArray[np.intp]]:
    """
    Stack all encodings of ``templates`` into a (n, dim) array and return the row indices.
    :param templates: the templates to stack
    :return: (matrix, owners) where matrix is (n, dim) and owners is (n,) row indices into templates
    """
    expected_dim = templates[0].dim
    for template in templates[1:]:
        if template.dim != expected_dim:
            raise TemplateSchemaError(
                f"Inconsistent encoding dimension: expected {expected_dim}, got {template.dim}"
            )

    matrix = np.vstack([template.embeddings for template in templates]).astype(
        np.float32, copy=False
    )
    owners = np.repeat(
        np.arange(len(templates), dtype=np.intp),
        [template.embeddings.shape[0] for template in templates],
    )
    return matrix, owners


def _serialize(template: Template) -> dict[str, Any]:
    """
    Serialize a template for storage.
    :param template: the template to serialize
    :return: the serialized template
    """
    return {
        "id": template.id,
        "label": template.label,
        "created": template.created,
        "model_id": template.model_id,
        "dim": template.dim,
        "data": template.embeddings.tolist(),
    }


def _write_json(path: Path, payload: Any) -> None:
    """
    Write ``payload`` so an interrupted write cannot destroy the existing file.
    :param path: the file to write
    :param payload: the data to write
    :return: None
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle_fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, _FILE_MODE)
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
