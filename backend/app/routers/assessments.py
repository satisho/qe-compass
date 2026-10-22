from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import activity
from ..db import get_db
from ..deps import get_engagement, require_writer
from ..models import Assessment, AssessmentHistory, Engagement, User, utcnow
from ..schemas import AssessmentIn, assessment_out
from .common import check_entity, focus_areas_for

router = APIRouter(prefix="/api/engagements/{eid}/assessments", tags=["assessments"])


def upsert_assessment(db: Session, eid: int, entity_id: int, fa_id: int, user_id: int | None, *,
                      score: int | None = None, set_score: bool = False, confidence: str | None = None,
                      set_confidence: bool = False, notes: str | None = None, source: str = "manual") -> Assessment:
    a = db.scalar(select(Assessment).where(Assessment.entity_id == entity_id, Assessment.focus_area_id == fa_id))
    if a is None:
        a = Assessment(engagement_id=eid, entity_id=entity_id, focus_area_id=fa_id, notes="")
        db.add(a)
    before = (a.score, a.confidence, a.notes)
    if set_score:
        a.score = score
    if set_confidence:
        a.confidence = confidence
    if notes is not None:
        a.notes = notes
    if (a.score, a.confidence, a.notes) != before:
        a.updated_by, a.updated_at = user_id, utcnow()
        db.add(AssessmentHistory(engagement_id=eid, entity_id=entity_id, focus_area_id=fa_id, score=a.score,
                                 confidence=a.confidence, notes=a.notes, source=source, changed_by=user_id))
    return a


@router.put("/{entity_id}/{fa_id}")
def save(entity_id: int, fa_id: int, body: AssessmentIn, eid: int, db: Session = Depends(get_db),
         user: User = Depends(require_writer), eng: Engagement = Depends(get_engagement)) -> dict:
    ent = check_entity(db, eid, entity_id)
    fa = focus_areas_for(db, eid, [fa_id])[0]
    prev = db.scalar(select(Assessment.score).where(Assessment.entity_id == entity_id, Assessment.focus_area_id == fa_id))
    a = upsert_assessment(db, eid, entity_id, fa_id, user.id, score=body.score, set_score=body.set_score,
                          confidence=body.confidence, set_confidence=body.set_confidence, notes=body.notes,
                          source=body.source)
    if body.set_score and body.score != prev:
        labels = [s["label"] for s in (eng.settings or {}).get("scale", [])] or ["1", "2", "3", "4", "5"]
        lvl = f"{body.score} · {labels[body.score - 1]}" if body.score else "not assessed"
        verb = "applied a suggested level to" if body.source == "suggestion" else "scored"
        activity.log(db, eid, user.id, "assessment", f"{verb} {fa.name} for {ent.name}: {lvl}")
    db.commit()
    return assessment_out(a)
