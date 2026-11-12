"""QE Compass 2.0 is client-neutral: nothing it ships names a real client."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLIENT_TERMS = re.compile(r"bc ?ferries|bcferries|maximo|sailing|vessel|\bfleet\b", re.I)


def test_sample_engagement_is_fictional(admin):
    eng = admin.post("/api/engagements/sample", expect=201).json()
    assert eng["client"] == "Northwind Sample Co."
    dump = admin.get(f"/api/engagements/{eng['id']}/export.json").text
    assert not CLIENT_TERMS.search(dump), CLIENT_TERMS.search(dump).group(0)


def test_no_client_specific_text_ships():
    files = [*ROOT.glob("backend/app/**/*.py"), *ROOT.glob("backend/app/**/*.json"),
             *ROOT.glob("frontend/src/**/*.ts*"), ROOT / "README.md"]
    hits = [str(p.relative_to(ROOT)) for p in files if CLIENT_TERMS.search(p.read_text(encoding="utf-8"))]
    assert hits == []
