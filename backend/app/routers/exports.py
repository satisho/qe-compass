"""CSV export of scores, and full JSON export/import of an engagement.

The JSON format is portable between installations (laptop → client server),
and keys records by their exported ids so imports rebuild every relationship.
Uploaded files are not embedded; they stay in the source installation's
uploads folder.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import activity, audit
from ..analytics import STATUS_LABEL, load_workspace
from ..db import get_db
from ..deps import current_user, get_engagement, require_writer
from ..models import (
    Activity, Assessment, Engagement, Entity, Evidence, FocusArea, Interview, Pillar, Snapshot, User,
)
from ..templates import DEFAULT_SETTINGS

router = APIRouter(prefix="/api/engagements", tags=["exports"])
FORMAT = "qe-compass-engagement"
TYPE = {"lob": "Line of business", "program": "Program", "app": "Application"}


def _fname(eng: Engagement, ext: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in eng.client)[:40]
    return f"QE_Compass_{safe}_{date.today().isoformat()}.{ext}"


@router.get("/{eid}/export.csv")
def export_csv(request: Request, eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db),
               user: User = Depends(current_user)) -> Response:
    audit.record_now(db, "data_export", request, user=user, detail=f"CSV scores · #{eng.id} {eng.title}")
    ws = load_workspace(db, eng)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Entity", "Entity type", "Part of", "Pillar", "Focus area", "Score", "Rolled up", "Level",
                "Confidence", "Status", "Linked interviews", "Linked artifacts", "Notes"])
    for e, _ in ws.tree():
        parent = ws.path(e.parent_id) if e.parent_id in ws.by_id else ""
        for f in ws.fas:
            s = ws.score(e.id, f.id)
            a = ws.scores.get((e.id, f.id))
            iv, ev = ws.linked(e.id, f.id)
            w.writerow([e.name, TYPE.get(e.type, e.type), parent, ws.pillars[f.pillar_index].name, f.name,
                        "" if s is None else round(s, 2), "yes" if ws.inherited(e.id, f.id) else "",
                        ws.level_label(s), ws.confidence(e.id, f.id) or "", STATUS_LABEL[ws.status(s)], iv, ev,
                        " ".join((a.notes if a else "").split())])
    return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{_fname(eng, "csv")}"'})


def _iso(v):  # noqa: ANN001, ANN202
    return v.isoformat() if isinstance(v, (date, datetime)) else v


@router.get("/{eid}/export.json")
def export_json(request: Request, eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db),
                user: User = Depends(current_user)) -> Response:
    audit.record_now(db, "data_export", request, user=user, detail=f"JSON engagement · #{eng.id} {eng.title}")
    import json

    pillars = db.scalars(select(Pillar).where(Pillar.engagement_id == eng.id).options(selectinload(Pillar.focus_areas)))
    doc = {
        "format": FORMAT, "version": 1, "exported_at": datetime.utcnow().isoformat() + "Z",
        "engagement": {"client": eng.client, "title": eng.title, "start_date": eng.start_date.isoformat(),
                       "weeks": eng.weeks, "interviews_planned": eng.interviews_planned, "settings": eng.settings},
        "pillars": [{"id": p.id, "key": p.key, "name": p.name, "short": p.short, "target": p.target, "weight": p.weight,
                     "color": p.color, "position": p.position,
                     "focus_areas": [{"id": f.id, "key": f.key, "name": f.name, "description": f.description,
                                      "question": f.question, "recommendation": f.recommendation,
                                      "horizon": f.horizon, "position": f.position} for f in p.focus_areas]}
                    for p in pillars],
        "entities": [{"id": e.id, "parent_id": e.parent_id, "type": e.type, "name": e.name, "apps": e.apps, "art": e.art,
                      "owner": e.owner, "criticality": e.criticality, "position": e.position}
                     for e in db.scalars(select(Entity).where(Entity.engagement_id == eng.id))],
        "assessments": [{"entity_id": a.entity_id, "focus_area_id": a.focus_area_id, "score": a.score,
                         "confidence": a.confidence, "notes": a.notes, "updated_at": _iso(a.updated_at)}
                        for a in db.scalars(select(Assessment).where(Assessment.engagement_id == eng.id))],
        "interviews": [{"entity_id": i.entity_id, "date": i.date.isoformat(), "stakeholder": i.stakeholder, "type": i.type,
                        "status": i.status, "notes": i.notes, "findings": i.findings,
                        "focus_area_ids": [f.id for f in i.focus_areas], "created_at": _iso(i.created_at)}
                       for i in db.scalars(select(Interview).where(Interview.engagement_id == eng.id)
                                           .options(selectinload(Interview.focus_areas)))],
        "evidence": [{"entity_id": e.entity_id, "name": e.name, "kind": e.kind, "doc_type": e.doc_type,
                      "summary": e.summary, "signals": e.signals, "url": e.url, "size": e.size,
                      "classified_by": e.classified_by, "focus_area_ids": [f.id for f in e.focus_areas],
                      "created_at": _iso(e.created_at)}
                     for e in db.scalars(select(Evidence).where(Evidence.engagement_id == eng.id)
                                         .options(selectinload(Evidence.focus_areas)))],
        "snapshots": [{"version": s.version, "note": s.note, "narrative": s.narrative, "data": s.data,
                       "created_at": _iso(s.created_at)}
                      for s in db.scalars(select(Snapshot).where(Snapshot.engagement_id == eng.id))],
        "activity": [{"kind": a.kind, "text": a.text, "created_at": _iso(a.created_at)}
                     for a in db.scalars(select(Activity).where(Activity.engagement_id == eng.id))],
    }
    return Response(json.dumps(doc, indent=1, default=str), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{_fname(eng, "json")}"'})


def _dt(v):  # noqa: ANN001, ANN202
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def import_document(db: Session, doc: dict, user_id: int | None, title_suffix: str = "") -> Engagement:
    """Create a new engagement from an export document. Raises ValueError on malformed input."""
    if doc.get("format") != FORMAT:
        raise ValueError("This file is not a QE Compass engagement export.")
    e = doc["engagement"]
    eng = Engagement(client=e["client"], title=e["title"] + title_suffix, start_date=date.fromisoformat(e["start_date"]),
                     weeks=int(e.get("weeks", 8)), interviews_planned=int(e.get("interviews_planned", 30)),
                     settings={**DEFAULT_SETTINGS, **(e.get("settings") or {})}, created_by=user_id)
    db.add(eng)
    db.flush()
    fa_map: dict[int, FocusArea] = {}
    for p in doc.get("pillars", []):
        pil = Pillar(engagement_id=eng.id, key=p["key"], name=p["name"], short=p.get("short") or p["name"][:40],
                     target=float(p.get("target", 3)), weight=float(p.get("weight", 1)), color=int(p.get("color", 0)),
                     position=int(p.get("position", 0)))
        db.add(pil)
        db.flush()
        for f in p.get("focus_areas", []):
            fa = FocusArea(engagement_id=eng.id, pillar_id=pil.id, key=f["key"], name=f["name"],
                           description=f.get("description", ""), question=f.get("question", ""),
                           recommendation=f.get("recommendation", ""), horizon=f.get("horizon", "next"),
                           position=int(f.get("position", 0)))
            db.add(fa)
            db.flush()
            fa_map[int(f["id"])] = fa
    ent_map: dict[int, Entity] = {}
    for x in doc.get("entities", []):
        ent = Entity(engagement_id=eng.id, type=x.get("type", "lob"), name=x["name"], apps=int(x.get("apps", 1)),
                     art=x.get("art", ""), owner=x.get("owner", ""), criticality=x.get("criticality", "Medium"),
                     position=int(x.get("position", 0)))
        db.add(ent)
        db.flush()
        ent_map[int(x["id"])] = ent
    for x in doc.get("entities", []):
        if x.get("parent_id") is not None and int(x["parent_id"]) in ent_map:
            ent_map[int(x["id"])].parent_id = ent_map[int(x["parent_id"])].id

    def fas(ids):  # noqa: ANN001, ANN202
        return [fa_map[int(i)] for i in ids or [] if int(i) in fa_map]

    def ent(i):  # noqa: ANN001, ANN202
        return ent_map[int(i)].id if i is not None and int(i) in ent_map else None

    for a in doc.get("assessments", []):
        if ent(a["entity_id"]) and int(a["focus_area_id"]) in fa_map:
            db.add(Assessment(engagement_id=eng.id, entity_id=ent(a["entity_id"]), focus_area_id=fa_map[int(a["focus_area_id"])].id,
                              score=a.get("score"), confidence=a.get("confidence"), notes=a.get("notes", ""),
                              updated_at=_dt(a.get("updated_at")) or datetime.utcnow()))
    for i in doc.get("interviews", []):
        findings = []
        for f in i.get("findings") or []:
            if int(f.get("focus_area_id", -1)) in fa_map:
                findings.append({**f, "focus_area_id": fa_map[int(f["focus_area_id"])].id})
        iv = Interview(engagement_id=eng.id, entity_id=ent(i.get("entity_id")), date=date.fromisoformat(i["date"]),
                       stakeholder=i["stakeholder"], type=i.get("type", "Interview"), status=i.get("status", "scheduled"),
                       notes=i.get("notes", ""), findings=findings or None, created_by=user_id,
                       created_at=_dt(i.get("created_at")) or datetime.utcnow())
        iv.focus_areas = fas(i.get("focus_area_ids"))
        db.add(iv)
    for x in doc.get("evidence", []):
        ev = Evidence(engagement_id=eng.id, entity_id=ent(x.get("entity_id")), name=x["name"], kind=x.get("kind", "link"),
                      doc_type=x.get("doc_type", "Document"), summary=x.get("summary", ""), signals=x.get("signals") or [],
                      url=x.get("url", ""), size=int(x.get("size", 0)), classified_by=x.get("classified_by", ""),
                      created_by=user_id, created_at=_dt(x.get("created_at")) or datetime.utcnow())
        ev.focus_areas = fas(x.get("focus_area_ids"))
        db.add(ev)
    for s in doc.get("snapshots", []):
        db.add(Snapshot(engagement_id=eng.id, version=int(s["version"]), note=s.get("note", ""),
                        narrative=s.get("narrative", ""), data=s["data"], created_by=user_id,
                        created_at=_dt(s.get("created_at")) or datetime.utcnow()))
    for a in doc.get("activity", []):
        db.add(Activity(engagement_id=eng.id, kind=a.get("kind", "scope"), text=a["text"],
                        created_at=_dt(a.get("created_at")) or datetime.utcnow()))
    return eng


@router.post("/import", status_code=201)
async def import_json(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict:
    import json

    raw = await file.read()
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Import files must be under 50 MB.")
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
        eng = import_document(db, doc, user.id, " (imported)")
        activity.log(db, eng.id, user.id, "scope", f"imported this engagement from {file.filename}")
        db.commit()
    except (ValueError, KeyError, TypeError) as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            str(exc) if isinstance(exc, ValueError) else "The file is missing required fields.") from exc
    return {"id": eng.id, "title": eng.title}
