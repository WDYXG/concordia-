"""Contract tests for optional local neural memory embeddings."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from concordia_riverbend.memory import FastEmbedTextEmbedder
from concordia_riverbend.memory import WorldMemory
from concordia_riverbend.scenarios.riverbend_world import (
    build_riverbend_world,
)


class _FakeFastEmbedBackend:
    def embed(self, texts: list[str]):
        for text in texts:
            yield np.asarray(
                [float(len(text)), 2.0, 1.0],
                dtype=np.float32,
            )


class FastEmbedTextEmbedderTest(unittest.TestCase):
    def test_normalizes_backend_vectors_without_downloading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            embedder = FastEmbedTextEmbedder(
                cache_dir=Path(directory),
                backend=_FakeFastEmbedBackend(),
            )
            vector = embedder("semantic memory")

        self.assertEqual(vector.shape, (3,))
        self.assertEqual(embedder.dimensions, 3)
        self.assertAlmostEqual(float(np.linalg.norm(vector)), 1.0)
        self.assertIn("paraphrase-multilingual", embedder.name)

    def test_world_memory_records_selected_embedder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            embedder = FastEmbedTextEmbedder(
                cache_dir=Path(directory),
                backend=_FakeFastEmbedBackend(),
            )
            memory = WorldMemory(
                build_riverbend_world(),
                embedder=embedder,
            )

        state = memory.to_dict()
        self.assertTrue(
            all(
                value["embedder"] == embedder.name
                for value in state.values()
            )
        )


if __name__ == "__main__":
    unittest.main()
