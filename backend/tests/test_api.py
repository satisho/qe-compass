from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app.main import app

from .conftest import ADMIN, H, Client


def ws(admin, eid):
    return admin.get(f"/api/engagements/{eid}/workspace").json()


def fa_id(w, key):
    return next(f["id"] for p in w["pillars"] for f in p["focus_areas"] if f["key"] == key)


def test_setup_only_once_and_csrf(admin, tc):
    r = admin.post("/api/auth/setup", json=ADMIN)
    assert r.status_code == 409
    # missing custom header is rejected for state-changing calls
    r = tc.post("/api/engagements", json={"client": "x", "title": "y", "start_date": "2026-01-01"})
    assert r.status_code == 403
    assert admin.get("/api/health").json()["status"] == "ok"


def test_template_and_entities_rollup(admin, engagement):
    eid = engagement["id"]
    w = ws(admin, eid)
    assert len(w["pillars"]) == 5 and sum(len(p["focus_areas"]) for p in w["pillars"]) == 25
    lob = admin.post(f"/api/engagements/{eid}/entities", json={"name": "Booking", "type": "lob", "apps": 10}, expect=201).json()
    prog = admin.post(f"/api/engagements/{eid}/entities",
                      json={"name": "Fare program", "type": "program", "parent_id": lob["id"], "apps": 4}, expect=201).json()
    app1 = admin.post(f"/api/engagements/{eid}/entities",
                      json={"name": "Web app", "type": "app", "parent_id": prog["id"], "apps": 1}, expect=201).json()
    # cycle prevention
    r = admin.patch(f"/api/engagements/{eid}/entities/{lob['id']}", json={"parent_id": app1["id"]}, expect=None)
    assert r.status_code == 400
    eng3 = fa_id(w, "eng3")
    admin.put(f"/api/engagements/{eid}/assessments/{prog['id']}/{eng3}", json={"score": 2, "set_score": True})
    admin.put(f"/api/engagements/{eid}/assessments/{app1['id']}/{eng3}", json={"score": 4, "set_score": True})
    a = ws(admin, eid)["analytics"]
    # LOB has no direct score -> rolls up from its program (which is scored directly: 2)
    cell = a["entities"][str(lob["id"])]["cells"][str(eng3)]
    assert cell["score"] == 2 and cell["inherited"] is True
    # enterprise only counts top-level entities
    assert a["top_level"] == [lob["id"]]
    assert a["enterprise"]["cells"][str(eng3)] == 2
    # clearing the program's score makes it roll up from the application
    admin.put(f"/api/engagements/{eid}/assessments/{prog['id']}/{eng3}", json={"score": None, "set_score": True})
    a = ws(admin, eid)["analytics"]
    assert a["entities"][str(lob["id"])]["cells"][str(eng3)]["score"] == 4
    # deleting the program re-parents the application to the LOB
    admin.delete(f"/api/engagements/{eid}/entities/{prog['id']}")
    ents = {e["id"]: e for e in ws(admin, eid)["entities"]}
    assert ents[app1["id"]]["parent_id"] == lob["id"]


def test_interview_extract_and_apply(admin, engagement):
    eid = engagement["id"]
    lob = admin.post(f"/api/engagements/{eid}/entities", json={"name": "Field Service"}, expect=201).json()
    notes = ("Regression is mostly manual and takes two weeks per release; automation covers only work orders. "
             "One shared test environment; refreshes take 3-4 weeks and block regression. "
             "Defects are tracked in Jira but escaped defects to production are not measured.")
    iv = admin.post(f"/api/engagements/{eid}/interviews", json={
        "entity_id": lob["id"], "date": "2026-10-08", "stakeholder": "EAM Platform Lead", "status": "completed",
        "notes": notes}, expect=201).json()
    iv = admin.post(f"/api/engagements/{eid}/interviews/{iv['id']}/extract", expect=200).json()
    assert iv["findings"], "rules engine should find focus areas"
    assert all(f["score"] is None or 1 <= f["score"] <= 5 for f in iv["findings"])
    iv = admin.post(f"/api/engagements/{eid}/interviews/{iv['id']}/apply",
                    json={"indexes": list(range(len(iv["findings"])))}, expect=200).json()
    assert iv["applied"] == len(iv["findings"])
    w = ws(admin, eid)
    notes_saved = [a["notes"] for a in w["assessments"] if a["entity_id"] == lob["id"]]
    assert any("EAM Platform Lead" in n for n in notes_saved)
    acts = admin.get(f"/api/engagements/{eid}/activity").json()
    assert any("extracted" in a["text"] for a in acts)


def test_evidence_upload_classify_download(admin, engagement):
    eid = engagement["id"]
    lob = admin.post(f"/api/engagements/{eid}/entities", json={"name": "Digital"}, expect=201).json()
    csv_bytes = b"id,summary,severity\n1,Checkout defect escaped to production,High\n2,Login bug,Low\n"
    import docx

    d = docx.Document()
    d.add_paragraph("Test Strategy v2. Regression testing is manual in some teams. No performance testing.")
    buf = io.BytesIO()
    d.save(buf)
    files = [("files", ("Jira_Defects_Q3.csv", csv_bytes, "text/csv")),
             ("files", ("Test_Strategy.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))]
    out = admin.post(f"/api/engagements/{eid}/evidence/upload", data={"entity_id": str(lob["id"])}, files=files, expect=201).json()
    assert len(out) == 2
    w = ws(admin, eid)
    keys = {f["id"]: f["key"] for p in w["pillars"] for f in p["focus_areas"]}
    assert "del3" in {keys[i] for i in out[0]["focus_area_ids"]}
    assert out[1]["doc_type"].startswith("Test strategy")
    r = admin.get(f"/api/engagements/{eid}/evidence/{out[0]['id']}/file")
    assert r.content == csv_bytes
    r = admin.post(f"/api/engagements/{eid}/evidence/upload", files=[("files", ("evil.exe", b"MZ", "application/octet-stream"))])
    assert r.status_code == 400
    link = admin.post(f"/api/engagements/{eid}/evidence/link", json={"name": "Wiki", "url": "javascript:alert(1)"})
    assert link.status_code == 422


def test_analyst_snapshot_export_import(admin):
    sample = admin.post("/api/engagements/sample", expect=201).json()
    eid = sample["id"]
    w = ws(admin, eid)
    assert len(w["entities"]) == 8
    assert w["analytics"]["enterprise"]["overall"] is not None
    for q in ["Where are the biggest gaps?", "What evidence is still missing?", "Draft follow-up interview questions",
              "Any conflicting signals?", "Quick wins for the next 90 days", "Write an executive summary",
              "How is Enterprise Asset Mgmt doing on automation engineering?", "compare entities"]:
        r = admin.post(f"/api/engagements/{eid}/analyst", json={"question": q}, expect=200).json()
        assert r["answer"].startswith("## "), (q, r["answer"][:80])
    snaps = admin.get(f"/api/engagements/{eid}/snapshots").json()
    assert [s["version"] for s in snaps] == [1]
    s2 = admin.post(f"/api/engagements/{eid}/snapshots", json={"note": "Week 3"}, expect=201).json()
    assert s2["version"] == 2 and s2["narrative"]
    csv_text = admin.get(f"/api/engagements/{eid}/export.csv").content.decode("utf-8-sig")
    assert csv_text.count("\n") == 8 * 25 + 1
    exported = admin.get(f"/api/engagements/{eid}/export.json").content
    imp = admin.post("/api/engagements/import", files=[("file", ("x.json", exported, "application/json"))], expect=201).json()
    w2 = ws(admin, imp["id"])
    assert len(w2["entities"]) == 8 and len(w2["assessments"]) == len(w["assessments"])
    assert w2["analytics"]["enterprise"]["overall"] == w["analytics"]["enterprise"]["overall"]
    bad = admin.post("/api/engagements/import", files=[("file", ("x.json", b'{"format":"nope"}', "application/json"))])
    assert bad.status_code == 422


def test_roles(admin, engagement):
    eid = engagement["id"]
    vid = admin.post("/api/users", json={"name": "Vic Viewer", "email": "viewer@example.com", "role": "viewer",
                                         "password": "Viewer12345A"}, expect=201).json()["id"]
    with TestClient(app) as tc2:
        v = Client(tc2)
        v.post("/api/auth/login", json={"email": "viewer@example.com", "password": "Viewer12345A"}, expect=200)
        assert v.get("/api/auth/me").json()["must_change_password"] is True
        # not a member yet: the engagement is invisible
        assert v.get(f"/api/engagements/{eid}/workspace", expect=None).status_code == 404
        assert all(e["id"] != eid for e in v.get("/api/engagements").json())
        admin.post(f"/api/engagements/{eid}/members", json={"user_id": vid}, expect=201)
        assert any(e["id"] == eid for e in v.get("/api/engagements").json())
        v.get(f"/api/engagements/{eid}/workspace")
        assert v.post(f"/api/engagements/{eid}/entities", json={"name": "X"}).status_code == 403
        assert v.get("/api/users", expect=None).status_code == 403
        # analyst is available to viewers
        v.post(f"/api/engagements/{eid}/analyst", json={"question": "summary"}, expect=200)
        v.post("/api/auth/change-password", json={"current_password": "Viewer12345A", "new_password": "Better12345B"}, expect=200)
        assert v.get("/api/auth/me").json()["must_change_password"] is False
    # last admin cannot be demoted
    me = admin.get("/api/auth/me").json()
    assert admin.patch(f"/api/users/{me['id']}", json={"role": "viewer"}, expect=None).status_code == 400


def test_framework_edits(admin, engagement):
    eid = engagement["id"]
    w = ws(admin, eid)
    p = w["pillars"][0]
    admin.patch(f"/api/engagements/{eid}/framework/pillars/{p['id']}", json={"target": 4.0})
    admin.post(f"/api/engagements/{eid}/framework/pillars/{p['id']}/focus-areas", json={"name": "Mobile device testing"}, expect=201)
    admin.patch(f"/api/engagements/{eid}/framework/settings", json={"thresholds": {"gap": 2.0, "strong": 3.5}, "weighting": "equal"})
    bad = admin.patch(f"/api/engagements/{eid}/framework/settings", json={"thresholds": {"gap": 4, "strong": 3}}, expect=None)
    assert bad.status_code == 422
    newp = admin.post(f"/api/engagements/{eid}/framework/pillars", json={"name": "Security QE"}, expect=201).json()
    w = ws(admin, eid)
    assert len(w["pillars"]) == 6 and w["pillars"][0]["target"] == 4.0 and len(w["pillars"][0]["focus_areas"]) == 6
    assert w["settings"]["weighting"] == "equal"
    admin.delete(f"/api/engagements/{eid}/framework/pillars/{newp['id']}")
    assert len(ws(admin, eid)["pillars"]) == 5


def test_suggest_level(admin, engagement):
    eid = engagement["id"]
    r = admin.post(f"/api/engagements/{eid}/suggest-level", json={"notes": "Testing is manual and varies by team, tracked in spreadsheets"}).json()
    assert r["level"] == 2 and r["cues"]
    r = admin.post(f"/api/engagements/{eid}/suggest-level", json={"notes": "short"}).json()
    assert r["level"] is None
