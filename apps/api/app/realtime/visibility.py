"""Single source of truth for who may see which simulation event.

Trainees only ever receive events marked ALL or PARTICIPANTS-events that name them.
INSTRUCTOR events (message creation, drops, delays, truth payloads) never reach trainees.
"""

from typing import Any

from app.models.enums import EventVisibility


def is_visible(
    visibility: str, targets: list[str], *, is_instructor: bool, participant_id: str | None
) -> bool:
    if is_instructor:
        return True
    if visibility == EventVisibility.ALL:
        return True
    if visibility == EventVisibility.PARTICIPANTS:
        return participant_id is not None and participant_id in targets
    return False


def wire_event_visible(
    event: dict[str, Any], *, is_instructor: bool, participant_id: str | None
) -> bool:
    return is_visible(
        str(event.get("visibility", EventVisibility.INSTRUCTOR)),
        list(event.get("targets") or []),
        is_instructor=is_instructor,
        participant_id=participant_id,
    )


def strip_for_trainee(event: dict[str, Any]) -> dict[str, Any]:
    """Trainees never need the targets list (it would reveal who else got what)."""
    return {k: v for k, v in event.items() if k not in ("targets", "actor_type")}
