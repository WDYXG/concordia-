"""Seeded daily events and phase rules for the Riverbend 10+1 protocol."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any

from concordia_riverbend.core import WorldEvent
from concordia_riverbend.core import WorldGameMaster
from concordia_riverbend.scenarios.election_conditions import ElectionCondition
from concordia_riverbend.scenarios.riverbend_election import (
    build_election_observation,
)


@dataclass(frozen=True)
class DailyEventTemplate:
    """One reusable background event that can be assigned to a life day."""

    event_type: str
    content: str
    location_id: str | None = None
    audience: tuple[str, ...] = ()
    is_public: bool = True


@dataclass(frozen=True)
class ScheduledDailyEvent:
    """One seeded background event assigned to an exact day."""

    day: int
    event_type: str
    content: str
    location_id: str | None = None
    audience: tuple[str, ...] = ()
    is_public: bool = True

    @property
    def event_id(self) -> str:
        return f"daily_event_day_{self.day:02d}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "content": self.content,
            "location_id": self.location_id,
            "audience": list(self.audience),
            "is_public": self.is_public,
        }

    def to_world_event(self) -> WorldEvent:
        return WorldEvent(
            event_id=self.event_id,
            round_index=self.day,
            event_type=self.event_type,
            content=self.content,
            location_id=self.location_id,
            audience=self.audience,
            is_public=self.is_public,
            metadata={"scheduled_day": self.day, "source": "Riverbend"},
        )


_DAILY_EVENT_POOL: tuple[DailyEventTemplate, ...] = (
    DailyEventTemplate(
        "weather_event",
        "Steady rain raises the river and slows travel across Riverbend.",
    ),
    DailyEventTemplate(
        "community_event",
        "The weekend market opens downtown and draws residents from across town.",
        location_id="downtown",
    ),
    DailyEventTemplate(
        "public_service_update",
        "The community clinic announces an evening vaccination session.",
        location_id="community_clinic",
    ),
    DailyEventTemplate(
        "environment_update",
        "Volunteers report litter and an unusual smell near the riverfront.",
        location_id="riverfront_park",
    ),
    DailyEventTemplate(
        "economic_update",
        "The old mill posts several short-term maintenance job openings.",
        location_id="factory_district",
    ),
    DailyEventTemplate(
        "school_event",
        "The public school holds a crowded meeting about next year's programs.",
        location_id="residential_district",
    ),
    DailyEventTemplate(
        "civic_event",
        "Town Hall publishes the election-day opening hours and voting rules.",
        location_id="town_hall",
    ),
    DailyEventTemplate(
        "business_update",
        "Several downtown shops begin a shared discount campaign.",
        location_id="downtown",
    ),
    DailyEventTemplate(
        "infrastructure_event",
        "A water-main repair temporarily redirects traffic near the clinic.",
        location_id="community_clinic",
    ),
    DailyEventTemplate(
        "environment_update",
        "A routine river sample is collected for laboratory testing.",
        location_id="riverfront_park",
    ),
    DailyEventTemplate(
        "employment_event",
        "Factory workers discuss uncertainty about next month's shift schedule.",
        location_id="factory_district",
    ),
    DailyEventTemplate(
        "community_event",
        "The library hosts a public discussion about Riverbend's future.",
        location_id="riverfront_park",
    ),
)


def build_daily_event_schedule(
    seed: int,
    *,
    life_days: int = 10,
) -> tuple[ScheduledDailyEvent, ...]:
    """Choose one reproducible background event for each life day."""
    if life_days < 1:
        raise ValueError("life_days must be at least 1.")
    rng = random.Random(seed)
    schedule: list[ScheduledDailyEvent] = []
    templates = list(_DAILY_EVENT_POOL)
    while len(schedule) < life_days:
        rng.shuffle(templates)
        for template in templates:
            if len(schedule) >= life_days:
                break
            schedule.append(
                ScheduledDailyEvent(
                    day=len(schedule) + 1,
                    event_type=template.event_type,
                    content=template.content,
                    location_id=template.location_id,
                    audience=template.audience,
                    is_public=template.is_public,
                )
            )
    return tuple(schedule)


class RiverbendDayScheduler:
    """Runs ten life days followed by one deterministic election day."""

    def __init__(
        self,
        *,
        schedule: tuple[ScheduledDailyEvent, ...],
        condition: ElectionCondition,
        candidate_order: tuple[str, str],
        election_day: int,
    ) -> None:
        if election_day != len(schedule) + 1:
            raise ValueError(
                "election_day must immediately follow the daily schedule."
            )
        self.schedule = schedule
        self.condition = condition
        self.candidate_order = candidate_order
        self.election_day = election_day

    def start_round(self, game_master: WorldGameMaster) -> None:
        state = game_master.state
        day = state.round_index
        state.variables["day"] = day

        if day < self.election_day:
            state.variables["phase"] = "daily_life"
            state.variables["allowed_actions"] = [
                "move",
                "speak",
                "inspect",
            ]
            event = self.schedule[day - 1]
            state.record_event(event.to_world_event())
            if day == self.election_day - 1 and self.condition.event:
                state.record_event(
                    WorldEvent(
                        event_id=f"condition_{self.condition.name}",
                        round_index=day,
                        event_type="information_treatment",
                        content=self.condition.event,
                        is_public=True,
                        metadata={
                            "condition": self.condition.name,
                            "scheduled_day": day,
                        },
                    )
                )
            return

        state.variables["phase"] = "election_day"
        state.variables["allowed_actions"] = ["vote"]
        for agent_id in game_master.scenario.agent_ids:
            state.agent_locations[agent_id] = "town_hall"
        state.record_event(
            WorldEvent(
                event_id="election_briefing",
                round_index=day,
                event_type="election_opening",
                content=build_election_observation(self.candidate_order),
                location_id="town_hall",
                is_public=True,
                metadata={
                    "candidate_order": self.candidate_order,
                    "scheduled_day": day,
                },
            )
        )
