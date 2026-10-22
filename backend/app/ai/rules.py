"""Offline analysis engine.

Deterministic, explainable heuristics that need no network access. It is the
default provider and the fallback when a model-backed provider is unavailable.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .base import AnalystRequest, Classification, Finding, FocusAreaRef, LevelSuggestion

LEVEL_CUES: list[tuple[int, list[str]]] = [
    (5, ["self-heal", "predictive", "autonomous", "optimi", "continuously improv", "ai-driven"]),
    (4, ["measured", "kpi", "dashboard", "enforced", "every merge", "every commit", "slo", "tracked", "on every change"]),
    (3, ["defined", "documented", "standard", "consistent", "most teams", "framework", "in the pipeline", "runs nightly"]),
    (2, ["some teams", "partial", "inconsistent", "varies", "manual", "spreadsheet", "email", "trialling", "pilot"]),
    (1, ["no ", "none", "ad hoc", "not measured", "blocks", "block ", "weeks", "nobody", "no one", "not in place", "judgement call"]),
]

STOP = set(
    "about their there these those which with from into have that this will what when where while other across under "
    "over more less such than then them they your ours shared quality testing tests based level management engineering".split()
)

DOC_RULES: list[tuple[str, list[str], str]] = [
    (r"regress|test result|execution|test run|pass rate|test summary", ["eng3", "del2", "del5"], "Execution results"),
    (r"defect|bug|jira|incident|leakage|escaped", ["del3", "del4"], "Defect data"),
    (r"strategy|test plan|test approach|master test", ["gov1", "gov2", "del1"], "Test strategy / plan"),
    (r"pipeline|quality gate|\bya?ml\b|jenkins|github actions|azure devops|gitlab|ci/cd", ["gov3", "fut1", "eng3"], "Pipeline configuration"),
    (r"perf|load test|jmeter|\bk6\b|gatling|stress", ["eng4"], "Performance report"),
    (r"accessib|wcag|axe", ["eng4"], "Accessibility report"),
    (r"test data|environment|refresh|virtuali|stub|mock", ["eng5"], "Environment / data"),
    (r"skill|role|training|onboard|competenc", ["tal1", "tal2", "tal3"], "Skills / roles"),
    (r"dashboard|kpi|metric|scorecard", ["del4"], "Quality dashboard"),
    (r"contract|pact|postman|swagger|openapi|api test", ["eng2"], "API test assets"),
    (r"pci|audit|compliance|sox|control", ["gov4"], "Assurance / compliance"),
    (r"monitor|observab|slo|telemetry|synthetic", ["fut4"], "Observability"),
    (r"genai|copilot|llm|ai-assist|self-heal", ["fut2"], "AI in QE"),
    (r"vendor|supplier|sow|sla", ["gov5"], "Partner governance"),
    (r"traceab|requirement|acceptance criteria|user stor", ["eng1"], "Requirements / traceability"),
]

INTENTS = [
    ("followups", r"question|interview|ask |follow.?up"),
    ("evidence", r"evidence|missing|coverage|confiden|thin"),
    ("conflicts", r"conflict|contradict|inconsist|mismatch"),
    ("quickwins", r"quick|90|win|first|start with|priorit"),
    ("strengths", r"strength|strong|good at|best|well"),
    ("gaps", r"gap|weak|low|worst|risk|improv"),
    ("compare", r"compare|versus|\bvs\b|differ|rank"),
    ("summary", r"summar|overview|status|where are we|exec"),
]


def _f(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f}"


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip(" -•\t") for p in parts if len(p.strip()) > 15]


def _keywords(fa: FocusAreaRef) -> list[str]:
    words = re.sub(r"[^a-z\s-]", " ", f"{fa.name} {fa.description}".lower()).split()
    return sorted({w for w in words if len(w) > 4 and w not in STOP})


def _stem_hit(text: str, kw: str) -> bool:
    return kw[: max(5, len(kw) - 2)] in text


class RulesProvider:
    name = "rules"

    # -- levels -------------------------------------------------------------
    def suggest_level(self, notes: str, scale: list[str]) -> LevelSuggestion:
        t = (notes or "").lower()
        if len(t.strip()) < 12:
            return LevelSuggestion(None, [])
        tally: Counter[int] = Counter()
        cues: list[str] = []
        for level, words in LEVEL_CUES:
            for w in words:
                if w in t:
                    tally[level] += 1
                    cues.append(w.strip())
        if not tally:
            return LevelSuggestion(None, [])
        total = sum(tally.values())
        level = round(sum(k * n for k, n in tally.items()) / total)
        return LevelSuggestion(max(1, min(len(scale) or 5, level)), list(dict.fromkeys(cues))[:4])

    # -- interviews ---------------------------------------------------------
    def extract_findings(self, notes, stakeholder, entity, focus_areas, scale) -> list[Finding]:  # noqa: ANN001
        sents = _sentences(notes)
        results = []
        for fa in focus_areas:
            kws = _keywords(fa)
            scored = []
            for s in sents:
                low = s.lower()
                hits = sum(1 for k in kws if _stem_hit(low, k))
                if hits:
                    scored.append((hits, s))
            if not scored:
                continue
            scored.sort(key=lambda x: -x[0])
            best_hits = scored[0][0]
            evidence = " ".join(s for _, s in scored[:2])
            sug = self.suggest_level(evidence, scale)
            conf = "high" if best_hits >= 3 and sug.level else "med" if best_hits >= 2 else "low"
            results.append((best_hits, Finding(
                focus_area_id=fa.id,
                score=sug.level,
                confidence=conf,
                finding=evidence[:400],
                followup="" if conf != "low" and sug.level else fa.question,
            )))
        results.sort(key=lambda x: -x[0])
        return [f for _, f in results[:8]]

    # -- evidence -----------------------------------------------------------
    def classify_evidence(self, filename, text, focus_areas) -> Classification:  # noqa: ANN001
        by_key = {f.key: f for f in focus_areas}
        fname = re.sub(r"[_\-.]+", " ", filename).lower()
        hay = f"{fname} {(text or '')[:6000]}".lower()
        ids: list[int] = []
        # the file name is the strongest signal for what kind of artifact this is
        doc_type = next((label for pattern, _, label in DOC_RULES if re.search(pattern, fname)), "")
        for pattern, keys, label in DOC_RULES:
            if re.search(pattern, hay):
                doc_type = doc_type or label
                ids.extend(by_key[k].id for k in keys if k in by_key)
        if text:
            # generic match on focus-area vocabulary for custom frameworks
            low = text.lower()
            overlap = []
            for fa in focus_areas:
                n = sum(1 for k in _keywords(fa) if _stem_hit(low, k))
                if n >= 2:
                    overlap.append((n, fa.id))
            ids.extend(i for _, i in sorted(overlap, reverse=True)[:3])
        ids = list(dict.fromkeys(ids))[:5]
        signals = []
        for s in _sentences(text or "")[:400]:
            if re.search(r"\d+\s?%|\b\d{2,}\b|no |not |manual|automat|weeks|days", s.lower()):
                signals.append(s[:180])
            if len(signals) >= 4:
                break
        ext = filename.rsplit(".", 1)[-1].upper() if "." in filename else "file"
        if text:
            lines = [ln for ln in (text or "").splitlines() if ln.strip()]
            summary = f"{doc_type or 'Document'} ({ext}, {len(lines)} lines of readable content)."
            if signals:
                summary += f" Notable: {signals[0]}"
        else:
            summary = f"{doc_type or 'Document'} ({ext}). Classified from the file name; open the file to confirm the mapping."
        return Classification(doc_type=doc_type or "Document", summary=summary[:600], focus_area_ids=ids, signals=signals)

    # -- analyst ------------------------------------------------------------
    def analyst(self, req: AnalystRequest) -> str:
        ctx, q = req.context, req.question.lower()
        if not any(f["score"] is not None for f in ctx["focus_areas"]):
            return f"## Nothing scored yet\nNo focus areas have been scored for **{ctx['scope']['name']}**. Start in **Assessment**, or log an interview and apply its findings."
        fa_hit = next((f for f in ctx["focus_areas"] if f["name"].lower() in q or f["name"].split(" ")[0].lower() + " " in q and len(f["name"].split(" ")[0]) > 6), None)
        if fa_hit and not re.search(r"summar|overview", q):
            return self._focus_area(ctx, fa_hit)
        intent = next((name for name, pat in INTENTS if re.search(pat, q)), "summary")
        return getattr(self, f"_{intent}")(ctx)

    def _scored(self, ctx: dict) -> list[dict]:
        return sorted([f for f in ctx["focus_areas"] if f["score"] is not None], key=lambda f: f["score"])

    def _pillars(self, ctx: dict) -> list[dict]:
        return sorted([p for p in ctx["pillars"] if p["score"] is not None], key=lambda p: p["score"])

    def _gaps(self, ctx: dict) -> str:
        p, ranked = self._pillars(ctx), self._scored(ctx)
        lines = [f"## Biggest gaps · {ctx['scope']['name']}",
                 f"The weakest pillar is **{p[0]['name']}** at {_f(p[0]['score'])} / 5 against a target of {p[0]['target']}."]
        lines += [f"- **{f['name']}** ({f['pillar']}) · {_f(f['score'])}: {f['recommendation']}." for f in ranked[:6]]
        lines.append(f"Pattern: gaps cluster in {', '.join(dict.fromkeys(f['pillar'] for f in ranked[:6]))}. "
                     "Fixing the foundational ones first raises the ceiling for automation and AI-enabled QE.")
        return "\n".join(lines)

    def _strengths(self, ctx: dict) -> str:
        ranked = list(reversed(self._scored(ctx)))[:5]
        lines = [f"## Strengths to scale · {ctx['scope']['name']}"]
        for f in ranked:
            best = max((e for e in ctx["entities"] if e["in_scope"] and f["id"] in e["cells"] and e["cells"][f["id"]]["score"] is not None),
                       key=lambda e: e["cells"][f["id"]]["score"], default=None)
            where = f", strongest in **{best['name']}** ({_f(best['cells'][f['id']]['score'])})" if best else ""
            lines.append(f"- **{f['name']}** · {_f(f['score'])}{where}")
        lines.append("Codify these as enterprise patterns and use the strongest teams as reference implementations.")
        return "\n".join(lines)

    def _evidence(self, ctx: dict) -> str:
        eg = ctx["evidence_gaps"]
        by: dict[str, list[dict]] = defaultdict(list)
        for g in eg:
            by[g["entity"]].append(g)
        why = Counter(g["why"] for g in eg)
        total = len(ctx["scope"]["entity_ids"]) * len(ctx["focus_areas"])
        lines = [f"## Evidence still missing · {ctx['scope']['name']}",
                 f"{len(eg)} of {total} assessments are not yet defensible: {why.get('Not yet assessed', 0)} not assessed, "
                 f"{why.get('Low confidence', 0)} low confidence, {why.get('No linked evidence', 0)} with no linked evidence."]
        for ent, items in sorted(by.items(), key=lambda kv: -len(kv[1]))[:6]:
            lines.append(f"- **{ent}** · {len(items)} gaps, e.g. {'; '.join(i['focus_area'] for i in items[:3])}")
        lines.append("Prioritise tool-data access (Jira, CI/CD, test management) to lift confidence across many focus areas in one pass.")
        return "\n".join(lines)

    def _followups(self, ctx: dict) -> str:
        eg = ctx["evidence_gaps"]
        if not eg:
            return "## No open evidence gaps\nEvery focus area in scope has a score with linked evidence."
        counts = Counter(g["entity_id"] for g in eg)
        target_id = counts.most_common(1)[0][0]
        ent = next(e for e in ctx["entities"] if e["id"] == target_id)
        fa_by = {f["id"]: f for f in ctx["focus_areas"]}
        items = [g for g in eg if g["entity_id"] == target_id][:6]
        lines = [f"## Follow-up interview pack · {ent['name']}",
                 f"For {ent['owner'] or 'the entity owner'}{' and the ' + ent['art'] + ' team' if ent['art'] else ''}. Each question targets a focus area where evidence is thin."]
        lines += [f"- **{g['focus_area']}** ({g['why'].lower()}): {fa_by[g['focus_area_id']]['question']}" for g in items]
        lines.append("Ask for artifacts during the session: a recent test summary report, a defect export for the last two releases, and pipeline configuration.")
        return "\n".join(lines)

    def _conflicts(self, ctx: dict) -> str:
        cf = ctx["conflicts"]
        if not cf:
            return "## No conflicting signals\nScores in scope are internally consistent so far."
        lines = [f"## Conflicting signals · {ctx['scope']['name']}",
                 f"{len(cf)} score combination{'s' if len(cf) > 1 else ''} {'don’t' if len(cf) > 1 else 'doesn’t'} sit comfortably together. Test {'each' if len(cf) > 1 else 'it'} in the validation workshop:"]
        lines += [f"- **{c['entity']}:** {c['a']} = {_f(c['a_score'])} but {c['b']} = {_f(c['b_score'])}. {c['message']}" for c in cf[:6]]
        return "\n".join(lines)

    def _quickwins(self, ctx: dict) -> str:
        qw = [f for f in self._scored(ctx) if f["horizon"] == "now"][:5]
        if not qw:
            return "## Quick wins\nNo scored focus areas are tagged for the 0–3 month horizon. Adjust horizons in **Framework**."
        lines = ["## Quick wins for the next 90 days",
                 f"Selected for low effort, high leverage and the size of the current gap in {ctx['scope']['name']}:"]
        lines += [f"- **{f['recommendation']}**, lifting {f['name']} from {_f(f['score'])} toward {f['target']}" for f in qw]
        lines.append("Together these establish the measurement baseline every later roadmap item depends on.")
        return "\n".join(lines)

    def _compare(self, ctx: dict) -> str:
        ents = [e for e in ctx["entities"] if e["in_scope"] and e["overall"] is not None]
        ents.sort(key=lambda e: -e["overall"])
        lines = [f"## Entity comparison · {ctx['scope']['name']}"]
        lines += [f"- **{e['name']}** ({e['type']}) · {_f(e['overall'])}" for e in ents[:12]]
        if len(ents) > 1:
            lines.append(f"Spread of {ents[0]['overall'] - ents[-1]['overall']:.1f} points between strongest and weakest; "
                         f"use **{ents[0]['name']}** practices as the reference for **{ents[-1]['name']}**.")
        return "\n".join(lines)

    def _focus_area(self, ctx: dict, fa: dict) -> str:
        rows = [(e, e["cells"].get(fa["id"])) for e in ctx["entities"] if e["in_scope"]]
        rows = [(e, c) for e, c in rows if c and c["score"] is not None]
        rows.sort(key=lambda x: x[1]["score"])
        lines = [f"## {fa['name']} · {ctx['scope']['name']}",
                 f"Weighted score **{_f(fa['score'])}** against a pillar target of {fa['target']}."]
        lines += [f"- **{e['name']}** · {_f(c['score'])}{' (rolled up)' if c['inherited'] else ''}, {c['confidence'] or '—'} confidence"
                  + (f": {c['notes'][:140]}" if c["notes"] else "") for e, c in rows[:8]]
        lines.append(f"Recommendation: {fa['recommendation']}.")
        return "\n".join(lines)

    def _summary(self, ctx: dict) -> str:
        p, ranked = self._pillars(ctx), self._scored(ctx)
        ov = ctx["overall"]
        level = ctx["scale"][max(1, min(len(ctx["scale"]), round(ov))) - 1] if ov else ""
        return "\n".join([
            f"## Executive summary · {ctx['scope']['name']}",
            f"Provisional maturity is **{_f(ov)} / 5 ({level})**. {p[-1]['name']} is strongest ({_f(p[-1]['score'])}); "
            f"{p[0]['name']} is weakest ({_f(p[0]['score'])}).",
            f"The most material opportunities are {', '.join('**' + f['name'] + '**' for f in ranked[:3])}. "
            f"Evidence coverage is {round(ctx['coverage'] * 100)}%, so findings remain provisional until validated.",
        ])

    # -- report -------------------------------------------------------------
    def executive_summary(self, snapshot: dict, client: str) -> str:
        s = snapshot
        if s.get("overall") is None:
            return "No maturity scores have been captured yet."
        ps = sorted([p for p in s["pillars"] if p["score"] is not None], key=lambda p: -p["score"])
        gaps = ", ".join(g["name"] for g in s["gaps"][:3])
        return (
            f"Across {len(s['entities'])} assessed areas covering {s['apps']} applications, {client}'s provisional "
            f"enterprise QE maturity is {_f(s['overall'])} / 5 ({s['level']}). {ps[0]['name']} leads at {_f(ps[0]['score'])}; "
            f"{ps[-1]['name']} trails at {_f(ps[-1]['score'])}.\n\n"
            f"{s['counts']['gap']} of {s['total']} focus-area assessments indicate a potential gap and {s['counts']['val']} remain "
            f"to be validated. The most material opportunities are {gaps}. Closing these establishes the unified governance "
            f"and measurement baseline needed to scale quality engineering across the portfolio. Findings are provisional "
            f"until validated with stakeholders."
        )
