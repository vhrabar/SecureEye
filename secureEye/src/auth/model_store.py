from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from .template_store import (
    LEGACY_MODEL_ID,
    EmptyTemplateStore,
    TemplateFileNotFound,
    TemplateSchemaError,
    TemplateSpaceMismatch,
    TemplateStoreError,
    load,
)

ModelStoreError = TemplateStoreError
ModelFileNotFound = TemplateFileNotFound
EmptyModelStore = EmptyTemplateStore
ModelSchemaError = TemplateSchemaError

__all__ = [
    "ModelStoreError",
    "ModelFileNotFound",
    "EmptyModelStore",
    "ModelSchemaError",
    "load_user_models",
]


def load_user_models(user: str) -> tuple[list[dict[str, Any]], NDArray[np.float32]]:
    """Load legacy-space models and flattened encodings for nearest-neighbor matching.

    Deprecated: call :func:`auth.template_store.load` and use the returned
    :class:`~auth.template_store.TemplateSet` directly.
    """
    try:
        templates = load(user, model_id=LEGACY_MODEL_ID)
    except TemplateSpaceMismatch as exc:
        raise EmptyModelStore(str(exc)) from exc

    models = [
        {
            "id": template.id,
            "label": template.label,
            "time": template.created,
            "data": template.embeddings.tolist(),
        }
        for template in templates.templates
    ]
    return models, templates.matrix
