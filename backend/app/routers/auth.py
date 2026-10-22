from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import COOKIE_NAME, current_user
from ..models import User, UserSession
from ..schemas import ChangePasswordIn, LoginIn, SetupIn, user_out
from ..security import hash_password, new_token, password_problem, token_hash, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# simple in-process throttle: 5 failed attempts per email per 15 minutes
_FAILS: dict[str, deque] = defaultdict(deque)
_WINDOW, _MAX_FAILS = 15 * 60, 5


def _throttled(key: str) -> bool:
    q, now = _FAILS[key], time.monotonic()
    while q and now - q[0] > _WINDOW:
        q.popleft()
    return len(q) >= _MAX_FAILS


def _start_session(db: Session, user: User, response: Response) -> None:
    token = new_token()
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.session_hours)
    db.add(UserSession(user_id=user.id, token_hash=token_hash(token), expires_at=expires))
    db.execute(delete(UserSession).where(UserSession.expires_at < datetime.now(timezone.utc)))
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    response.set_cookie(
        COOKIE_NAME, token, max_age=settings.session_hours * 3600, httponly=True,
        samesite="strict", secure=settings.cookie_secure, path="/",
    )


@router.get("/status")
def setup_status(db: Session = Depends(get_db)) -> dict:
    return {"needs_setup": (db.scalar(select(func.count(User.id))) or 0) == 0}


@router.post("/setup")
def first_admin(body: SetupIn, response: Response, db: Session = Depends(get_db)) -> dict:
    if (db.scalar(select(func.count(User.id))) or 0) > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Setup is already complete. Sign in instead.")
    if problem := password_problem(body.password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)
    user = User(email=body.email.lower(), name=body.name, password_hash=hash_password(body.password), role="admin")
    db.add(user)
    db.flush()
    _start_session(db, user, response)
    return user_out(user)


@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)) -> dict:
    key = body.email.lower()
    if _throttled(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Wait 15 minutes and try again.")
    user = db.scalar(select(User).where(User.email == key))
    if not user or not verify_password(body.password, user.password_hash):
        _FAILS[key].append(time.monotonic())
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    if not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is deactivated. Ask an administrator.")
    _FAILS.pop(key, None)
    _start_session(db, user, response)
    return user_out(user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == token_hash(token)))
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/session")
def session(request: Request, db: Session = Depends(get_db)) -> dict:
    """Like /me, but answers 200 with user=null when signed out (avoids noisy 401s on page load)."""
    try:
        return {"user": user_out(current_user(request, db))}
    except HTTPException:
        return {"user": None}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return user_out(user)


@router.post("/change-password")
def change_password(body: ChangePasswordIn, request: Request, user: User = Depends(current_user),
                    db: Session = Depends(get_db)) -> dict:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your current password is incorrect.")
    if problem := password_problem(body.new_password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)
    user = db.merge(user)
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    # sign out other sessions
    current = token_hash(request.cookies.get(COOKIE_NAME, ""))
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.token_hash != current))
    db.commit()
    return {"ok": True}
