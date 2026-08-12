from __future__ import annotations

import unittest

from concordia.associative_memory.basic_associative_memory import (
    AssociativeMemoryBank,
)
import numpy as np

from concordia_riverbend.memory.hash_embedder import HashingTextEmbedder


class HashingTextEmbedderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.embedder = HashingTextEmbedder(dimensions=512)

    def test_is_deterministic_and_normalized(self) -> None:
        first = self.embedder("Alice protects the river.")
        second = self.embedder("Alice protects the river.")

        np.testing.assert_array_equal(first, second)
        self.assertEqual(first.shape, (512,))
        self.assertAlmostEqual(float(np.linalg.norm(first)), 1.0, places=6)

    def test_related_text_has_higher_similarity(self) -> None:
        query = self.embedder("river protection and the environment")
        related = self.embedder(
            "Alice supports river protection and the environment"
        )
        unrelated = self.embedder(
            "Bob wants a factory and lower business taxes"
        )

        related_score = float(np.dot(query, related))
        unrelated_score = float(np.dot(query, unrelated))
        self.assertGreater(related_score, unrelated_score)

    def test_integrates_with_concordia_associative_memory(self) -> None:
        memory = AssociativeMemoryBank(self.embedder)
        alice_memory = (
            "Alice promised river protection and environmental restoration."
        )
        bob_memory = (
            "Bob proposed a new factory and lower business taxes."
        )
        memory.extend([alice_memory, bob_memory])

        retrieved = memory.retrieve_associative(
            "Which candidate supports river protection?", k=1
        )

        self.assertEqual(retrieved, [alice_memory])

    def test_empty_text_is_still_a_valid_vector(self) -> None:
        vector = self.embedder("")
        self.assertEqual(vector.shape, (512,))
        self.assertAlmostEqual(float(np.linalg.norm(vector)), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
