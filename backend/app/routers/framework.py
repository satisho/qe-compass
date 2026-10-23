from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import activity
from ..db import get_db
from ..deps import get_engagement, require_writer
from ..models import Engagement, FocusArea, Pillar, User
from ..schemas import FocusAreaIn, FocusAreaUpdate, FrameworkSettingsIn, PillarIn, PillarUpdate, pillar_out
from ..templates import DEFAULT_SETTINGS
from .common import not_found

router = APIRouter(prefix="/api/engagements/{eid}/framework", tags=["framework"])


@router.patch("/settings")
def update_settings(body: FrameworkSettingsIn, eng: Engagement = Depends(get_engagement),
                    db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict:
    eng = db.merge(eng)
    cur = {**DEFAULT_SETTINGS, **(eng.settings or {})}
    data = body.model_dump(exclude_none=True)
    if "thresholds" in data and data["thresholds"]["gap"] >= data["thresholds"]["strong"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The gap threshold must be below the strength threshold.")
    cur.update(data)
    eng.settings = cur
    what = ", ".join({"scale": "maturity scale", "thresholds": "status thresholds", "weighting": "roll-up weighting"}[k] for k in data)
    activity.log(db, eng.id, user.id, "framework", f"changed the {what or 'framework settings'}")
    db.commit()
    return cur


def _pillar(db: Session, eid: int, pid: int) -> Pillar:
    p = db.get(Pillar, pid)
    if not p or p.engagement_id != eid:
        raise not_found("Pillar")
    return p


def _fa(db: Session, eid: int, fid: int) -> FocusArea:
    f = db.get(FocusArea, fid)
    if not f or f.engagement_id != eid:
        raise not_found("Focus area")
    return f


@router.post("/pillars", status_code=201)
def add_pillar(body: PillarIn, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
               _: Engagement = Depends(get_engagement)) -> dict:
    used = set(db.scalars(select(Pillar.color).where(Pillar.engagement_id == eid)))
    color = next((c for c in range(7) if c not in used), 0)
    pos = (db.scalar(select(func.max(Pillar.position)).where(Pillar.engagement_id == eid)) or 0) + 1
    p = Pillar(engagement_id=eid, key="p" + secrets.token_hex(3), name=body.name, short=(body.short or body.name)[:40],
               target=body.target, weight=body.weight, color=color, position=pos)
    db.add(p)
    activity.log(db, eid, user.id, "framework", f"added pillar “{p.name}”")
    db.commit()
    db.refresh(p)
    return pillar_out(p)


@router.patch("/pillars/{pid}")
def update_pillar(pid: int, body: PillarUpdate, eid: int, db: Session = Depends(get_db),
                  user: User = Depends(require_writer), _: Engagement = Depends(get_engagement)) -> dict:
    p = _pillar(db, eid, pid)
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(p, k, v)
    label = {"target": f"target to {p.target}", "weight": f"weight to {p.weight}"}
    desc = ", ".join(label.get(k, k) for k in changes)
    activity.log(db, eid, user.id, "framework", f"updated pillar {p.short} ({desc})")
    db.commit()
    return pillar_out(p)


@router.delete("/pillars/{pid}")
def delete_pillar(pid: int, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
                  _: Engagement = Depends(get_engagement)) -> dict:
    p = _pillar(db, eid, pid)
    if (db.scalar(select(func.count(Pillar.id)).where(Pillar.engagement_id == eid)) or 0) <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Keep at least one pillar.")
    activity.log(db, eid, user.id, "framework", f"removed pillar “{p.name}” and its focus areas")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/pillars/{pid}/focus-areas", status_code=201)
def add_fa(pid: int, body: FocusAreaIn, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
           _: Engagement = Depends(get_engagement)) -> dict:
    p = _pillar(db, eid, pid)
    pos = (db.scalar(select(func.max(FocusArea.position)).where(FocusArea.pillar_id == pid)) or 0) + 1
    f = FocusArea(engagement_id=eid, pillar_id=p.id, key=f"{p.key}x{secrets.token_hex(2)}", position=pos, **body.model_dump())
    db.add(f)
    activity.log(db, eid, user.id, "framework", f"added focus area “{f.name}” to {p.short}")
    db.commit()
    db.refresh(p)
    return pillar_out(p)


@router.patch("/focus-areas/{fid}")
def update_fa(fid: int, body: FocusAreaUpdate, eid: int, db: Session = Depends(get_db),
              user: User = Depends(require_writer), _: Engagement = Depends(get_engagement)) -> dict:
    f = _fa(db, eid, fid)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(f, k, v)
    activity.log(db, eid, user.id, "framework", f"edited focus area “{f.name}”")
    db.commit()
    return pillar_out(f.pillar)


@router.delete("/focus-areas/{fid}")
def delete_fa(fid: int, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
              _: Engagement = Depends(get_engagement)) -> dict:
    f = _fa(db, eid, fid)
    activity.log(db, eid, user.id, "framework", f"removed focus area “{f.name}” and its scores")
    db.delete(f)
    db.commit()
    return {"ok": True}
