from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import activity
from ..ai import get_provider
from ..ai.base import AnalystRequest
from ..ai.context import build_context
from ..analytics import load_workspace, scope_summary, snapshot_payload
from ..db import get_db
from ..deps import current_user, get_engagement, require_writer
from ..models import Engagement, Evidence, Interview, Snapshot, User
from ..schemas import AnalystIn, SnapshotIn, SuggestIn, snapshot_out
from .common import not_found

router = APIRouter(prefix="/api/engagements/{eid}", tags=["analysis"])


@router.get("/summary")
def summary(eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db),
            scope: int | None = Query(None)) -> dict:
    return scope_summary(load_workspace(db, eng), scope)


@router.post("/suggest-level")
def suggest(body: SuggestIn, eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db)) -> dict:
    labels = [s["label"] for s in (eng.settings or {}).get("scale", [])] or ["1", "2", "3", "4", "5"]
    s = get_provider().suggest_level(body.notes, labels)
    return {"level": s.level, "cues": s.cues}


def _mentioned_entity(ws, question: str) -> int | None:  # noqa: ANN001
    q = question.lower()
    best = None
    for e in ws.entities:
        name = e.name.lower()
        first = name.split(" ")[0].strip("&,.")
        if name in q or (len(first) > 4 and f"{first}" in q.split()):
            if best is None or len(e.name) > len(best.name):
                best = e
    return best.id if best else None


@router.post("/analyst")
def analyst(body: AnalystIn, eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db),
            _: User = Depends(current_user)) -> dict:
    ws = load_workspace(db, eng)
    scope = body.scope if body.scope in ws.by_id else _mentioned_entity(ws, body.question)
    ctx = build_context(db, ws, scope)
    provider = get_provider()
    answer = provider.analyst(AnalystRequest(question=body.question, scope_name=ctx["scope"]["name"], context=ctx,
                                             history=body.history[-8:]))
    return {"answer": answer, "engine": provider.name, "scope": scope, "scope_name": ctx["scope"]["name"]}


def _counts(db: Session, eid: int) -> tuple[int, int]:
    iv = db.scalar(select(func.count(Interview.id)).where(Interview.engagement_id == eid, Interview.status == "completed")) or 0
    ev = db.scalar(select(func.count(Evidence.id)).where(Evidence.engagement_id == eid)) or 0
    return iv, ev


@router.get("/report/live")
def live_report(eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db)) -> dict:
    ws = load_workspace(db, eng)
    data = snapshot_payload(ws, *_counts(db, eng.id))
    return {"data": data, "narrative": get_provider().executive_summary(data, eng.client), "engine": get_provider().name}


@router.get("/snapshots")
def list_snapshots(eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Snapshot).where(Snapshot.engagement_id == eng.id).order_by(Snapshot.version))
    return [snapshot_out(s, full=False) for s in rows]


@router.get("/snapshots/{sid}")
def get_snapshot(sid: int, eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db)) -> dict:
    s = db.get(Snapshot, sid)
    if not s or s.engagement_id != eng.id:
        raise not_found("Dashboard version")
    return snapshot_out(s)


@router.post("/snapshots", status_code=201)
def publish(body: SnapshotIn, eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db),
            user: User = Depends(require_writer)) -> dict:
    ws = load_workspace(db, eng)
    data = snapshot_payload(ws, *_counts(db, eng.id))
    version = (db.scalar(select(func.max(Snapshot.version)).where(Snapshot.engagement_id == eng.id)) or 0) + 1
    narrative = body.narrative.strip() or get_provider().executive_summary(data, eng.client)
    note = body.note.strip() or f"Version {version}"
    s = Snapshot(engagement_id=eng.id, version=version, note=note, narrative=narrative, data=data, created_by=user.id)
    db.add(s)
    ov = data.get("overall")
    activity.log(db, eng.id, user.id, "report", f"published dashboard v{version} (enterprise {ov:.1f})" if ov is not None
                 else f"published dashboard v{version}")
    db.commit()
    return snapshot_out(s)
