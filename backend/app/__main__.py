"""Run QE Compass:  python -m app [--open] [--host H] [--port P]

Administrative commands:
  python -m app create-admin --email you@example.com --name "Your Name"
  python -m app reset-password --email you@example.com
  python -m app load-sample
"""
from __future__ import annotations

import argparse
import getpass
import sys
import threading
import time
import webbrowser


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    from .config import settings

    host, port = args.host or settings.host, args.port or settings.port
    url = f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}"
    if args.open:
        threading.Thread(target=lambda: (time.sleep(2.0), webbrowser.open(url)), daemon=True).start()
    print(f"\n  QE Compass is starting at {url}\n  Press Ctrl+C to stop.\n", flush=True)
    uvicorn.run("app.main:app", host=host, port=port, log_level="info", proxy_headers=True)


def _ask_password(confirm: bool = True) -> str:
    from .security import password_problem

    while True:
        pw = getpass.getpass("New password: ")
        if problem := password_problem(pw):
            print(problem)
            continue
        if confirm and getpass.getpass("Repeat password: ") != pw:
            print("Passwords don't match.")
            continue
        return pw


def _create_admin(args: argparse.Namespace) -> None:
    from sqlalchemy import select

    from .db import SessionLocal
    from .migrate import upgrade
    from .models import User
    from .security import hash_password

    upgrade()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == args.email.lower())):
            sys.exit("A user with that email already exists. Use reset-password instead.")
        db.add(User(email=args.email.lower(), name=args.name, role="admin", password_hash=hash_password(_ask_password())))
        db.commit()
    print(f"Administrator {args.email} created.")


def _reset(args: argparse.Namespace) -> None:
    from sqlalchemy import delete, select

    from .db import SessionLocal
    from .migrate import upgrade
    from .models import User, UserSession
    from .security import hash_password

    upgrade()
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == args.email.lower()))
        if not u:
            sys.exit("No user with that email.")
        u.password_hash, u.active = hash_password(_ask_password()), True
        db.execute(delete(UserSession).where(UserSession.user_id == u.id))
        db.commit()
    print(f"Password reset for {args.email}. The account is active.")


def _sample(_: argparse.Namespace) -> None:
    from .db import SessionLocal
    from .migrate import upgrade
    from .seed.sample import create_sample

    upgrade()
    with SessionLocal() as db:
        eng = create_sample(db, None)
    print(f"Loaded sample engagement #{eng.id}: {eng.title}")


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m app", description="QE Compass")
    p.add_argument("--open", action="store_true", help="open the browser once the server starts")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("create-admin")
    a.add_argument("--email", required=True)
    a.add_argument("--name", required=True)
    r = sub.add_parser("reset-password")
    r.add_argument("--email", required=True)
    sub.add_parser("load-sample")
    args = p.parse_args()
    {"create-admin": _create_admin, "reset-password": _reset, "load-sample": _sample}.get(args.cmd, _serve)(args)


if __name__ == "__main__":
    main()
