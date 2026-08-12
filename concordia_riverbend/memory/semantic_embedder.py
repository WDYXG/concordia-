"""Local neural text embeddings backed by FastEmbed and ONNX Runtime."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any
import warnings

import numpy as np


DEFAULT_SEMANTIC_MODEL = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
DEFAULT_SEMANTIC_DIMENSIONS = 384


class FastEmbedTextEmbedder:
    """Generate normalized multilingual embeddings without a paid API."""

    def __init__(
        self,
        *,
        cache_dir: str | Path,
        model_name: str = DEFAULT_SEMANTIC_MODEL,
        local_files_only: bool = True,
        threads: int | None = None,
        backend: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = Path(cache_dir)
        self.local_files_only = local_files_only
        self._dimensions = DEFAULT_SEMANTIC_DIMENSIONS
        if backend is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as error:
                raise RuntimeError(
                    "FastEmbed is not installed. Run "
                    "`python -m pip install fastembed==0.8.0`."
                ) from error
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=(
                        "The model .* now uses mean pooling instead of "
                        "CLS embedding.*"
                    ),
                    category=UserWarning,
                )
                backend = TextEmbedding(
                    model_name=model_name,
                    cache_dir=str(self.cache_dir),
                    threads=threads,
                    local_files_only=local_files_only,
                )
        self._backend = backend

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def name(self) -> str:
        return f"fastembed:{self.model_name}"

    def embed_many(self, texts: Iterable[str]) -> tuple[np.ndarray, ...]:
        values = list(texts)
        if not values:
            return ()
        vectors = tuple(
            np.asarray(vector, dtype=np.float32)
            for vector in self._backend.embed(values)
        )
        if len(vectors) != len(values):
            raise RuntimeError(
                "FastEmbed returned a different number of vectors."
            )
        normalized: list[np.ndarray] = []
        for vector in vectors:
            if vector.ndim != 1:
                raise RuntimeError("FastEmbed returned a non-vector result.")
            norm = float(np.linalg.norm(vector))
            if not norm:
                raise RuntimeError("FastEmbed returned a zero vector.")
            normalized.append(vector / norm)
        if normalized:
            self._dimensions = int(normalized[0].shape[0])
        return tuple(normalized)

    def __call__(self, text: str) -> np.ndarray:
        return self.embed_many((text,))[0]


def semantic_model_cache(project_root: str | Path) -> Path:
    """Return the project-local model cache shared by scripts and runs."""

    return Path(project_root) / "models" / "fastembed"
