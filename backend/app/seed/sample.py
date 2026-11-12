"""Sample engagement for a fictional client (illustrative data), shifted so it always looks current."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Activity, Assessment, Engagement, Entity, Evidence, FocusArea, Interview, Snapshot
from ..templates import DEFAULT_SETTINGS, FRAMEWORK, apply_template

SAMPLE = Path(__file__).with_name("sample_engagement.json")
SAMPLE_CLIENT = "Northwind Sample Co."  # fictional; rename the engagement to show it under another name
ANCHOR = date(2026, 10, 16)  # the day the sample data was authored
KEYS = [p[0] for p in FRAMEWORK]


def create_sample(db: Session, user_id: int | None) -> Engagement:
    doc = json.loads(SAMPLE.read_text(encoding="utf-8"))
    today = date.today()
    shift = today - ANCHOR
    now = datetime.now(timezone.utc)

    def at(rel: int) -> datetime:
        return now + timedelta(seconds=rel)

    eng = Engagement(client=SAMPLE_CLIENT, title="Enterprise Quality Engineering Discovery (sample)",
                     start_date=today - timedelta(days=16), weeks=8, interviews_planned=32,
                     settings=dict(DEFAULT_SETTINGS), created_by=user_id)
    db.add(eng)
    db.flush()
    apply_template(eng, db)
    db.flush()
    by_key = {f.key: f for f in db.scalars(select(FocusArea).where(FocusArea.engagement_id == eng.id))}

    def fa(sample_id: int) -> FocusArea:
        return by_key[f"{KEYS[sample_id // 100 - 1]}{sample_id % 100}"]

    ents: dict[int, Entity] = {}
    for x in doc["entities"]:
        e = Entity(engagement_id=eng.id, type=x["type"], name=x["name"], apps=x["apps"], art=x["art"],
                   owner=x["owner"], criticality=x["criticality"], position=x["position"])
        db.add(e)
        db.flush()
        ents[x["id"]] = e
    for x in doc["entities"]:
        if x["parent_id"]:
            ents[x["id"]].parent_id = ents[x["parent_id"]].id
    for a in doc["assessments"]:
        db.add(Assessment(engagement_id=eng.id, entity_id=ents[a["entity_id"]].id, focus_area_id=fa(a["focus_area_id"]).id,
                          score=a["score"], confidence=a["confidence"], notes=a["notes"], updated_by=None,
                          updated_at=at(a["rel"])))
    for i in doc["interviews"]:
        iv = Interview(engagement_id=eng.id, entity_id=ents[i["entity_id"]].id if i["entity_id"] else None,
                       date=date.fromisoformat(i["date"]) + shift, stakeholder=i["stakeholder"], type=i["type"],
                       status=i["status"], notes=i["notes"], created_at=at(i["rel"]), updated_at=at(i["rel"]))
        iv.focus_areas = [fa(f) for f in i["focus_area_ids"]]
        db.add(iv)
    for x in doc["evidence"]:
        ev = Evidence(engagement_id=eng.id, entity_id=ents[x["entity_id"]].id if x["entity_id"] else None, name=x["name"],
                      kind="link", doc_type=x["doc_type"], summary=x["summary"], size=x["size"],
                      classified_by=x["classified_by"], created_at=at(x["rel"]))
        ev.focus_areas = [fa(f) for f in x["focus_area_ids"]]
        db.add(ev)
    for s in doc["snapshots"]:
        db.add(Snapshot(engagement_id=eng.id, version=s["version"], note=s["note"], narrative=s["narrative"],
                        data=s["data"], created_at=at(s["rel"])))
    for a in doc["activity"]:
        text = a["text"]
        kind = ("interview" if any(w in text for w in ("interview", "walkthrough", "finding")) else
                "evidence" if "evidence" in text else "report" if "published" in text else
                "assessment" if "scored" in text else "scope")
        db.add(Activity(engagement_id=eng.id, kind=kind, text=text, created_at=at(a["rel"])))
    db.add(Activity(engagement_id=eng.id, user_id=user_id, kind="scope", text="loaded the sample engagement",
                    created_at=now))
    db.commit()
    return eng
