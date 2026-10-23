from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import activity, audit
from ..analytics import analytics_payload, load_workspace
from ..db import get_db
from ..deps import can_open, current_user, get_engagement, require_admin, require_writer
from ..models import Activity, Engagement, EngagementMember, Entity, Evidence, Interview, Pillar, Snapshot, User
from ..schemas import (
    EngagementCreate, EngagementUpdate, MemberIn, assessment_out, engagement_out, entity_out, pillar_out,
)
from ..templates import DEFAULT_SETTINGS, apply_template

router = APIRouter(prefix="/api/engagements", tags=["engagements"])


@router.get("")
def list_engagements(db: Session = Depends(get_db), user: User = Depends(current_user)) -> list[dict]:
    out = []
    for e in db.scalars(select(Engagement).order_by(Engagement.archived, Engagement.created_at.desc())):
        if not can_open(db, user, e):
            continue
        d = engagement_out(e)
        d["entities"] = db.scalar(select(func.count(Entity.id)).where(Entity.engagement_id == e.id)) or 0
        d["interviews"] = db.scalar(select(func.count(Interview.id)).where(
            Interview.engagement_id == e.id, Interview.status == "completed")) or 0
        d["evidence"] = db.scalar(select(func.count(Evidence.id)).where(Evidence.engagement_id == e.id)) or 0
        d["snapshots"] = db.scalar(select(func.count(Snapshot.id)).where(Snapshot.engagement_id == e.id)) or 0
        out.append(d)
    return out


@router.post("", status_code=201)
def create_engagement(body: EngagementCreate, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict:
    eng = Engagement(**body.model_dump(), settings=dict(DEFAULT_SETTINGS), created_by=user.id)
    db.add(eng)
    db.flush()
    apply_template(eng, db)
    activity.log(db, eng.id, user.id, "scope", f"created the engagement {eng.title}")
    db.commit()
    return engagement_out(eng)


@router.get("/{eid}")
def get_one(eng: Engagement = Depends(get_engagement)) -> dict:
    return engagement_out(eng)


@router.patch("/{eid}")
def update_engagement(body: EngagementUpdate, eng: Engagement = Depends(get_engagement),
                      db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict:
    eng = db.merge(eng)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(eng, k, v)
    activity.log(db, eng.id, user.id, "scope", "updated the engagement details")
    db.commit()
    return engagement_out(eng)


@router.delete("/{eid}")
def delete_engagement(request: Request, eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db),
                      me: User = Depends(require_admin)) -> dict:
    from ..routers.evidence import delete_stored_files

    audit.record(db, "engagement_deleted", request, user=me, detail=f"#{eng.id} {eng.client} · {eng.title}")
    delete_stored_files(db, eng.id)
    db.delete(db.merge(eng))
    db.commit()
    return {"ok": True}


@router.get("/{eid}/workspace")
def workspace(eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db)) -> dict:
    """Framework, scope, scores and computed analytics in one round trip."""
    ws = load_workspace(db, eng)
    pillars = db.scalars(select(Pillar).where(Pillar.engagement_id == eng.id)
                         .options(selectinload(Pillar.focus_areas)).order_by(Pillar.position, Pillar.id))
    return {
        "engagement": engagement_out(eng),
        "settings": ws.settings,
        "pillars": [pillar_out(p) for p in pillars],
        "entities": [entity_out(e) for e, _ in ws.tree()],
        "assessments": [assessment_out(a) for a in ws.scores.values()],
        "analytics": analytics_payload(ws),
    }


@router.get("/{eid}/activity")
def activity_feed(eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db),
                  limit: int = Query(30, ge=1, le=200)) -> list[dict]:
    rows = db.scalars(select(Activity).where(Activity.engagement_id == eng.id)
                      .order_by(Activity.created_at.desc(), Activity.id.desc()).limit(limit))
    return [{"id": a.id, "kind": a.kind, "text": a.text, "user_id": a.user_id, "created_at": a.created_at} for a in rows]


@router.get("/{eid}/assessments/{entity_id}/{fa_id}/history")
def history(entity_id: int, fa_id: int, eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db)) -> list[dict]:
    from ..models import AssessmentHistory

    rows = db.scalars(select(AssessmentHistory).where(
        AssessmentHistory.engagement_id == eng.id, AssessmentHistory.entity_id == entity_id,
        AssessmentHistory.focus_area_id == fa_id).order_by(AssessmentHistory.changed_at.desc()).limit(50))
    return [{"score": h.score, "confidence": h.confidence, "notes": h.notes, "source": h.source,
             "changed_by": h.changed_by, "changed_at": h.changed_at} for h in rows]


@router.post("/sample", status_code=201)
def load_sample(db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict:
    from ..seed.sample import create_sample

    eng = create_sample(db, user.id)
    return engagement_out(eng)


# ---- who can open this engagement ---------------------------------------------
@router.get("/{eid}/members")
def list_members(eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db)) -> dict:
    ids = [m.user_id for m in db.scalars(select(EngagementMember).where(EngagementMember.engagement_id == eng.id))]
    return {"created_by": eng.created_by, "members": ids}


@router.post("/{eid}/members", status_code=201)
def add_member(body: MemberIn, request: Request, eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db),
               me: User = Depends(require_writer)) -> dict:
    u = db.get(User, body.user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    if not db.get(EngagementMember, (eng.id, u.id)):
        db.add(EngagementMember(engagement_id=eng.id, user_id=u.id))
        audit.record(db, "member_added", request, user=me, detail=f"{u.email} -> #{eng.id} {eng.title}")
        activity.log(db, eng.id, me.id, "scope", f"gave {u.name} access to this engagement")
        db.commit()
    return list_members(eng, db)


@router.delete("/{eid}/members/{uid}")
def remove_member(uid: int, request: Request, eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db),
                  me: User = Depends(require_writer)) -> dict:
    m = db.get(EngagementMember, (eng.id, uid))
    if m:
        u = db.get(User, uid)
        db.delete(m)
        audit.record(db, "member_removed", request, user=me, detail=f"{u.email if u else uid} -> #{eng.id} {eng.title}")
        activity.log(db, eng.id, me.id, "scope", f"removed {u.name if u else 'a user'}'s access to this engagement")
        db.commit()
    return list_members(eng, db)
