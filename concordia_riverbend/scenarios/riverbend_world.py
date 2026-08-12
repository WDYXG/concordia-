"""Riverbend represented with the domain-neutral simulation contracts."""

from __future__ import annotations

import re

from concordia_riverbend.core import ActionSpec
from concordia_riverbend.core import AgentSpec
from concordia_riverbend.core import LocationSpec
from concordia_riverbend.core import ScenarioSpec
from concordia_riverbend.core import WorldEvent
from concordia_riverbend.core import WorldState
from concordia_riverbend.scenarios.election_conditions import BASELINE
from concordia_riverbend.scenarios.election_conditions import ElectionCondition
from concordia_riverbend.scenarios.riverbend_election import RIVERBEND_VOTERS
from concordia_riverbend.scenarios.riverbend_election import (
    build_election_announcement,
)
from concordia_riverbend.scenarios.riverbend_election import (
    build_election_observation,
)


RIVERBEND_LOCATIONS: tuple[LocationSpec, ...] = (
    LocationSpec(
        location_id="residential_district",
        name="Residential District",
        description="Homes and a public school near the riverfront.",
    ),
    LocationSpec(
        location_id="factory_district",
        name="Factory District",
        description="The old mill and the proposed factory expansion site.",
    ),
    LocationSpec(
        location_id="downtown",
        name="Downtown",
        description="Small businesses, cafes, and public meeting spaces.",
    ),
    LocationSpec(
        location_id="community_clinic",
        name="Community Clinic",
        description="Riverbend's publicly supported health clinic.",
    ),
    LocationSpec(
        location_id="riverfront_park",
        name="Riverfront Park",
        description="A public park beside the river and library.",
    ),
    LocationSpec(
        location_id="town_hall",
        name="Town Hall",
        description="The civic center where public meetings and voting occur.",
    ),
)


RIVERBEND_ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        action_type="move",
        description="Move to another accessible Riverbend location.",
        parameter_names=("destination",),
        allowed_roles=("voter",),
    ),
    ActionSpec(
        action_type="speak",
        description="Send a public or private message to other residents.",
        parameter_names=("message", "channel", "recipients"),
        optional_parameter_names=("source_event_id",),
        allowed_roles=("voter",),
    ),
    ActionSpec(
        action_type="inspect",
        description="Inspect a location or an available source of information.",
        parameter_names=("target",),
        allowed_roles=("voter",),
    ),
    ActionSpec(
        action_type="vote",
        description=(
            "Cast one secret ballot and give a concise first-person reason "
            "for the choice."
        ),
        parameter_names=("candidate",),
        optional_parameter_names=("reason",),
        allowed_roles=("voter",),
    ),
)


_INITIAL_LOCATIONS = {
    "Maya Chen": "residential_district",
    "Luis Ortiz": "factory_district",
    "Evelyn Brooks": "downtown",
    "Noah Williams": "community_clinic",
    "Jordan Lee": "riverfront_park",
}


def _agent_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def build_riverbend_world(
    condition: ElectionCondition = BASELINE,
    candidate_order: tuple[str, str] = ("Alice", "Bob"),
    *,
    start_at_voting_location: bool = False,
    life_simulation: bool = False,
    election_day: int = 11,
) -> ScenarioSpec:
    """Build the Riverbend scenario without constructing or calling an LLM."""
    if set(candidate_order) != {"Alice", "Bob"}:
        raise ValueError(
            "candidate_order must contain Alice and Bob exactly once."
        )
    allowed_actions = tuple(
        action.action_type for action in RIVERBEND_ACTIONS
    )
    agents = tuple(
        AgentSpec(
            agent_id=_agent_id(profile.name),
            name=profile.name,
            role="voter",
            goal=profile.goal,
            initial_location=(
                "town_hall"
                if start_at_voting_location
                else _INITIAL_LOCATIONS[profile.name]
            ),
            initial_memories=profile.memories,
            allowed_actions=allowed_actions,
            attributes={"background": profile.background},
        )
        for profile in RIVERBEND_VOTERS
    )

    initial_events = [
        WorldEvent(
            event_id=(
                "election_announcement"
                if life_simulation
                else "election_briefing"
            ),
            round_index=0,
            event_type="public_announcement",
            content=(
                build_election_announcement(election_day)
                if life_simulation
                else build_election_observation(candidate_order)
            ),
            is_public=True,
            metadata={"source": "Riverbend Election Game Master"},
        )
    ]
    if condition.event and not life_simulation:
        initial_events.append(
            WorldEvent(
                event_id=f"condition_{condition.name}",
                round_index=0,
                event_type="information_treatment",
                content=condition.event,
                is_public=True,
                metadata={"condition": condition.name},
            )
        )

    return ScenarioSpec(
        scenario_id="riverbend_election",
        title="Riverbend Election",
        description=(
            "A small-town social simulation about jobs, public services, "
            "environmental risk, communication, and voting."
        ),
        agents=agents,
        locations=RIVERBEND_LOCATIONS,
        actions=RIVERBEND_ACTIONS,
        initial_events=tuple(initial_events),
        metadata={
            "condition": condition.name,
            "candidates": candidate_order,
            "voting_location": "town_hall",
            "starting_location_policy": (
                "voting_location"
                if start_at_voting_location
                else "distributed_world"
            ),
            "source_profiles": "riverbend_election.RIVERBEND_VOTERS",
            "protocol": (
                "daily_life_election"
                if life_simulation
                else "immediate_election"
            ),
            "election_day": election_day,
        },
    )


def build_initial_riverbend_state(
    condition: ElectionCondition = BASELINE,
    candidate_order: tuple[str, str] = ("Alice", "Bob"),
    *,
    start_at_voting_location: bool = False,
    life_simulation: bool = False,
    election_day: int = 11,
) -> WorldState:
    """Create grounded mutable state for a fresh Riverbend simulation."""
    return WorldState.from_scenario(
        build_riverbend_world(
            condition,
            candidate_order,
            start_at_voting_location=start_at_voting_location,
            life_simulation=life_simulation,
            election_day=election_day,
        )
    )
