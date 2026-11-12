"""QE Compass application entry point."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .deps import engagement_access
from .migrate import upgrade
from .routers import analysis, assessments, auth, engagements, entities, evidence, exports, framework, interviews, users

__version__ = "2.0.1"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("qecompass")



@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    upgrade()
    log.info("QE Compass %s ready · database: %s · AI provider: %s", __version__,
             "SQLite" if settings.is_sqlite else "external", settings.ai_provider)
    yield


# API documentation is off unless QEC_API_DOCS=true. OpenTelemetry auto-export is pinned off:
# the platform makes no outbound connections.
_docs = settings.api_docs
app = FastAPI(title="QE Compass", version=__version__, docs_url="/api/docs" if _docs else None,
              openapi_url="/api/openapi.json" if _docs else None, redoc_url=None, lifespan=lifespan,
              telemetry={"auto_configure": False})


@app.middleware("http")
async def security_headers(request: Request, call_next):  # noqa: ANN001, ANN201
    # CSRF defence in depth: cookies are SameSite=Strict, and state-changing API
    # calls must also carry a custom header that cross-site forms cannot set.
    if request.url.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.headers.get("x-requested-with") != "qe-compass":
            return JSONResponse({"detail": "Missing request header."}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
        "font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
    )
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(RequestValidationError)
async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", [])[1:]) or "request"
    return JSONResponse({"detail": f"{field}: {first.get('msg', 'invalid value')}"}, status_code=422)


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(users.security_router)
# every route with an {eid} in its path checks the signed-in user may open that engagement
for r in (engagements, framework, entities, assessments, interviews, evidence, analysis, exports):
    app.include_router(r.router, dependencies=[Depends(engagement_access)])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "ai_provider": settings.ai_provider}


# ---- single-page front end -------------------------------------------------
dist: Path = settings.frontend_dir
if (dist / "index.html").is_file():
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found."}, status_code=404)  # type: ignore[return-value]
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})
else:
    @app.get("/", include_in_schema=False)
    def no_frontend() -> JSONResponse:
        return JSONResponse({"detail": "Front end not built. Run `npm run build` in the frontend folder."}, status_code=503)
