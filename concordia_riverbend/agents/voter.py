"""A minimal Concordia voter with associative memory."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from concordia.agents import entity_agent_with_logging
from concordia.associative_memory import basic_associative_memory
from concordia.components import agent as agent_components
from concordia.language_model import language_model
from concordia.prefabs.entity import minimal
from concordia.typing import entity

from concordia_riverbend.memory.hash_embedder import HashingTextEmbedder


@dataclass(frozen=True)
class VoterProfile:
    """Stable identity and formative memories for one simulated voter."""

    name: str
    background: str
    goal: str
    memories: tuple[str, ...]


@dataclass(frozen=True)
class BuiltVoter:
    """The Concordia entity together with the state used to build it."""

    profile: VoterProfile
    agent: entity_agent_with_logging.EntityAgentWithLogging
    memory_bank: basic_associative_memory.AssociativeMemoryBank


@dataclass(frozen=True)
class VoteDecision:
    """A validated candidate choice and the agent's short explanation."""

    candidate: str
    reason: str


def build_voter_agent(
    *,
    model: language_model.LanguageModel,
    profile: VoterProfile,
    memories_to_retrieve: int = 3,
) -> BuiltVoter:
    """Build one real Concordia EntityAgent from the official minimal prefab."""
    if memories_to_retrieve < 1:
        raise ValueError("memories_to_retrieve must be at least 1.")

    memory_bank = basic_associative_memory.AssociativeMemoryBank(
        sentence_embedder=HashingTextEmbedder()
    )
    memory_bank.extend(
        [f"[background] {profile.background}"]
        + [f"[memory] {memory}" for memory in profile.memories]
    )

    observation_key = (
        agent_components.observation.DEFAULT_OBSERVATION_COMPONENT_KEY
    )
    relevant_memories_key = "RelevantMemories"
    relevant_memories = (
        agent_components.all_similar_memories.AllSimilarMemories(
            model=model,
            components=(observation_key,),
            num_memories_to_retrieve=memories_to_retrieve,
            pre_act_label="\nRelevant memories",
        )
    )

    instructions = (
        f"You are {profile.name}, a resident of Riverbend. Stay in character. "
        "Use your own background, observations, goals, and recalled memories "
        "when deciding how to vote. Do not assume facts that were not provided."
    )
    prefab = minimal.Entity(
        params={
            "name": profile.name,
            "goal": profile.goal,
            "custom_instructions": instructions,
            "extra_components": {
                relevant_memories_key: relevant_memories,
            },
            # Put recalled memories after the current observation.
            "extra_components_index": {
                relevant_memories_key: 3,
            },
            "randomize_choices": False,
        }
    )
    agent = prefab.build(model=model, memory_bank=memory_bank)
    return BuiltVoter(profile=profile, agent=agent, memory_bank=memory_bank)


def run_vote(
    voter: BuiltVoter,
    *,
    election_observation: str,
    additional_observations: Sequence[str] = (),
    candidates: tuple[str, ...] = ("Alice", "Bob"),
    include_reason: bool = True,
) -> VoteDecision:
    """Let a voter observe one election situation, choose, and explain."""
    if len(candidates) < 2:
        raise ValueError("At least two candidates are required.")
    if len(set(candidates)) != len(candidates):
        raise ValueError("Candidate names must be unique.")

    voter.agent.observe(election_observation)
    for observation in additional_observations:
        voter.agent.observe(observation)
    choice = voter.agent.act(
        entity.ActionSpec(
            call_to_action=(
                "{name}, considering the election information and your "
                "relevant memories, which candidate do you vote for?"
            ),
            output_type=entity.OutputType.CHOICE,
            options=candidates,
            tag="vote",
        )
    )

    reason = ""
    if include_reason:
        reason = voter.agent.act(
            entity.ActionSpec(
                call_to_action=(
                    f"{{name}} voted for {choice}. Explain the main reason in "
                    "one or two sentences, speaking from the voter's "
                    "perspective."
                ),
                output_type=entity.OutputType.FREE,
                tag="vote_reason",
            )
        ).strip()
        name_prefix = f"{voter.profile.name} "
        if reason.startswith(name_prefix):
            reason = reason[len(name_prefix) :].strip()

    return VoteDecision(candidate=choice, reason=reason)
