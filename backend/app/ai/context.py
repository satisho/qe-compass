"""Builds the structured, provider-neutral view of a workspace the analyst reasons over."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analytics import Workspace, r2
from ..models import Evidence, Interview
from .base import FocusAreaRef

TYPE_LABEL = {"lob": "Line of business", "program": "Program", "app": "Application"}


def focus_area_refs(ws: Workspace) -> list[FocusAreaRef]:
    out = []
    for f in ws.fas:
        p = ws.pillars[f.pillar_index]
        fa = next(x for x in p.focus_areas if x.id == f.id)
        out.append(FocusAreaRef(f.id, f.key, f.name, p.short, fa.description, f.question, f.recommendation, f.horizon))
    return out


def scale_labels(ws: Workspace) -> list[str]:
    return [s["label"] for s in ws.settings.get("scale", [])]


def week_of(ws: Workspace) -> int:
    eng = ws.engagement
    w = (date.today() - eng.start_date).days // 7 + 1
    return max(1, min(eng.weeks, w))


def build_context(db: Session, ws: Workspace, scope: int | None) -> dict:
    in_scope = ws.top_ids() if scope is None or scope not in ws.by_id else [scope]
    scope_set = set(in_scope)
    for i in list(in_scope):
        scope_set.update(ws.descendants(i))

    entities = []
    for e, depth in ws.tree():
        cells = {}
        for f in ws.fas:
            s = ws.score(e.id, f.id)
            a = ws.scores.get((e.id, f.id))
            if s is None and not (a and a.notes):
                continue
            cells[f.id] = {
                "score": r2(s),
                "inherited": ws.inherited(e.id, f.id),
                "confidence": ws.confidence(e.id, f.id),
                "evidence": sum(ws.linked(e.id, f.id)),
                "notes": (a.notes if a else "")[:300],
            }
        entities.append({
            "id": e.id, "name": e.name, "type": TYPE_LABEL.get(e.type, e.type), "path": ws.path(e.id),
            "depth": depth, "owner": e.owner, "art": e.art, "apps": e.apps,
            "top_level": e.id in ws.top_ids(), "in_scope": e.id in scope_set,
            "overall": r2(ws.entity_overall(e.id)), "cells": cells,
        })

    ivs = db.scalars(select(Interview).where(Interview.engagement_id == ws.engagement.id).order_by(Interview.date.desc()))
    evs = db.scalars(select(Evidence).where(Evidence.engagement_id == ws.engagement.id).order_by(Evidence.created_at.desc()))
    fa_name = {f.id: f.name for f in ws.fas}
    return {
        "client": ws.engagement.client,
        "week": week_of(ws),
        "weeks": ws.engagement.weeks,
        "scale": scale_labels(ws),
        "thresholds": ws.settings.get("thresholds"),
        "scope": {"name": "Enterprise" if len(in_scope) != 1 or scope is None else ws.by_id[in_scope[0]].name,
                  "entity_ids": in_scope},
        "overall": r2(ws.ent_overall(in_scope)),
        "coverage": round(ws.coverage(in_scope), 3),
        "pillars": [{"name": p.name, "short": p.short, "target": p.target, "score": r2(ws.ent_pillar(pi, in_scope))}
                    for pi, p in enumerate(ws.pillars)],
        "focus_areas": [{"id": f.id, "key": f.key, "name": f.name, "pillar": ws.pillars[f.pillar_index].short,
                         "horizon": f.horizon, "recommendation": f.recommendation, "question": f.question,
                         "target": ws.pillars[f.pillar_index].target,
                         "score": r2(ws.ent_fa(f.id, in_scope))} for f in ws.fas],
        "entities": entities,
        "evidence_gaps": [{"entity": ws.by_id[g["entity_id"]].name, "entity_id": g["entity_id"],
                           "focus_area": fa_name[g["focus_area_id"]], "focus_area_id": g["focus_area_id"], "why": g["why"]}
                          for g in ws.evidence_gaps(in_scope)],
        "conflicts": [{"entity": ws.by_id[c["entity_id"]].name, "a": fa_name[c["a"]], "b": fa_name[c["b"]],
                       "a_score": c["a_score"], "b_score": c["b_score"], "message": c["message"]}
                      for c in ws.conflicts(in_scope)],
        "interviews": [{"entity": ws.path(i.entity_id) if i.entity_id in ws.by_id else "", "stakeholder": i.stakeholder,
                        "date": i.date.isoformat(), "status": i.status, "notes": (i.notes or "")[:500]}
                       for i in ivs if i.entity_id in scope_set][:30],
        "artifacts": [{"entity": ws.path(e.entity_id) if e.entity_id in ws.by_id else "", "name": e.name,
                       "type": e.doc_type, "summary": (e.summary or "")[:240]}
                      for e in evs if e.entity_id in scope_set][:40],
    }
