from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import current_user, require_admin
from ..models import SecurityEvent, User, UserSession
from ..schemas import ResetPasswordIn, UserCreate, UserUpdate, user_out
from ..security import hash_password, password_problem

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/directory")
def directory(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict]:
    """Names and roles only, so the UI can attribute changes and pick engagement members."""
    return [{"id": u.id, "name": u.name, "role": u.role, "active": u.active} for u in db.scalars(select(User).order_by(User.name))]


@router.get("")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[dict]:
    return [user_out(u) for u in db.scalars(select(User).order_by(User.name))]


@router.post("", status_code=201)
def create_user(body: UserCreate, request: Request, db: Session = Depends(get_db), me: User = Depends(require_admin)) -> dict:
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists.")
    if problem := password_problem(body.password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    u = User(email=email, name=body.name, role=body.role, password_hash=hash_password(body.password),
             must_change_password=True)
    db.add(u)
    db.flush()
    audit.record(db, "user_created", request, user=me, detail=f"{u.email} as {u.role}")
    db.commit()
    return user_out(u)


def _admins_left(db: Session, excluding: int) -> int:
    return db.scalar(select(func.count(User.id)).where(User.role == "admin", User.active.is_(True), User.id != excluding)) or 0


@router.patch("/{uid}")
def update_user(uid: int, body: UserUpdate, request: Request, db: Session = Depends(get_db), me: User = Depends(require_admin)) -> dict:
    u = db.get(User, uid)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    demoting = (body.role and body.role != "admin") or body.active is False
    if u.role == "admin" and demoting and _admins_left(db, u.id) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Keep at least one active administrator.")
    changes = []
    for k, v in body.model_dump(exclude_none=True).items():
        if getattr(u, k) != v:
            changes.append(f"{k}: {getattr(u, k)} -> {v}")
        setattr(u, k, v)
    if body.active is False:
        db.execute(delete(UserSession).where(UserSession.user_id == u.id))
    if changes:
        audit.record(db, "user_updated", request, user=me, detail=f"{u.email}: " + "; ".join(changes))
    db.commit()
    return user_out(u)


@router.post("/{uid}/reset-password")
def reset_password(uid: int, body: ResetPasswordIn, request: Request, db: Session = Depends(get_db),
                   me: User = Depends(require_admin)) -> dict:
    u = db.get(User, uid)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    if problem := password_problem(body.password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    u.password_hash = hash_password(body.password)
    u.must_change_password = True
    db.execute(delete(UserSession).where(UserSession.user_id == u.id))
    audit.record(db, "password_reset", request, user=me, detail=u.email)
    db.commit()
    return {"ok": True}


@router.post("/{uid}/reset-mfa")
def reset_mfa(uid: int, request: Request, db: Session = Depends(get_db), me: User = Depends(require_admin)) -> dict:
    """For a user who lost their phone: turns two-step off so they can set it up again."""
    u = db.get(User, uid)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    u.mfa_enabled, u.mfa_secret, u.mfa_last_step = False, None, None
    db.execute(delete(UserSession).where(UserSession.user_id == u.id))
    audit.record(db, "mfa_reset", request, user=me, detail=u.email)
    db.commit()
    return user_out(u)


security_router = APIRouter(prefix="/api/security-events", tags=["users"])


@security_router.get("")
def security_events(db: Session = Depends(get_db), _: User = Depends(require_admin),
                    limit: int = Query(200, ge=1, le=1000), kind: str | None = None) -> list[dict]:
    q = select(SecurityEvent).order_by(SecurityEvent.created_at.desc(), SecurityEvent.id.desc()).limit(limit)
    if kind:
        q = q.where(SecurityEvent.kind == kind)
    return [{"id": e.id, "created_at": e.created_at, "kind": e.kind, "label": audit.LABELS.get(e.kind, e.kind),
             "user_id": e.user_id, "email": e.email, "ip": e.ip, "detail": e.detail} for e in db.scalars(q)]
