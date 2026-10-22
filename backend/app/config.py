"""Runtime configuration.

Values come from environment variables, optionally loaded from a `.env` file in
the backend folder or the project root. Defaults are tuned for running
standalone on a laptop: SQLite database and uploads under ./data, bound to
localhost only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


def _load_dotenv() -> None:
    for candidate in (PROJECT_DIR / ".env", BACKEND_DIR / ".env"):
        if not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_dotenv()


def _env(name: str, default: str) -> str:
    return os.environ.get(f"QEC_{name}", default)


def _path(value: str) -> Path:
    """Relative paths in settings are relative to the project folder, not the working directory."""
    p = Path(value).expanduser()
    return (p if p.is_absolute() else PROJECT_DIR / p).resolve()


def _bool(name: str, default: bool) -> bool:
    return _env(name, "true" if default else "false").lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: _path(_env("DATA_DIR", "data")))
    database_url: str = ""
    upload_dir: Path = field(default_factory=lambda: Path())
    frontend_dir: Path = field(default_factory=lambda: _path(_env("FRONTEND_DIR", "frontend/dist")))
    session_hours: int = int(_env("SESSION_HOURS", "12"))
    cookie_secure: bool = _bool("COOKIE_SECURE", False)
    max_upload_mb: int = int(_env("MAX_UPLOAD_MB", "25"))
    ai_provider: str = _env("AI_PROVIDER", "rules")
    host: str = _env("HOST", "127.0.0.1")
    port: int = int(_env("PORT", "8000"))

    def __post_init__(self) -> None:
        url = _env("DATABASE_URL", "") or f"sqlite:///{(self.data_dir / 'qecompass.db').as_posix()}"
        object.__setattr__(self, "database_url", url)
        object.__setattr__(self, "upload_dir", _path(_env("UPLOAD_DIR", str(self.data_dir / "uploads"))))

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


settings = Settings()
