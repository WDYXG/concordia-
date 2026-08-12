"""Five balanced voter profiles and one shared Riverbend election briefing."""

from concordia_riverbend.agents.voter import VoterProfile


_CANDIDATE_BRIEFS = {
    "Alice": (
        "Alice proposes stronger river-pollution enforcement, restored "
        "funding for public parks, and stable funding for schools and the "
        "community clinic. She would pay for part of the plan with modest "
        "fees on large industrial projects."
    ),
    "Bob": (
        "Bob proposes approving a factory expansion expected to create 300 "
        "jobs, reducing local business taxes, and shortening the permit "
        "process. He argues that economic growth will increase future "
        "funding for public services."
    ),
}


def build_election_observation(
    candidate_order: tuple[str, str],
) -> str:
    """Present candidate briefs in the assigned experimental order."""
    if set(candidate_order) != set(_CANDIDATE_BRIEFS):
        raise ValueError(
            "candidate_order must contain Alice and Bob exactly once."
        )
    first, second = candidate_order
    return "\n\n".join(
        (
            (
                "It is election day in Riverbend. Both candidates have "
                "completed their final campaign events."
            ),
            _CANDIDATE_BRIEFS[first],
            _CANDIDATE_BRIEFS[second],
            (
                "No independent forecast can guarantee either candidate's "
                "promised outcomes. Each voter must now cast one vote for "
                f"{first} or {second}."
            ),
        )
    )


def build_election_announcement(election_day: int = 11) -> str:
    """Announce a future election without presenting it as ready to vote."""
    if election_day < 2:
        raise ValueError("election_day must be at least 2.")
    return (
        f"Riverbend will hold its town election on day {election_day} at "
        "Town Hall. Residents may continue their normal activities until "
        "then. The final candidate briefing will be published when the "
        "polls open."
    )


ELECTION_OBSERVATION = build_election_observation(("Alice", "Bob"))


RIVERBEND_VOTERS: tuple[VoterProfile, ...] = (
    VoterProfile(
        name="Maya Chen",
        background=(
            "Maya is a 38-year-old public-school teacher who lives with her "
            "family near Riverbend's riverfront park."
        ),
        goal=(
            "Vote for the candidate Maya believes will best protect her "
            "family's health and Riverbend's long-term quality of life."
        ),
        memories=(
            "Maya's child became ill after pollution reached the river.",
            "Maya's school lost an after-school program during a budget cut.",
            "Alice promised river cleanup, parks, and stable school funding.",
            "Maya's spouse worries that Riverbend does not have enough jobs.",
        ),
    ),
    VoterProfile(
        name="Luis Ortiz",
        background=(
            "Luis is a 45-year-old machine operator whose hours were recently "
            "reduced. He supports two children and lives near the old mill."
        ),
        goal=(
            "Vote for the candidate Luis believes offers his household the "
            "best combination of economic security and a livable town."
        ),
        memories=(
            "Reduced shifts forced Luis to use part of his emergency savings.",
            "Bob said the factory expansion would prioritize local workers.",
            "Luis remembers earlier job promises that never fully materialized.",
            "Luis fishes in the river and dislikes the smell near the old mill.",
        ),
    ),
    VoterProfile(
        name="Evelyn Brooks",
        background=(
            "Evelyn is a 52-year-old owner of a small cafe near downtown. "
            "Her margins are narrow and she employs six local residents."
        ),
        goal=(
            "Vote for the candidate Evelyn believes will keep her business "
            "viable while maintaining a town that attracts customers."
        ),
        memories=(
            "A recent tax increase made it harder for Evelyn to replace equipment.",
            "Bob promised lower business taxes and a faster permit process.",
            "Weekend park events bring many customers to Evelyn's cafe.",
            "Construction during an earlier expansion reduced downtown traffic.",
        ),
    ),
    VoterProfile(
        name="Noah Williams",
        background=(
            "Noah is a 34-year-old nurse at Riverbend's community clinic. "
            "He treats families from both the industrial and river districts."
        ),
        goal=(
            "Vote for the candidate Noah believes will produce the greatest "
            "overall improvement in residents' health and security."
        ),
        memories=(
            "Noah treated several children with symptoms after a river spill.",
            "The clinic postponed replacing equipment after a funding freeze.",
            "Alice promised pollution enforcement and stable clinic funding.",
            "Noah's brother has struggled to find a steady local job.",
        ),
    ),
    VoterProfile(
        name="Jordan Lee",
        background=(
            "Jordan is a 25-year-old renter who recently completed technical "
            "training and is deciding whether to remain in Riverbend."
        ),
        goal=(
            "Vote for the candidate Jordan believes offers the most credible "
            "path to an affordable, healthy, and economically secure future."
        ),
        memories=(
            "Jordan has submitted many job applications with few responses.",
            "A rent increase consumed most of Jordan's recent pay raise.",
            "Jordan regularly uses the riverfront park and public library.",
            "Jordan distrusts campaign promises that lack independent evidence.",
        ),
    ),
)
