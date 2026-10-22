from __future__ import annotations

import logging
import mimetypes
import re
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import activity
from ..ai import get_provider
from ..ai.context import focus_area_refs
from ..analytics import load_workspace
from ..config import settings
from ..db import get_db
from ..deps import get_engagement, require_writer
from ..models import Engagement, Evidence, User
from ..schemas import EvidenceUpdate, LinkEvidenceIn, evidence_out
from ..textextract import extract_text
from .common import check_entity, focus_areas_for, not_found

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/engagements/{eid}/evidence", tags=["evidence"])
BLOCKED_EXT = {".exe", ".bat", ".cmd", ".com", ".msi", ".ps1", ".sh", ".dll", ".scr", ".js", ".vbs", ".jar"}


def _dir(eid: int) -> Path:
    d = settings.upload_dir / f"engagement-{eid}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_name(name: str) -> str:
    base = Path(name or "file").name
    return re.sub(r"[^A-Za-z0-9._ -]", "_", base)[:200] or "file"


def delete_stored_files(db: Session, eid: int) -> None:
    for ev in db.scalars(select(Evidence).where(Evidence.engagement_id == eid, Evidence.stored_name.is_not(None))):
        try:
            (_dir(eid) / ev.stored_name).unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Could not delete %s: %s", ev.stored_name, exc)


def _get(db: Session, eid: int, evid: int) -> Evidence:
    ev = db.get(Evidence, evid)
    if not ev or ev.engagement_id != eid:
        raise not_found("Evidence")
    return ev


@router.get("")
def list_evidence(eng: Engagement = Depends(get_engagement), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Evidence).where(Evidence.engagement_id == eng.id)
                      .options(selectinload(Evidence.focus_areas)).order_by(Evidence.created_at.desc()))
    return [evidence_out(e) for e in rows]


@router.post("/upload", status_code=201)
async def upload(eid: int, entity_id: int | None = Form(None), files: list[UploadFile] = File(...),
                 db: Session = Depends(get_db), user: User = Depends(require_writer),
                 eng: Engagement = Depends(get_engagement)) -> list[dict]:
    ent = check_entity(db, eid, entity_id)
    ws = load_workspace(db, eng)
    refs = focus_area_refs(ws)
    provider = get_provider()
    out = []
    limit = settings.max_upload_mb * 1024 * 1024
    for up in files:
        name = _safe_name(up.filename or "file")
        if Path(name).suffix.lower() in BLOCKED_EXT:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{name}: executable and script files are not accepted as evidence.")
        stored = f"{secrets.token_hex(8)}_{name}"
        dest = _dir(eid) / stored
        size = 0
        with dest.open("wb") as fh:
            while chunk := await up.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    fh.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                        f"{name} is larger than {settings.max_upload_mb} MB.")
                fh.write(chunk)
        text = extract_text(dest, name)
        cls = provider.classify_evidence(name, text, refs)
        ev = Evidence(engagement_id=eid, entity_id=ent.id if ent else None, name=name, kind="file",
                      doc_type=cls.doc_type, summary=cls.summary, signals=cls.signals, stored_name=stored,
                      content_type=up.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream",
                      size=size, text_excerpt=text[:20000], classified_by=provider.name, created_by=user.id)
        ev.focus_areas = focus_areas_for(db, eid, cls.focus_area_ids)
        db.add(ev)
        activity.log(db, eid, user.id, "evidence",
                     f"added “{name}” to {ent.name if ent else 'the evidence library'} ({len(cls.focus_area_ids)} focus areas)")
        db.flush()
        out.append(evidence_out(ev))
    db.commit()
    return out


@router.post("/link", status_code=201)
def add_link(body: LinkEvidenceIn, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
             _: Engagement = Depends(get_engagement)) -> dict:
    ent = check_entity(db, eid, body.entity_id)
    ev = Evidence(engagement_id=eid, entity_id=body.entity_id, name=body.name, kind="link", doc_type=body.doc_type,
                  summary=body.summary, url=body.url, classified_by="manual", created_by=user.id)
    ev.focus_areas = focus_areas_for(db, eid, body.focus_area_ids)
    db.add(ev)
    activity.log(db, eid, user.id, "evidence", f"registered “{ev.name}” for {ent.name if ent else 'the evidence library'}")
    db.commit()
    return evidence_out(ev)


@router.patch("/{evid}")
def update(evid: int, body: EvidenceUpdate, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
           _: Engagement = Depends(get_engagement)) -> dict:
    ev = _get(db, eid, evid)
    data = body.model_dump(exclude_unset=True)
    if "entity_id" in data:
        check_entity(db, eid, data["entity_id"])
    if "focus_area_ids" in data:
        ev.focus_areas = focus_areas_for(db, eid, data.pop("focus_area_ids") or [])
    for k, v in data.items():
        if v is not None or k == "entity_id":
            setattr(ev, k, v)
    activity.log(db, eid, user.id, "evidence", f"updated “{ev.name}” ({len(ev.focus_areas)} focus areas)")
    db.commit()
    return evidence_out(ev)


@router.delete("/{evid}")
def delete(evid: int, eid: int, db: Session = Depends(get_db), user: User = Depends(require_writer),
           _: Engagement = Depends(get_engagement)) -> dict:
    ev = _get(db, eid, evid)
    if ev.stored_name:
        (_dir(eid) / ev.stored_name).unlink(missing_ok=True)
    activity.log(db, eid, user.id, "evidence", f"removed “{ev.name}” from evidence")
    db.delete(ev)
    db.commit()
    return {"ok": True}


@router.get("/{evid}/file")
def download(evid: int, eid: int, db: Session = Depends(get_db), _: Engagement = Depends(get_engagement)) -> FileResponse:
    ev = _get(db, eid, evid)
    path = (_dir(eid) / (ev.stored_name or "")).resolve()
    if not ev.stored_name or not path.is_file() or _dir(eid).resolve() not in path.parents:
        raise not_found("File")
    return FileResponse(path, filename=ev.name, media_type=ev.content_type or "application/octet-stream")
