"""Request bodies and serializers."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from . import models as m

Role = Literal["admin", "assessor", "viewer"]
EntityType = Literal["lob", "program", "app"]
Horizon = Literal["now", "next", "later"]
Confidence = Literal["low", "med", "high"]


class Strict(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


# --- auth / users ---------------------------------------------------------
class LoginIn(Strict):
    email: str = Field(max_length=255)
    password: str = Field(max_length=500)
    code: str | None = Field(default=None, max_length=20)  # two-step verification code, when enabled


class MfaCodeIn(Strict):
    code: str = Field(max_length=20)


class MfaDisableIn(Strict):
    password: str = Field(max_length=500)


class MemberIn(Strict):
    user_id: int


class SetupIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(max_length=500)


class ChangePasswordIn(Strict):
    current_password: str = Field(max_length=500)
    new_password: str = Field(max_length=500)


class UserCreate(Strict):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=255)
    role: Role = "assessor"
    password: str = Field(max_length=500)


class UserUpdate(Strict):
    name: str | None = Field(default=None, max_length=200)
    role: Role | None = None
    active: bool | None = None


class ResetPasswordIn(Strict):
    password: str = Field(max_length=500)


def user_out(u: m.User) -> dict:
    return {
        "id": u.id, "email": u.email, "name": u.name, "role": u.role, "active": u.active,
        "must_change_password": u.must_change_password, "mfa_enabled": bool(u.mfa_enabled),
        "created_at": u.created_at, "last_login_at": u.last_login_at,
    }


# --- engagements ---------------------------------------------------------
class EngagementCreate(Strict):
    client: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    start_date: dt.date
    weeks: int = Field(default=8, ge=1, le=52)
    interviews_planned: int = Field(default=30, ge=1, le=1000)


class EngagementUpdate(Strict):
    client: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    start_date: dt.date | None = None
    weeks: int | None = Field(default=None, ge=1, le=52)
    interviews_planned: int | None = Field(default=None, ge=1, le=1000)
    archived: bool | None = None


def engagement_out(e: m.Engagement) -> dict:
    return {
        "id": e.id, "client": e.client, "title": e.title, "start_date": e.start_date, "weeks": e.weeks,
        "interviews_planned": e.interviews_planned, "archived": e.archived, "created_at": e.created_at,
    }


# --- framework -----------------------------------------------------------
class ScaleLevel(Strict):
    label: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=500)


class Thresholds(Strict):
    gap: float = Field(ge=1, le=5)
    strong: float = Field(ge=1, le=5)


class FrameworkSettingsIn(Strict):
    scale: list[ScaleLevel] | None = Field(default=None, min_length=5, max_length=5)
    thresholds: Thresholds | None = None
    weighting: Literal["apps", "equal"] | None = None


class PillarIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    short: str = Field(default="", max_length=40)
    target: float = Field(default=3.0, ge=1, le=5)
    weight: float = Field(default=1.0, ge=0, le=10)


class PillarUpdate(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    short: str | None = Field(default=None, max_length=40)
    target: float | None = Field(default=None, ge=1, le=5)
    weight: float | None = Field(default=None, ge=0, le=10)
    position: int | None = None


class FocusAreaIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    question: str = Field(default="", max_length=2000)
    recommendation: str = Field(default="", max_length=2000)
    horizon: Horizon = "next"


class FocusAreaUpdate(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    question: str | None = Field(default=None, max_length=2000)
    recommendation: str | None = Field(default=None, max_length=2000)
    horizon: Horizon | None = None
    position: int | None = None


def pillar_out(p: m.Pillar) -> dict:
    return {
        "id": p.id, "key": p.key, "name": p.name, "short": p.short, "target": p.target, "weight": p.weight,
        "color": p.color, "position": p.position,
        "focus_areas": [
            {"id": f.id, "key": f.key, "name": f.name, "description": f.description, "question": f.question,
             "recommendation": f.recommendation, "horizon": f.horizon, "position": f.position, "pillar_id": p.id}
            for f in sorted(p.focus_areas, key=lambda x: (x.position, x.id))
        ],
    }


# --- entities ------------------------------------------------------------
class EntityIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    type: EntityType = "lob"
    parent_id: int | None = None
    apps: int = Field(default=1, ge=1, le=100000)
    art: str = Field(default="", max_length=200)
    owner: str = Field(default="", max_length=200)
    criticality: Literal["High", "Medium", "Low"] = "Medium"


class EntityUpdate(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: EntityType | None = None
    parent_id: int | None = None
    apps: int | None = Field(default=None, ge=1, le=100000)
    art: str | None = Field(default=None, max_length=200)
    owner: str | None = Field(default=None, max_length=200)
    criticality: Literal["High", "Medium", "Low"] | None = None
    clear_parent: bool = False


def entity_out(e: m.Entity) -> dict:
    return {
        "id": e.id, "name": e.name, "type": e.type, "parent_id": e.parent_id, "apps": e.apps, "art": e.art,
        "owner": e.owner, "criticality": e.criticality, "position": e.position, "created_at": e.created_at,
    }


# --- assessments ---------------------------------------------------------
class AssessmentIn(Strict):
    score: int | None = Field(default=None, ge=1, le=5)
    set_score: bool = False  # distinguishes "clear score" from "leave score unchanged"
    confidence: Confidence | None = None
    set_confidence: bool = False
    notes: str | None = Field(default=None, max_length=20000)
    source: str = Field(default="manual", max_length=40)


def assessment_out(a: m.Assessment) -> dict:
    return {
        "entity_id": a.entity_id, "focus_area_id": a.focus_area_id, "score": a.score, "confidence": a.confidence,
        "notes": a.notes, "updated_by": a.updated_by, "updated_at": a.updated_at,
    }


# --- interviews ----------------------------------------------------------
class InterviewIn(Strict):
    entity_id: int | None = None
    date: dt.date
    stakeholder: str = Field(min_length=1, max_length=300)
    type: str = Field(default="Interview", max_length=40)
    status: Literal["scheduled", "completed"] = "scheduled"
    notes: str = Field(default="", max_length=50000)
    focus_area_ids: list[int] = Field(default_factory=list, max_length=200)


class InterviewUpdate(Strict):
    entity_id: int | None = None
    date: dt.date | None = None
    stakeholder: str | None = Field(default=None, min_length=1, max_length=300)
    type: str | None = Field(default=None, max_length=40)
    status: Literal["scheduled", "completed"] | None = None
    notes: str | None = Field(default=None, max_length=50000)
    focus_area_ids: list[int] | None = Field(default=None, max_length=200)


class ApplyFindingsIn(Strict):
    indexes: list[int] = Field(min_length=1, max_length=50)


def interview_out(i: m.Interview) -> dict:
    return {
        "id": i.id, "entity_id": i.entity_id, "date": i.date, "stakeholder": i.stakeholder, "type": i.type,
        "status": i.status, "notes": i.notes, "findings": i.findings,
        "applied": sum(1 for f in (i.findings or []) if f.get("applied")),
        "focus_area_ids": sorted(f.id for f in i.focus_areas),
        "created_by": i.created_by, "created_at": i.created_at, "updated_at": i.updated_at,
    }


# --- evidence ------------------------------------------------------------
class LinkEvidenceIn(Strict):
    entity_id: int | None = None
    name: str = Field(min_length=1, max_length=400)
    url: str = Field(default="", max_length=1000)
    doc_type: str = Field(default="Linked document", max_length=100)

    @field_validator("url")
    @classmethod
    def _web_link(cls, v: str) -> str:
        if v and not v.lower().startswith(("https://", "http://")):
            raise ValueError("links must start with https:// or http://")
        return v
    summary: str = Field(default="", max_length=5000)
    focus_area_ids: list[int] = Field(default_factory=list, max_length=200)

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        if v and not v.lower().startswith(("http://", "https://")):
            raise ValueError("Links must start with http:// or https://")
        return v


class EvidenceUpdate(Strict):
    entity_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=400)
    doc_type: str | None = Field(default=None, max_length=100)
    summary: str | None = Field(default=None, max_length=5000)
    focus_area_ids: list[int] | None = Field(default=None, max_length=200)


def evidence_out(e: m.Evidence) -> dict:
    return {
        "id": e.id, "entity_id": e.entity_id, "name": e.name, "kind": e.kind, "doc_type": e.doc_type,
        "summary": e.summary, "signals": e.signals or [], "url": e.url, "has_file": bool(e.stored_name),
        "content_type": e.content_type, "size": e.size, "classified_by": e.classified_by,
        "focus_area_ids": sorted(f.id for f in e.focus_areas), "created_by": e.created_by, "created_at": e.created_at,
    }


# --- analyst / snapshots -------------------------------------------------
class AnalystIn(Strict):
    question: str = Field(min_length=1, max_length=2000)
    scope: int | None = None
    history: list[dict] = Field(default_factory=list, max_length=20)


class SuggestIn(Strict):
    notes: str = Field(max_length=20000)


class SnapshotIn(Strict):
    note: str = Field(default="", max_length=300)
    narrative: str = Field(default="", max_length=10000)


def snapshot_out(s: m.Snapshot, full: bool = True) -> dict:
    out = {"id": s.id, "version": s.version, "note": s.note, "created_by": s.created_by, "created_at": s.created_at,
           "overall": (s.data or {}).get("overall")}
    if full:
        out["narrative"] = s.narrative
        out["data"] = s.data
    return out
