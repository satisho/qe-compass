from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Entity, FocusArea


def check_entity(db: Session, eid: int, entity_id: int | None) -> Entity | None:
    if entity_id is None:
        return None
    ent = db.get(Entity, entity_id)
    if not ent or ent.engagement_id != eid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That entity is not part of this engagement.")
    return ent


def focus_areas_for(db: Session, eid: int, ids: list[int]) -> list[FocusArea]:
    if not ids:
        return []
    fas = list(db.scalars(select(FocusArea).where(FocusArea.engagement_id == eid, FocusArea.id.in_(set(ids)))))
    if len(fas) != len(set(ids)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "One or more focus areas are not part of this engagement.")
    return fas


def not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found.")
