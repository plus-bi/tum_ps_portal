from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .db import Listing


_REFERENCE_LOCKS = {"ps": 1_879_001, "idp": 1_879_002}


def next_reference_code(session: Session, opportunity_type: str) -> str:
    """Allocate a stable, per-type public reference code in the current transaction."""
    prefix = "idp" if opportunity_type == "idp" else "ps"
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": _REFERENCE_LOCKS[prefix]})

    existing = session.scalars(select(Listing.reference_code).where(
        Listing.reference_code.like(f"{prefix}-%"),
    )).all()
    numbers = [int(code.rsplit("-", 1)[1]) for code in existing if code and code.rsplit("-", 1)[1].isdigit()]
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"
