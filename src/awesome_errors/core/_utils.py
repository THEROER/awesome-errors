"""Shared internal helpers for the core package."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC ``datetime``."""
    return datetime.now(timezone.utc)


def to_iso_z(value: datetime) -> str:
    """Render a ``datetime`` as an ISO-8601 string with a ``Z`` UTC suffix.

    Naive datetimes are assumed to be UTC. Aware datetimes are converted to
    UTC. The result always ends in ``Z`` and never contains a ``+00:00``
    offset, giving a single canonical timestamp format across the library.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")
