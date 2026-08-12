"""Small deterministic text embedder for local Concordia experiments."""

from __future__ import annotations

import hashlib
import re

import numpy as np


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]", re.IGNORECASE)


class HashingTextEmbedder:
    """Maps lexical features into a normalized fixed-dimensional vector.

    This is intentionally lightweight. It preserves word and adjacent-token
    overlap, but it does not understand synonyms like a neural embedding model.
    """

    def __init__(self, dimensions: int = 512) -> None:
        if dimensions < 32:
            raise ValueError("dimensions must be at least 32.")
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def name(self) -> str:
        return f"hashing:{self._dimensions}"

    def _features(self, text: str) -> list[str]:
        tokens = [token.lower() for token in _TOKEN_PATTERN.findall(text)]
        if not tokens:
            return ["__empty__"]
        bigrams = [
            f"{left}::{right}" for left, right in zip(tokens, tokens[1:])
        ]
        return tokens + bigrams

    def __call__(self, text: str) -> np.ndarray:
        vector = np.zeros(self._dimensions, dtype=np.float32)
        for feature in self._features(text):
            digest = hashlib.blake2b(
                feature.encode("utf-8"), digest_size=16
            ).digest()
            index = int.from_bytes(digest[:8], "little") % self._dimensions
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[index] += sign

        norm = float(np.linalg.norm(vector))
        if norm:
            vector /= norm
        return vector
