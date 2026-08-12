"""Controlled information treatments for the Riverbend election."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ElectionCondition:
    """One level of the information-treatment independent variable."""

    name: str
    description: str
    event: str | None


BASELINE = ElectionCondition(
    name="baseline",
    description="No second announcement is broadcast after the base briefing.",
    event=None,
)

PLACEBO = ElectionCondition(
    name="placebo",
    description="No new evidence about either platform's expected effects.",
    event=(
        "The Riverbend Independent Review Board released its final bulletin. "
        "After reviewing the available documents, it found no new evidence "
        "that changes the already published assessment of either candidate's "
        "platform. The board made no additional forecast about jobs or river "
        "pollution."
    ),
)

EMPLOYMENT_EVIDENCE = ElectionCondition(
    name="employment_evidence",
    description="Independent evidence supports the factory's employment claim.",
    event=(
        "The Riverbend Independent Review Board released its final bulletin. "
        "After reviewing audited contracts and staffing plans, it estimated "
        "that the proposed factory expansion would probably create about 300 "
        "net local jobs. The board made no additional forecast about river "
        "pollution."
    ),
)

POLLUTION_EVIDENCE = ElectionCondition(
    name="pollution_evidence",
    description="Independent evidence identifies additional pollution risk.",
    event=(
        "The Riverbend Independent Review Board released its final bulletin. "
        "After reviewing water and soil assessments, it estimated that the "
        "proposed factory expansion would probably cause a substantial "
        "increase in river-pollution risk. The board made no additional "
        "forecast about employment."
    ),
)

ELECTION_CONDITIONS: tuple[ElectionCondition, ...] = (
    BASELINE,
    PLACEBO,
    EMPLOYMENT_EVIDENCE,
    POLLUTION_EVIDENCE,
)
