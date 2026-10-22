from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Engagement, User, UserSession
from .security import token_hash

COOKIE_NAME = "qec_session"


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(token)))
    now = datetime.now(timezone.utc)
    if not sess or _aware(sess.expires_at) < now or not sess.user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has ended. Sign in again.")
    return sess.user


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def require_writer(user: User = Depends(current_user)) -> User:
    if user.role not in ("admin", "assessor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role is view-only.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only administrators can do this.")
    return user


def get_engagement(eid: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> Engagement:
    eng = db.get(Engagement, eid)
    if not eng:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Engagement not found.")
    return eng
