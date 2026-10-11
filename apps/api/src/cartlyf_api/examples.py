"""Placeholder ids for request-body examples. The isolation harness swaps them for real ids,
so every id a body can carry must come from here."""

from collections.abc import Mapping
from types import MappingProxyType
from uuid import UUID

EXAMPLE_IDS: Mapping[str, UUID] = MappingProxyType(
    {
        name: UUID(f"00000000-0000-4000-8000-{n:012d}")
        for n, name in enumerate(
            (
                "resource_type_id",
                "resource_id",
                "schedule_id",
                "slot_template_id",
                "demand_id",
                "activity_id",
            ),
            start=1,
        )
    }
)


def example_id(name: str) -> str:
    return str(EXAMPLE_IDS[name])
