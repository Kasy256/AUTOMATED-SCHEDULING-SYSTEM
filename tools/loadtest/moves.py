import random
from typing import Any


# Any: the version is untyped JSON from the API.
def move_for(version: dict[str, Any], rng: random.Random) -> dict[str, Any] | None:
    """A validate-move body: one assignment moved to another's start, same resources."""
    assignments: list[dict[str, Any]] = version["assignments"]
    if len(assignments) < 2:
        return None
    mine, other = rng.sample(assignments, 2)
    if other["start_at"] == mine["start_at"]:
        return None
    return {
        "activity_id": mine["activity_id"],
        "start_at": other["start_at"],
        "resources": mine["resources"],
    }
