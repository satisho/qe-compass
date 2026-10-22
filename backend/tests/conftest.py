from __future__ import annotations

import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="qec-test-")
os.environ["QEC_DATA_DIR"] = _TMP
os.environ["QEC_FRONTEND_DIR"] = os.path.join(_TMP, "no-frontend")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

H = {"X-Requested-With": "qe-compass"}
ADMIN = {"name": "Ada Admin", "email": "admin@example.com", "password": "Sup3rSecret!x"}


class Client:
    def __init__(self, tc: TestClient):
        self.tc = tc

    def _do(self, method: str, url: str, expect: int | None = None, **kw):
        headers = {**H, **kw.pop("headers", {})}
        r = self.tc.request(method, url, headers=headers, **kw)
        if expect is not None:
            assert r.status_code == expect, f"{method} {url} -> {r.status_code}: {r.text}"
        return r

    def get(self, url, expect=200, **kw):
        return self._do("GET", url, expect, **kw)

    def post(self, url, expect=None, **kw):
        return self._do("POST", url, expect, **kw)

    def put(self, url, expect=200, **kw):
        return self._do("PUT", url, expect, **kw)

    def patch(self, url, expect=200, **kw):
        return self._do("PATCH", url, expect, **kw)

    def delete(self, url, expect=200, **kw):
        return self._do("DELETE", url, expect, **kw)


@pytest.fixture(scope="session")
def tc():
    with TestClient(app) as c:
        yield c
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(scope="session")
def admin(tc) -> Client:
    c = Client(tc)
    if c.get("/api/auth/status").json()["needs_setup"]:
        c.post("/api/auth/setup", json=ADMIN, expect=200)
    else:
        c.post("/api/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]}, expect=200)
    return c


@pytest.fixture()
def engagement(admin) -> dict:
    return admin.post("/api/engagements", json={"client": "Acme", "title": "QE Discovery", "start_date": "2026-09-28"},
                      expect=201).json()
