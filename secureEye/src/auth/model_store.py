"""Model loading and validation for compare flow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

import paths_factory


class ModelStoreError(Exception):
    """Base class for model store errors."""


class ModelFileNotFound(ModelStoreError):
    """Raised when no model file exists for the user."""


class EmptyModelStore(ModelStoreError):
    """Raised when model file exists but contains no usable models."""


class ModelSchemaError(ModelStoreError):
    """Raised when model JSON shape is invalid."""


def _read_payload(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise ModelFileNotFound(f"Model file not found: {path}") from exc


def _ensure_models(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ModelSchemaError("Model file must contain a JSON list")
    if not payload:
        raise EmptyModelStore("No models found")

    models: list[dict[str, Any]] = []
    for idx, model in enumerate(payload):
        if not isinstance(model, dict):
            raise ModelSchemaError(f"Model at index {idx} is not an object")
        data = model.get("data")
        if not isinstance(data, list):
            raise ModelSchemaError(f"Model at index {idx} missing list field 'data'")
        models.append(model)
    return models


def _flatten_encodings(models: list[dict[str, Any]]) -> NDArray[np.float32]:
    rows: list[np.ndarray] = []
    expected_dim: int | None = None

    for model_index, model in enumerate(models):
        for sample_index, vector in enumerate(model["data"]):
            arr = np.asarray(vector, dtype=np.float32)
            if arr.ndim != 1:
                raise ModelSchemaError(
                    f"Encoding at model[{model_index}]['data'][{sample_index}] is not 1D"
                )
            if arr.size == 0:
                raise ModelSchemaError(
                    f"Encoding at model[{model_index}]['data'][{sample_index}] is empty"
                )
            if not np.all(np.isfinite(arr)):
                raise ModelSchemaError(
                    f"Encoding at model[{model_index}]['data'][{sample_index}] has invalid values"
                )
            if expected_dim is None:
                expected_dim = int(arr.size)
            elif expected_dim != int(arr.size):
                raise ModelSchemaError(
                    f"Inconsistent encoding dimension: expected {expected_dim}, got {arr.size}"
                )
            rows.append(arr)

    if not rows:
        raise EmptyModelStore("No encodings found")

    return np.vstack(rows).astype(np.float32, copy=False)


def load_user_models(user: str) -> tuple[list[dict[str, Any]], NDArray[np.float32]]:
    """Load user models and flattened encodings for nearest-neighbor matching."""
    payload = _read_payload(Path(paths_factory.user_model_path(user)))
    models = _ensure_models(payload)
    return models, _flatten_encodings(models)
