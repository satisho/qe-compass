from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .config import settings
from .db import get_db
from .models import Engagement, EngagementMember, User, UserSession
from .security import token_hash

COOKIE_NAME = "qec_session"
# while two-step verification is required but not yet set up, only these calls are allowed
_MFA_SETUP_PATHS = ("/api/auth/",)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def session_for(request: Request, db: Session) -> UserSession:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(token)))
    now = datetime.now(timezone.utc)
    if not sess or _aware(sess.expires_at) < now or not sess.user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has ended. Sign in again.")
    seen = _aware(sess.last_seen_at or sess.created_at)
    if settings.idle_minutes > 0 and now - seen > timedelta(minutes=settings.idle_minutes):
        audit.record(db, "session_idle", request, user=sess.user)
        db.delete(sess)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "You were signed out after a period of inactivity. Sign in again.")
    if now - seen > timedelta(seconds=60):  # avoid a write on every request
        sess.last_seen_at = now
        db.commit()
    return sess


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = session_for(request, db).user
    if settings.require_mfa and not user.mfa_enabled and not request.url.path.startswith(_MFA_SETUP_PATHS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Set up two-step verification to continue.")
    return user


def require_writer(user: User = Depends(current_user)) -> User:
    if user.role not in ("admin", "assessor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role is view-only.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only administrators can do this.")
    return user


def can_open(db: Session, user: User, eng: Engagement) -> bool:
    if user.role == "admin" or eng.created_by == user.id:
        return True
    return db.get(EngagementMember, (eng.id, user.id)) is not None


def engagement_access(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> None:
    """Router-level guard: any route with an {eid} path parameter requires access to that engagement."""
    raw = request.path_params.get("eid")
    if raw is None:
        return
    try:
        eng = db.get(Engagement, int(raw))
    except ValueError:
        eng = None
    # same answer for "doesn't exist" and "no access", so engagement ids can't be probed
    if not eng or not can_open(db, user, eng):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Engagement not found.")


def get_engagement(eid: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> Engagement:
    eng = db.get(Engagement, eid)
    if not eng:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Engagement not found.")
    return eng
