from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Activity


def log(db: Session, engagement_id: int, user_id: int | None, kind: str, text: str) -> None:
    """Record a human-readable event. Callers commit."""
    db.add(Activity(engagement_id=engagement_id, user_id=user_id, kind=kind, text=text[:1000]))
