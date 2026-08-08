import sys
from pathlib import Path

import numpy as np
import pytest

# Path setup
SRC_DIR = str(Path(__file__).resolve().parents[2] / "secureEye" / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from auth.interfaces import Embedding, Face, Recognizer  # noqa: E402


def _landmarks(fill: float = 0.0) -> np.ndarray:
    return np.full((5, 2), fill, dtype=np.float32)


class TestFace:
    def test_equality_and_hashing_ignore_landmarks(self):
        """Comparing ndarray fields field-wise raises; landmarks stay out of it."""
        a = Face((0, 0, 10, 10), _landmarks(0.0), 0.9)
        b = Face((0, 0, 10, 10), _landmarks(1.0), 0.9)

        assert a == b
        assert hash(a) == hash(b)
        assert len({a, b}) == 1

    def test_differing_boxes_are_not_equal(self):
        assert Face((0, 0, 10, 10)) != Face((0, 0, 11, 10))

    def test_landmarks_are_optional(self):
        face = Face((1, 2, 3, 4))

        assert face.has_landmarks is False
        assert face.landmarks.shape == (0, 2)
        assert face.score == 1.0

    def test_landmarks_present(self):
        assert Face((1, 2, 3, 4), _landmarks()).has_landmarks is True

    def test_malformed_landmarks_rejected(self):
        with pytest.raises(ValueError, match=r"shape \(N, 2\)"):
            Face((0, 0, 1, 1), np.zeros((5, 3), dtype=np.float32))


class TestEmbedding:
    def test_normalized_produces_unit_vector(self):
        embedding = Embedding.normalized(np.array([3.0, 0.0, 4.0]), "dlib-resnet-v1")

        assert embedding.dim == 3
        assert embedding.model_id == "dlib-resnet-v1"
        assert np.allclose(embedding.vector, [0.6, 0.0, 0.8])
        assert embedding.vector.dtype == np.float32

    def test_normalized_flattens_and_rejects_zero(self):
        assert Embedding.normalized(np.ones((1, 4)), "m").vector.shape == (4,)

        with pytest.raises(ValueError, match="zero-length"):
            Embedding.normalized(np.zeros(4), "m")

    def test_dim_must_match_vector(self):
        with pytest.raises(ValueError, match="expected 128"):
            Embedding(np.zeros(3, dtype=np.float32), "m", 128)

    def test_non_1d_vector_rejected(self):
        with pytest.raises(ValueError, match="must be 1-D"):
            Embedding(np.zeros((2, 2), dtype=np.float32), "m", 2)

    def test_cosine_is_bounded(self):
        same = Embedding.normalized(np.array([1.0, 0.0]), "m")
        opposite = Embedding.normalized(np.array([-1.0, 0.0]), "m")
        orthogonal = Embedding.normalized(np.array([0.0, 1.0]), "m")

        assert same.cosine(same) == 1.0
        assert same.cosine(opposite) == -1.0
        assert same.cosine(orthogonal) == 0.0

    def test_cosine_refuses_foreign_embedding_space(self):
        dlib = Embedding.normalized(np.array([1.0, 0.0]), "dlib-resnet-v1")
        sface = Embedding.normalized(np.array([1.0, 0.0]), "sface-2021dec")

        with pytest.raises(ValueError, match="embedding space mismatch"):
            dlib.cosine(sface)


class TestRecognizerContract:
    def test_missing_model_id_blocks_instantiation(self):
        """model_id is stamped into stored templates, so it may not be forgotten."""

        class Incomplete(Recognizer):
            def embed(self, frame, face):
                raise NotImplementedError

        with pytest.raises(TypeError, match="model_id"):
            Incomplete()

    def test_class_attributes_satisfy_the_contract(self):
        class Complete(Recognizer):
            model_id = "dlib-resnet-v1"
            dim = 128

            def embed(self, frame, face):
                return Embedding.normalized(np.ones(self.dim), self.model_id)

        recognizer = Complete()

        assert recognizer.model_id == "dlib-resnet-v1"
        assert recognizer.embed(None, Face((0, 0, 1, 1))).dim == 128
