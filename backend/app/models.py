"""Database schema.

An engagement owns its own copy of the assessment framework (pillars and focus
areas), so a client's framework can be tailored without affecting other
engagements. Assessable entities (lines of business, programs, applications)
form a tree inside an engagement; scores are stored per entity and focus area.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Boolean,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


ROLES = ("admin", "assessor", "viewer")
ENTITY_TYPES = ("lob", "program", "app")
HORIZONS = ("now", "next", "later")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default="assessor")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # two-step verification (TOTP). The secret is set during setup and only used once mfa_enabled is true.
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mfa_last_step: Mapped[int | None] = mapped_column(Integer, nullable=True)  # blocks code replay


class UserSession(Base):
    __tablename__ = "user_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped[User] = relationship()


class SecurityEvent(Base):
    """Append-only security audit log: sign-ins, account and access changes, exports."""

    __tablename__ = "security_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    email: Mapped[str] = mapped_column(String(255), default="", index=True)
    ip: Mapped[str] = mapped_column(String(64), default="", index=True)
    detail: Mapped[str] = mapped_column(String(1000), default="")


class EngagementMember(Base):
    """Who may open an engagement. Administrators and the engagement's creator always can."""

    __tablename__ = "engagement_members"
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagements.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Engagement(Base):
    __tablename__ = "engagements"
    id: Mapped[int] = mapped_column(primary_key=True)
    client: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    start_date: Mapped[date] = mapped_column(Date)
    weeks: Mapped[int] = mapped_column(Integer, default=8)
    interviews_planned: Mapped[int] = mapped_column(Integer, default=30)
    # maturity scale, status thresholds, roll-up weighting
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    pillars: Mapped[list[Pillar]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan", order_by="Pillar.position"
    )


class Pillar(Base):
    __tablename__ = "pillars"
    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagements.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    short: Mapped[str] = mapped_column(String(40))
    target: Mapped[float] = mapped_column(Float, default=3.0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    color: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)

    engagement: Mapped[Engagement] = relationship(back_populates="pillars")
    focus_areas: Mapped[list[FocusArea]] = relationship(
        back_populates="pillar", cascade="all, delete-orphan", order_by="FocusArea.position"
    )


class FocusArea(Base):
    __tablename__ = "focus_areas"
    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagements.id", ondelete="CASCADE"), index=True)
    pillar_id: Mapped[int] = mapped_column(ForeignKey("pillars.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    question: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    horizon: Mapped[str] = mapped_column(String(10), default="next")
    position: Mapped[int] = mapped_column(Integer, default=0)

    pillar: Mapped[Pillar] = relationship(back_populates="focus_areas")


class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagements.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[str] = mapped_column(String(20), default="lob")
    name: Mapped[str] = mapped_column(String(200))
    apps: Mapped[int] = mapped_column(Integer, default=1)
    art: Mapped[str] = mapped_column(String(200), default="")
    owner: Mapped[str] = mapped_column(String(200), default="")
    criticality: Mapped[str] = mapped_column(String(20), default="Medium")
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (UniqueConstraint("entity_id", "focus_area_id", name="uq_assessment_entity_fa"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagements.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    focus_area_id: Mapped[int] = mapped_column(ForeignKey("focus_areas.id", ondelete="CASCADE"), index=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)  # manual override
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssessmentHistory(Base):
    """Append-only audit trail of every score change."""

    __tablename__ = "assessment_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagements.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    focus_area_id: Mapped[int] = mapped_column(ForeignKey("focus_areas.id", ondelete="CASCADE"), index=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(40), default="manual")
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


interview_focus_areas = Table(
    "interview_focus_areas",
    Base.metadata,
    Column("interview_id", ForeignKey("interviews.id", ondelete="CASCADE"), primary_key=True),
    Column("focus_area_id", ForeignKey("focus_areas.id", ondelete="CASCADE"), primary_key=True),
)

evidence_focus_areas = Table(
    "evidence_focus_areas",
    Base.metadata,
    Column("evidence_id", ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True),
    Column("focus_area_id", ForeignKey("focus_areas.id", ondelete="CASCADE"), primary_key=True),
)


class Interview(Base):
    __tablename__ = "interviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagements.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True)
    date: Mapped[date] = mapped_column(Date)
    stakeholder: Mapped[str] = mapped_column(String(300))
    type: Mapped[str] = mapped_column(String(40), default="Interview")
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    notes: Mapped[str] = mapped_column(Text, default="")
    # list of {focus_area_id, score, confidence, finding, followup, applied}
    findings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    focus_areas: Mapped[list[FocusArea]] = relationship(secondary=interview_focus_areas)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagements.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(400))
    kind: Mapped[str] = mapped_column(String(10), default="file")  # file | link
    doc_type: Mapped[str] = mapped_column(String(100), default="Document")
    summary: Mapped[str] = mapped_column(Text, default="")
    signals: Mapped[list] = mapped_column(JSON, default=list)
    url: Mapped[str] = mapped_column(String(1000), default="")
    stored_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    content_type: Mapped[str] = mapped_column(String(200), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    text_excerpt: Mapped[str] = mapped_column(Text, default="")
    classified_by: Mapped[str] = mapped_column(String(40), default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    focus_areas: Mapped[list[FocusArea]] = relationship(secondary=evidence_focus_areas)


class Snapshot(Base):
    """A published, immutable dashboard version."""

    __tablename__ = "snapshots"
    __table_args__ = (UniqueConstraint("engagement_id", "version", name="uq_snapshot_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagements.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(300), default="")
    narrative: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Activity(Base):
    __tablename__ = "activity"
    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagements.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30), default="scope")
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
