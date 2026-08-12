"""Structured episodic, semantic, and social memory for world Agents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from concordia_riverbend.core.models import AgentSpec
from concordia_riverbend.core.models import ScenarioSpec
from concordia_riverbend.core.models import WorldEvent
from concordia_riverbend.memory.hash_embedder import HashingTextEmbedder


_SEMANTIC_EVENT_TYPES = {
    "public_announcement",
    "information_treatment",
    "inspection",
}
_SOCIAL_EVENT_TYPES = {
    "public_statement",
    "private_message",
}
_IMPORTANCE_BY_EVENT_TYPE = {
    "information_treatment": 0.95,
    "secret_ballot": 0.85,
    "public_announcement": 0.8,
    "private_message": 0.7,
    "public_statement": 0.6,
    "inspection": 0.55,
    "movement": 0.25,
}


class TextEmbedder(Protocol):
    """Minimal embedding contract used by Agent memory."""

    @property
    def name(self) -> str:
        """Return a stable backend description for run provenance."""

    def __call__(self, text: str) -> np.ndarray:
        """Map text to one normalized dense vector."""


@dataclass(frozen=True)
class MemoryRecord:
    """One trace with type, source provenance, and retrieval metadata."""

    memory_id: str
    agent_id: str
    memory_type: str
    content: str
    round_index: int
    event_id: str | None = None
    source_agent_id: str | None = None
    source_event_id: str | None = None
    importance: float = 0.5
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.memory_type not in {"episodic", "semantic", "social"}:
            raise ValueError(f"Unknown memory type: {self.memory_type!r}.")
        if not 0.0 <= self.importance <= 1.0:
            raise ValueError("importance must be between 0 and 1.")
        if self.round_index < 0:
            raise ValueError("round_index must be non-negative.")
        if not self.content.strip():
            raise ValueError("Memory content must not be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "agent_id": self.agent_id,
            "memory_type": self.memory_type,
            "content": self.content,
            "round_index": self.round_index,
            "event_id": self.event_id,
            "source_agent_id": self.source_agent_id,
            "source_event_id": self.source_event_id,
            "importance": self.importance,
            "metadata": dict(self.metadata or {}),
        }


def _memory_type_for(event: WorldEvent) -> str:
    if event.event_type in _SEMANTIC_EVENT_TYPES:
        return "semantic"
    if event.event_type in _SOCIAL_EVENT_TYPES:
        return "social"
    return "episodic"


class AgentEventMemory:
    """Queryable event memory for one Agent."""

    def __init__(
        self,
        *,
        agent: AgentSpec,
        embedder: TextEmbedder | None = None,
    ) -> None:
        self.agent = agent
        self._embedder = embedder or HashingTextEmbedder()
        self._records: list[MemoryRecord] = []
        self._vectors: dict[str, np.ndarray] = {}
        self._event_ids: set[str] = set()
        for index, content in enumerate(agent.initial_memories):
            self._append(
                MemoryRecord(
                    memory_id=f"initial_{agent.agent_id}_{index:03d}",
                    agent_id=agent.agent_id,
                    memory_type="episodic",
                    content=content,
                    round_index=0,
                    importance=0.65,
                    metadata={"origin": "initial_memory"},
                )
            )

    @property
    def records(self) -> tuple[MemoryRecord, ...]:
        return tuple(self._records)

    def _append(self, record: MemoryRecord) -> None:
        if any(
            existing.memory_id == record.memory_id
            for existing in self._records
        ):
            raise ValueError(f"Duplicate memory ID: {record.memory_id!r}.")
        self._records.append(record)
        self._vectors[record.memory_id] = self._embedder(record.content)

    def observe(self, events: Sequence[WorldEvent]) -> None:
        for event in events:
            if event.event_id in self._event_ids:
                continue
            record = MemoryRecord(
                memory_id=f"event_{self.agent.agent_id}_{event.event_id}",
                agent_id=self.agent.agent_id,
                memory_type=_memory_type_for(event),
                content=event.content,
                round_index=event.round_index,
                event_id=event.event_id,
                source_agent_id=event.actor_id,
                source_event_id=(
                    str(event.metadata["source_event_id"])
                    if event.metadata.get("source_event_id")
                    else None
                ),
                importance=_IMPORTANCE_BY_EVENT_TYPE.get(
                    event.event_type,
                    0.5,
                ),
                metadata={
                    "event_type": event.event_type,
                    "location_id": event.location_id,
                    **dict(event.metadata),
                },
            )
            self._append(record)
            self._event_ids.add(event.event_id)

    def retrieve(
        self,
        query: str,
        *,
        current_round: int,
        limit: int = 5,
    ) -> tuple[MemoryRecord, ...]:
        if limit < 1:
            raise ValueError("limit must be at least 1.")
        query_vector = self._embedder(query)
        scored: list[tuple[float, MemoryRecord]] = []
        for record in self._records:
            relevance = float(
                np.dot(query_vector, self._vectors[record.memory_id])
            )
            relevance = max(0.0, relevance)
            age = max(0, current_round - record.round_index)
            recency = 1.0 / (1.0 + age)
            score = (
                0.65 * relevance
                + 0.2 * recency
                + 0.15 * record.importance
            )
            scored.append((score, record))
        scored.sort(
            key=lambda item: (
                item[0],
                item[1].round_index,
                item[1].memory_id,
            ),
            reverse=True,
        )
        return tuple(record for _, record in scored[:limit])

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent.agent_id,
            "embedder": self._embedder.name,
            "records": [record.to_dict() for record in self._records],
        }


class WorldMemory:
    """Coordinates isolated Agent memories without sharing private traces."""

    def __init__(
        self,
        scenario: ScenarioSpec,
        *,
        embedder: TextEmbedder | None = None,
    ) -> None:
        shared_embedder = embedder or HashingTextEmbedder()
        self._memories = {
            agent.agent_id: AgentEventMemory(
                agent=agent,
                embedder=shared_embedder,
            )
            for agent in scenario.agents
        }

    def observe(
        self,
        agent_id: str,
        events: Sequence[WorldEvent],
    ) -> None:
        self._memories[agent_id].observe(events)

    def recall(
        self,
        agent_id: str,
        query: str,
        *,
        current_round: int,
        limit: int = 5,
    ) -> tuple[Mapping[str, Any], ...]:
        return tuple(
            record.to_dict()
            for record in self._memories[agent_id].retrieve(
                query,
                current_round=current_round,
                limit=limit,
            )
        )

    def records_for(self, agent_id: str) -> tuple[MemoryRecord, ...]:
        return self._memories[agent_id].records

    def to_dict(self) -> dict[str, Any]:
        return {
            agent_id: memory.to_dict()
            for agent_id, memory in self._memories.items()
        }
