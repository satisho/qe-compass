from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .. import activity
from ..db import get_db
from ..deps import get_engagement, require_writer
from ..models import Engagement, Entity, User
from ..schemas import EntityIn, EntityUpdate, entity_out
from .common import check_entity, not_found

router = APIRouter(prefix="/api/engagements/{eid}/entities", tags=["entities"])
TYPE = {"lob": "line of business", "program": "program", "app": "application"}


def _descendants(db: Session, eid: int, root: int) -> set[int]:
    rows = db.execute(select(Entity.id, Entity.parent_id).where(Entity.engagement_id == eid)).all()
    children: dict[int | None, list[int]] = {}
    for i, p in rows:
        children.setdefault(p, []).append(i)
    out, stack = set(), [root]
    while stack:
        for c in children.get(stack.pop(), []):
            if c not in out:
                out.add(c)
                stack.append(c)
    return out


@router.post("", status_code=201)
def create_entity(body: EntityIn, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
                  _: Engagement = Depends(get_engagement)) -> dict:
    parent = check_entity(db, eid, body.parent_id)
    pos = (db.scalar(select(func.max(Entity.position)).where(Entity.engagement_id == eid)) or 0) + 1
    e = Entity(engagement_id=eid, position=pos, **body.model_dump())
    db.add(e)
    activity.log(db, eid, user.id, "scope",
                 f"added {TYPE[e.type]} {e.name} to scope" + (f" under {parent.name}" if parent else ""))
    db.commit()
    return entity_out(e)


@router.patch("/{entity_id}")
def update_entity(entity_id: int, body: EntityUpdate, eid: int, db: Session = Depends(get_db),
                  user: User = Depends(require_writer), _: Engagement = Depends(get_engagement)) -> dict:
    e = check_entity(db, eid, entity_id)
    data = body.model_dump(exclude_unset=True)
    clear = data.pop("clear_parent", False)
    if "parent_id" in data or clear:
        new_parent = None if clear else data.pop("parent_id", None)
        if new_parent is not None:
            check_entity(db, eid, new_parent)
            if new_parent == e.id or new_parent in _descendants(db, eid, e.id):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "An entity can’t be placed under itself or one of its children.")
        e.parent_id = new_parent
    data.pop("parent_id", None)
    for k, v in data.items():
        if v is not None:
            setattr(e, k, v)
    activity.log(db, eid, user.id, "scope", f"updated {TYPE[e.type]} {e.name}")
    db.commit()
    return entity_out(e)


@router.delete("/{entity_id}")
def delete_entity(entity_id: int, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
                  _: Engagement = Depends(get_engagement)) -> dict:
    e = check_entity(db, eid, entity_id)
    if e is None:
        raise not_found("Entity")
    # children move up to the removed entity's parent
    db.execute(update(Entity).where(Entity.parent_id == e.id).values(parent_id=e.parent_id))
    activity.log(db, eid, user.id, "scope", f"removed {TYPE[e.type]} {e.name} from scope")
    db.delete(e)
    db.commit()
    return {"ok": True}
