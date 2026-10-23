"""Security audit log.

Every security-relevant event (sign-in success and failure, lockouts, password and
two-step changes, user and access changes, data exports) is written to the
append-only `security_events` table and to the `qecompass.security` log, so it can
be reviewed in the app (Users -> Security log) and collected by a SIEM.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import SecurityEvent, User

log = logging.getLogger("qecompass.security")

LABELS = {
    "login_success": "Signed in",
    "login_failed": "Sign-in failed",
    "login_blocked": "Sign-in blocked (too many attempts)",
    "mfa_failed": "Two-step code rejected",
    "logout": "Signed out",
    "session_idle": "Session ended after inactivity",
    "setup_admin": "First administrator created",
    "password_changed": "Password changed",
    "password_reset": "Password reset by administrator",
    "mfa_enabled": "Two-step verification turned on",
    "mfa_disabled": "Two-step verification turned off",
    "mfa_reset": "Two-step verification reset by administrator",
    "user_created": "User created",
    "user_updated": "User changed",
    "member_added": "Engagement access granted",
    "member_removed": "Engagement access removed",
    "engagement_deleted": "Engagement deleted",
    "data_export": "Data exported",
}


def client_ip(request: Request | None) -> str:
    return (request.client.host if request and request.client else "") or ""


def record(db: Session, kind: str, request: Request | None = None, *, user: User | None = None,
           email: str = "", detail: str = "") -> None:
    """Add an event to the session. Callers commit (or call `record_now`)."""
    ev = SecurityEvent(kind=kind, user_id=user.id if user else None, email=(email or (user.email if user else ""))[:255],
                       ip=client_ip(request)[:64], detail=detail[:1000])
    db.add(ev)
    log.info("%s email=%s ip=%s %s", kind, ev.email or "-", ev.ip or "-", detail)


def record_now(db: Session, kind: str, request: Request | None = None, **kw) -> None:
    record(db, kind, request, **kw)
    db.commit()


def recent_failures(db: Session, *, email: str | None = None, ip: str | None = None, minutes: int = 15) -> int:
    """Failed sign-ins in the window, counting only those after the account's last successful sign-in."""
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    q = select(func.count(SecurityEvent.id)).where(
        SecurityEvent.kind.in_(("login_failed", "mfa_failed")), SecurityEvent.created_at >= since)
    if email is not None:
        last_ok = db.scalar(select(func.max(SecurityEvent.created_at)).where(
            SecurityEvent.kind == "login_success", SecurityEvent.email == email))
        if last_ok is not None:
            last_ok = last_ok if last_ok.tzinfo else last_ok.replace(tzinfo=timezone.utc)
            since = max(since, last_ok)
        q = q.where(SecurityEvent.email == email, SecurityEvent.created_at >= since)
    if ip is not None:
        q = q.where(SecurityEvent.ip == ip)
    return db.scalar(q) or 0
