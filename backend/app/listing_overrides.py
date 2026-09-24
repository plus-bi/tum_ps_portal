from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import ManualOverride


def manual_text_overrides(session: Session, listing_id: UUID) -> dict[str, str]:
    """Return the newest valid text override for each listing field."""
    rows = session.scalars(
        select(ManualOverride)
        .where(ManualOverride.listing_id == listing_id)
        .order_by(ManualOverride.created_at, ManualOverride.id)
    ).all()
    overrides: dict[str, str] = {}
    for row in rows:
        value = row.value.get("value") if isinstance(row.value, dict) else None
        if row.field in {"title", "summary"} and isinstance(value, str) and value.strip():
            overrides[row.field] = value.strip()
    return overrides
