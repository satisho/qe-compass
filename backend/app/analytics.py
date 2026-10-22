"""Maturity analytics.

Scoring rules
-------------
* An entity's score for a focus area is its own assessment when one exists.
  Otherwise it rolls up from its child programs/applications, weighted by
  application count (or equally, per the engagement's weighting rule).
* Pillar score = mean of the entity's focus-area scores in that pillar.
* Entity overall = mean of pillar scores, weighted by pillar weight.
* Enterprise figures roll up from top-level entities only, so children are
  never counted twice.
* Confidence is the assessor's override when set, else derived from linked
  evidence (completed interviews and artifacts on the entity or its children):
  3+ = high, 2 = medium, fewer = low.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Assessment, Engagement, Entity, Evidence, Interview, Pillar
from .templates import CONFLICT_RULES, DEFAULT_SETTINGS

STATUS_LABEL = {
    "gap": "Potential gap",
    "partial": "Partial capability",
    "val": "To be validated",
    "strong": "Strength",
}


def wavg(pairs: list[tuple[float | None, float]]) -> float | None:
    num = den = 0.0
    for v, w in pairs:
        if v is not None and w:
            num += v * w
            den += w
    return num / den if den else None


def mean(vals: list[float | None]) -> float | None:
    xs = [v for v in vals if v is not None]
    return sum(xs) / len(xs) if xs else None


def r2(v: float | None) -> float | None:
    return None if v is None else round(v, 2)


@dataclass
class FA:
    id: int
    key: str
    name: str
    pillar_index: int
    horizon: str
    recommendation: str
    question: str


@dataclass
class Workspace:
    engagement: Engagement
    settings: dict
    pillars: list[Pillar]
    fas: list[FA]
    entities: list[Entity]
    scores: dict[tuple[int, int], Assessment]
    interview_links: list[tuple[int | None, set[int]]]
    evidence_links: list[tuple[int | None, set[int]]]
    by_id: dict[int, Entity] = field(default_factory=dict)
    children: dict[int | None, list[Entity]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.by_id = {e.id: e for e in self.entities}
        self.children = {}
        for e in self.entities:
            parent = e.parent_id if e.parent_id in self.by_id and e.parent_id != e.id else None
            self.children.setdefault(parent, []).append(e)
        for lst in self.children.values():
            lst.sort(key=lambda e: (e.position, e.name.lower()))
        self.fa_by_id = {f.id: f for f in self.fas}
        self.fa_by_key = {f.key: f for f in self.fas}
        self._sc = lru_cache(maxsize=None)(self._score)
        self._desc_cache: dict[int, list[int]] = {}

    # ---- structure -------------------------------------------------------
    @property
    def top_level(self) -> list[Entity]:
        return self.children.get(None, [])

    def kids(self, eid: int) -> list[Entity]:
        return self.children.get(eid, [])

    def descendants(self, eid: int) -> list[int]:
        if eid in self._desc_cache:
            return self._desc_cache[eid]
        out: list[int] = []
        stack, seen = [eid], {eid}
        while stack:
            for c in self.kids(stack.pop()):
                if c.id not in seen:
                    seen.add(c.id)
                    out.append(c.id)
                    stack.append(c.id)
        self._desc_cache[eid] = out
        return out

    def tree(self) -> list[tuple[Entity, int]]:
        out: list[tuple[Entity, int]] = []
        seen: set[int] = set()

        def walk(parent: int | None, depth: int) -> None:
            for e in self.children.get(parent, []):
                if e.id in seen:
                    continue
                seen.add(e.id)
                out.append((e, depth))
                walk(e.id, depth + 1)

        walk(None, 0)
        out.extend((e, 0) for e in self.entities if e.id not in seen)
        return out

    def path(self, eid: int) -> str:
        names, e, guard = [], self.by_id.get(eid), 0
        while e and guard < 8:
            names.insert(0, e.name)
            e = self.by_id.get(e.parent_id) if e.parent_id and e.parent_id != e.id else None
            guard += 1
        return " › ".join(names)

    # ---- scoring ---------------------------------------------------------
    def weight(self, eid: int) -> float:
        if self.settings.get("weighting") == "equal":
            return 1.0
        return float(max(1, self.by_id[eid].apps or 1))

    def direct(self, eid: int, fid: int) -> int | None:
        a = self.scores.get((eid, fid))
        return a.score if a else None

    def _score(self, eid: int, fid: int, depth: int = 0) -> float | None:
        s = self.direct(eid, fid)
        if s is not None:
            return float(s)
        if depth > 6:
            return None
        kids = self.kids(eid)
        if not kids:
            return None
        return wavg([(self._sc(k.id, fid, depth + 1), self.weight(k.id)) for k in kids])

    def score(self, eid: int, fid: int) -> float | None:
        return self._sc(eid, fid, 0)

    def inherited(self, eid: int, fid: int) -> bool:
        return self.direct(eid, fid) is None and self.score(eid, fid) is not None

    def pillar_fas(self, pi: int) -> list[FA]:
        return [f for f in self.fas if f.pillar_index == pi]

    def entity_pillar(self, eid: int, pi: int) -> float | None:
        return mean([self.score(eid, f.id) for f in self.pillar_fas(pi)])

    def entity_overall(self, eid: int) -> float | None:
        return wavg([(self.entity_pillar(eid, pi), p.weight) for pi, p in enumerate(self.pillars)])

    def top_ids(self) -> list[int]:
        return [e.id for e in self.top_level]

    def ent_fa(self, fid: int, lids: list[int] | None = None) -> float | None:
        lids = self.top_ids() if lids is None else lids
        return wavg([(self.score(i, fid), self.weight(i)) for i in lids])

    def ent_pillar(self, pi: int, lids: list[int] | None = None) -> float | None:
        lids = self.top_ids() if lids is None else lids
        return wavg([(self.entity_pillar(i, pi), self.weight(i)) for i in lids])

    def ent_overall(self, lids: list[int] | None = None) -> float | None:
        return wavg([(self.ent_pillar(pi, lids), p.weight) for pi, p in enumerate(self.pillars)])

    # ---- evidence & confidence -------------------------------------------
    def linked(self, eid: int, fid: int) -> tuple[int, int]:
        ids = {eid, *self.descendants(eid)}
        iv = sum(1 for ent, fas in self.interview_links if ent in ids and fid in fas)
        ev = sum(1 for ent, fas in self.evidence_links if ent in ids and fid in fas)
        return iv, ev

    def confidence(self, eid: int, fid: int) -> str | None:
        if self.score(eid, fid) is None:
            return None
        a = self.scores.get((eid, fid))
        if a and a.score is not None and a.confidence:
            return a.confidence
        n = sum(self.linked(eid, fid))
        return "high" if n >= 3 else "med" if n >= 2 else "low"

    def status(self, s: float | None) -> str:
        t = self.settings.get("thresholds", DEFAULT_SETTINGS["thresholds"])
        if s is None:
            return "val"
        if s <= t.get("gap", 2.25):
            return "gap"
        if s < t.get("strong", 3.25):
            return "partial"
        return "strong"

    def coverage(self, lids: list[int] | None = None) -> float:
        lids = self.top_ids() if lids is None else lids
        total = ok = 0
        for i in lids:
            for f in self.fas:
                total += 1
                if self.score(i, f.id) is not None and self.confidence(i, f.id) != "low":
                    ok += 1
        return ok / total if total else 0.0

    def evidence_gaps(self, lids: list[int] | None = None) -> list[dict]:
        lids = self.top_ids() if lids is None else lids
        out = []
        for i in lids:
            for f in self.fas:
                s, c = self.score(i, f.id), self.confidence(i, f.id)
                n = sum(self.linked(i, f.id))
                if s is None or c == "low" or n < 1:
                    why = "Not yet assessed" if s is None else "Low confidence" if c == "low" else "No linked evidence"
                    out.append({"entity_id": i, "focus_area_id": f.id, "why": why})
        return out

    def conflicts(self, lids: list[int] | None = None) -> list[dict]:
        lids = self.top_ids() if lids is None else lids
        out = []
        for i in lids:
            for a_key, b_key, msg in CONFLICT_RULES:
                fa, fb = self.fa_by_key.get(a_key), self.fa_by_key.get(b_key)
                if not fa or not fb:
                    continue
                x, y = self.score(i, fa.id), self.score(i, fb.id)
                if x is not None and y is not None and x >= 3 and y <= 2:
                    out.append({"entity_id": i, "a": fa.id, "b": fb.id, "a_score": r2(x), "b_score": r2(y), "message": msg})
        return out

    def ranked(self, lids: list[int] | None = None) -> list[tuple[FA, float]]:
        rows = [(f, self.ent_fa(f.id, lids)) for f in self.fas]
        return sorted([(f, s) for f, s in rows if s is not None], key=lambda x: x[1])

    def counts(self, lids: list[int] | None = None) -> dict[str, int]:
        lids = self.top_ids() if lids is None else lids
        c = {"gap": 0, "partial": 0, "val": 0, "strong": 0}
        for i in lids:
            for f in self.fas:
                c[self.status(self.score(i, f.id))] += 1
        return c

    def level_label(self, v: float | None) -> str:
        if v is None:
            return ""
        scale = self.settings.get("scale", DEFAULT_SETTINGS["scale"])
        idx = max(1, min(len(scale), round(v))) - 1
        return scale[idx]["label"]


def load_workspace(db: Session, engagement: Engagement) -> Workspace:
    pillars = list(
        db.scalars(
            select(Pillar).where(Pillar.engagement_id == engagement.id)
            .options(selectinload(Pillar.focus_areas)).order_by(Pillar.position, Pillar.id)
        )
    )
    fas: list[FA] = []
    for pi, p in enumerate(pillars):
        for f in sorted(p.focus_areas, key=lambda x: (x.position, x.id)):
            fas.append(FA(f.id, f.key, f.name, pi, f.horizon, f.recommendation, f.question))
    entities = list(db.scalars(select(Entity).where(Entity.engagement_id == engagement.id)))
    scores = {
        (a.entity_id, a.focus_area_id): a
        for a in db.scalars(select(Assessment).where(Assessment.engagement_id == engagement.id))
    }
    ivs = db.scalars(
        select(Interview).where(Interview.engagement_id == engagement.id, Interview.status == "completed")
        .options(selectinload(Interview.focus_areas))
    )
    evs = db.scalars(select(Evidence).where(Evidence.engagement_id == engagement.id).options(selectinload(Evidence.focus_areas)))
    settings = {**DEFAULT_SETTINGS, **(engagement.settings or {})}
    return Workspace(
        engagement=engagement,
        settings=settings,
        pillars=pillars,
        fas=fas,
        entities=entities,
        scores=scores,
        interview_links=[(i.entity_id, {f.id for f in i.focus_areas}) for i in ivs],
        evidence_links=[(e.entity_id, {f.id for f in e.focus_areas}) for e in evs],
    )


# ---- API payloads ---------------------------------------------------------

def analytics_payload(ws: Workspace) -> dict[str, Any]:
    """Everything the UI needs to render scores, heatmaps and status."""
    entities: dict[int, Any] = {}
    for e, depth in ws.tree():
        cells = {}
        for f in ws.fas:
            s = ws.score(e.id, f.id)
            iv, ev = ws.linked(e.id, f.id)
            cells[f.id] = {
                "score": r2(s),
                "inherited": ws.inherited(e.id, f.id),
                "confidence": ws.confidence(e.id, f.id),
                "interviews": iv,
                "evidence": ev,
                "status": ws.status(s),
            }
        entities[e.id] = {
            "depth": depth,
            "path": ws.path(e.id),
            "overall": r2(ws.entity_overall(e.id)),
            "pillars": [r2(ws.entity_pillar(e.id, pi)) for pi in range(len(ws.pillars))],
            "coverage": round(ws.coverage([e.id]), 3),
            "cells": cells,
        }
    ranked = ws.ranked()
    return {
        "order": [e.id for e, _ in ws.tree()],
        "top_level": ws.top_ids(),
        "entities": entities,
        "enterprise": {
            "overall": r2(ws.ent_overall()),
            "level": ws.level_label(ws.ent_overall()),
            "coverage": round(ws.coverage(), 3),
            "pillars": [r2(ws.ent_pillar(pi)) for pi in range(len(ws.pillars))],
            "cells": {f.id: r2(ws.ent_fa(f.id)) for f in ws.fas},
            "counts": ws.counts(),
            "total": len(ws.top_ids()) * len(ws.fas),
        },
        "ranked": [{"focus_area_id": f.id, "score": r2(s)} for f, s in ranked],
        "conflicts": ws.conflicts(),
        "evidence_gaps": ws.evidence_gaps(),
    }


def scope_summary(ws: Workspace, scope: int | None) -> dict[str, Any]:
    lids = ws.top_ids() if scope is None or scope not in ws.by_id else [scope]
    return {
        "overall": r2(ws.ent_overall(lids)),
        "coverage": round(ws.coverage(lids), 3),
        "evidence_gaps": len(ws.evidence_gaps(lids)),
        "conflicts": len(ws.conflicts(lids)),
        "gap_focus_areas": sum(1 for _, s in ws.ranked(lids) if ws.status(s) == "gap"),
    }


def snapshot_payload(ws: Workspace, interviews_completed: int, evidence_count: int) -> dict[str, Any]:
    """An immutable copy of the dashboard, stored with names rather than ids."""
    lids = ws.top_ids()
    ranked = ws.ranked()

    def pick(h: str) -> list[dict]:
        return [
            {"name": f.name, "rec": f.recommendation, "score": r2(s), "target": ws.pillars[f.pillar_index].target}
            for f, s in ranked if f.horizon == h
        ][:4]

    strengths = []
    for f, s in list(reversed(ranked))[:3]:
        best = sorted(
            [(e, ws.score(e.id, f.id)) for e in ws.top_level if ws.score(e.id, f.id) is not None],
            key=lambda x: -x[1],
        )
        strengths.append({"name": f.name, "score": r2(s), "best": best[0][0].name if best else ""})
    return {
        "overall": r2(ws.ent_overall()),
        "level": ws.level_label(ws.ent_overall()),
        "coverage": round(ws.coverage(), 3),
        "apps": sum(max(1, e.apps or 1) for e in ws.top_level),
        "counts": ws.counts(),
        "total": len(lids) * len(ws.fas),
        "interviews": interviews_completed,
        "evidence": evidence_count,
        "evidence_gaps": len(ws.evidence_gaps()),
        "conflicts": len(ws.conflicts()),
        "pillars": [
            {"name": p.name, "short": p.short, "color": p.color, "target": p.target, "score": r2(ws.ent_pillar(pi))}
            for pi, p in enumerate(ws.pillars)
        ],
        "entities": [
            {"name": e.name, "type": e.type, "apps": e.apps, "overall": r2(ws.entity_overall(e.id)),
             "pillars": [r2(ws.entity_pillar(e.id, pi)) for pi in range(len(ws.pillars))]}
            for e in ws.top_level
        ],
        "gaps": [
            {"name": f.name, "pillar": ws.pillars[f.pillar_index].short, "score": r2(s), "rec": f.recommendation,
             "status": ws.status(s)}
            for f, s in ranked[:6]
        ],
        "strengths": strengths,
        "roadmap": {"now": pick("now"), "next": pick("next"), "later": pick("later")},
        "scale": [s["label"] for s in ws.settings.get("scale", [])],
    }
