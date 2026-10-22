from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import activity
from ..ai import get_provider
from ..ai.context import focus_area_refs, scale_labels
from ..analytics import load_workspace
from ..db import get_db
from ..deps import get_engagement, require_writer
from ..models import Assessment, Engagement, Entity, Interview, User, utcnow
from ..schemas import ApplyFindingsIn, InterviewIn, InterviewUpdate, interview_out
from .assessments import upsert_assessment
from .common import check_entity, focus_areas_for, not_found

router = APIRouter(prefix="/api/engagements/{eid}/interviews", tags=["interviews"])


def _get(db: Session, eid: int, iid: int) -> Interview:
    iv = db.get(Interview, iid)
    if not iv or iv.engagement_id != eid:
        raise not_found("Interview")
    return iv


def _ename(db: Session, entity_id: int | None) -> str:
    e = db.get(Entity, entity_id) if entity_id else None
    return e.name if e else "no entity"


@router.get("")
def list_interviews(eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Interview).where(Interview.engagement_id == eng.id)
                      .options(selectinload(Interview.focus_areas)).order_by(Interview.date.desc(), Interview.id.desc()))
    return [interview_out(i) for i in rows]


@router.post("", status_code=201)
def create(body: InterviewIn, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
           _: Engagement = Depends(get_engagement)) -> dict:
    check_entity(db, eid, body.entity_id)
    data = body.model_dump(exclude={"focus_area_ids"})
    iv = Interview(engagement_id=eid, created_by=user.id, **data)
    iv.focus_areas = focus_areas_for(db, eid, body.focus_area_ids)
    db.add(iv)
    verb = "logged" if iv.status == "completed" else "scheduled"
    activity.log(db, eid, user.id, "interview", f"{verb} a {iv.type.lower()} with {iv.stakeholder} ({_ename(db, iv.entity_id)})")
    db.commit()
    return interview_out(iv)


@router.patch("/{iid}")
def update(iid: int, body: InterviewUpdate, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
           _: Engagement = Depends(get_engagement)) -> dict:
    iv = _get(db, eid, iid)
    data = body.model_dump(exclude_unset=True)
    if "entity_id" in data:
        check_entity(db, eid, data["entity_id"])
    if "focus_area_ids" in data:
        iv.focus_areas = focus_areas_for(db, eid, data.pop("focus_area_ids") or [])
    was = iv.status
    for k, v in data.items():
        if v is not None or k == "entity_id":
            setattr(iv, k, v)
    iv.updated_at = utcnow()
    msg = (f"completed the {iv.type.lower()} with {iv.stakeholder}" if was != "completed" and iv.status == "completed"
           else f"updated the {iv.stakeholder} {iv.type.lower()}")
    activity.log(db, eid, user.id, "interview", msg)
    db.commit()
    return interview_out(iv)


@router.delete("/{iid}")
def delete(iid: int, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
           _: Engagement = Depends(get_engagement)) -> dict:
    iv = _get(db, eid, iid)
    activity.log(db, eid, user.id, "interview", f"deleted the {iv.stakeholder} {iv.type.lower()} record")
    db.delete(iv)
    db.commit()
    return {"ok": True}


@router.post("/{iid}/extract")
def extract(iid: int, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
            eng: Engagement = Depends(get_engagement)) -> dict:
    iv = _get(db, eid, iid)
    if iv.status != "completed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mark the interview as completed before extracting findings.")
    if not (iv.notes or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add interview notes first.")
    ws = load_workspace(db, eng)
    provider = get_provider()
    findings = provider.extract_findings(iv.notes, iv.stakeholder, _ename(db, iv.entity_id), focus_area_refs(ws), scale_labels(ws))
    iv.findings = [asdict(f) for f in findings]
    existing = {f.id for f in iv.focus_areas}
    add = [f.focus_area_id for f in findings if f.focus_area_id not in existing]
    if add:
        iv.focus_areas = list(iv.focus_areas) + focus_areas_for(db, eid, add)
    iv.updated_at = utcnow()
    activity.log(db, eid, user.id, "interview", f"extracted {len(findings)} findings from the {iv.stakeholder} {iv.type.lower()}")
    db.commit()
    return interview_out(iv)


@router.post("/{iid}/apply")
def apply(iid: int, body: ApplyFindingsIn, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
          _: Engagement = Depends(get_engagement)) -> dict:
    iv = _get(db, eid, iid)
    if not iv.entity_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Set the entity this stakeholder belongs to before applying findings.")
    findings = [dict(f) for f in (iv.findings or [])]
    applied = 0
    for idx in body.indexes:
        if not 0 <= idx < len(findings) or findings[idx].get("applied"):
            continue
        f = findings[idx]
        fa = focus_areas_for(db, eid, [f["focus_area_id"]])[0]
        a = db.scalar(select(Assessment).where(Assessment.entity_id == iv.entity_id, Assessment.focus_area_id == fa.id))
        line = f"[{iv.stakeholder}, {iv.date.isoformat()}] {f['finding']}"
        notes = a.notes if a and a.notes else ""
        if f["finding"] not in notes:
            notes = (notes + "\n" + line).strip()
        upsert_assessment(db, eid, iv.entity_id, fa.id, user.id, score=f.get("score"), set_score=f.get("score") is not None,
                          notes=notes, source="interview")
        f["applied"] = True
        applied += 1
    iv.findings = findings
    if applied:
        activity.log(db, eid, user.id, "interview",
                     f"applied {applied} interview finding{'s' if applied > 1 else ''} to {_ename(db, iv.entity_id)}")
    db.commit()
    return interview_out(iv)
