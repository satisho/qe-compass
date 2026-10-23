"""Apply database migrations on startup (Alembic, run programmatically)."""
from __future__ import annotations

from alembic import command
from alembic.config import Config

from .config import BACKEND_DIR, settings


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    return cfg


def _check_not_from_v11() -> None:
    """A database last opened by the withdrawn v1.1 preview can't be opened by 1.0.x; say how to fix it."""
    from sqlalchemy import create_engine, inspect, text

    eng = create_engine(settings.database_url)
    try:
        with eng.connect() as c:
            if "alembic_version" in inspect(c).get_table_names():
                if c.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0002":
                    raise SystemExit(
                        "\n  This database was opened by the QE Compass v1.1 preview, which has been withdrawn.\n"
                        "  See README.md > Troubleshooting > 'Can't locate revision 0002' to restore it for this version.\n")
    finally:
        eng.dispose()


def upgrade() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    _check_not_from_v11()
    command.upgrade(alembic_config(), "head")
