import { Link, useNavigate } from "react-router-dom";
import { Page } from "../components/Layout";
import { ActIcon, EType, Loading, NoScope } from "../components/ui";
import { PHASES, ago, cap, fmt, phaseAt, pillarColor, weekOf } from "../lib/format";
import { useActivity, useDirectory, useEid, useEvidence, useInterviews, useModel, useSnapshots, useWorkspace, type Model } from "../lib/workspace";
import type { Entity, Workspace } from "../types";

export function Overview() {
  const eid = useEid();
  const ws = useWorkspace(eid);
  const m = useModel(ws.data);
  const ivs = useInterviews(eid).data || [];
  const evs = useEvidence(eid).data || [];
  const snaps = useSnapshots(eid).data || [];
  const acts = useActivity(eid).data || [];
  const names = useDirectory();
  if (!ws.data) return <Page title="Command Center" eid={eid}><Loading /></Page>;
  const w = ws.data;
  const a = w.analytics;
  const eng = w.engagement;
  const wk = weekOf(eng.start_date, eng.weeks);
  const done = ivs.filter((i) => i.status === "completed").length;
  const apps = m.topLevel.reduce((s, e) => s + (e.apps || 0), 0);
  const typeCount = (t: string) => m.entities.filter((e) => e.type === t).length;
  const scopeTxt = [["lob", "LOB"], ["program", "program"], ["app", "app"]].map(([t, l]) => { const n = typeCount(t); return n ? `${n} ${l}${n > 1 ? "s" : ""}` : ""; }).filter(Boolean).join(" · ");
  const last = snaps[snaps.length - 1];
  const ov = a.enterprise.overall;

  const insights: [string, string, string][] = [];
  const r0 = a.ranked[0], r1 = a.ranked[1];
  if (r0) insights.push(["--gap", `Largest enterprise gap: ${m.faById.get(r0.focus_area_id)?.name}`, `Weighted maturity ${fmt(r0.score)} / 5.${r1 ? ` Next: ${m.faById.get(r1.focus_area_id)?.name} (${fmt(r1.score)}).` : ""}`]);
  if (a.conflicts[0]) insights.push(["--partial", `Conflicting signal in ${m.entById.get(a.conflicts[0].entity_id)?.name}`, a.conflicts[0].message]);
  if (a.evidence_gaps.length) {
    const by = new Map<number, number>();
    a.evidence_gaps.forEach((g) => by.set(g.entity_id, (by.get(g.entity_id) || 0) + 1));
    const [top, n] = [...by.entries()].sort((x, y) => y[1] - x[1])[0];
    insights.push(["--val", `${a.evidence_gaps.length} evidence gaps to close`, `Most in ${m.entById.get(top)?.name} (${n}). The AI Analyst can draft follow-up interview questions.`]);
  }

  const kpis: [string, string | number, string, string, number | null][] = [
    ["Entities in scope", m.entities.length, "", `${scopeTxt || "none yet"} · ${apps} apps`, null],
    ["Interviews", done, ` / ${eng.interviews_planned}`, `${ivs.length - done} scheduled`, done / eng.interviews_planned],
    ["Evidence items", evs.length, "", "Artifacts in the library", null],
    ["Evidence coverage", Math.round(a.enterprise.coverage * 100), "%", "Scored with medium+ confidence", a.enterprise.coverage],
    ["Enterprise maturity", fmt(ov), " / 5", ov != null ? `${a.enterprise.level} · live` : "No scores yet", (ov || 0) / 5],
    ["Published", last ? `v${last.version}` : "—", "", last ? `${ago(last.created_at)} · ${fmt(last.overall)}` : "No dashboard yet", null],
  ];

  return (
    <Page title="Command Center" sub="Live engagement status, maturity and recent activity" eid={eid}>
      <section className="hero">
        <svg className="waves" viewBox="0 0 1200 44" preserveAspectRatio="none" aria-hidden="true"><path d="M0 24 Q 75 4 150 24 T 300 24 T 450 24 T 600 24 T 750 24 T 900 24 T 1050 24 T 1200 24 V44 H0Z" fill="#fff" /></svg>
        <div>
          <div className="eyebrow" style={{ color: "#7fb7d8" }}>{eng.client} · {eng.title}</div>
          <h2>One live workspace for the whole assessment</h2>
          <p>Interviews, artifacts and scores go in here as the team works. Maturity, gaps and the report update instantly, and every published dashboard is versioned.</p>
        </div>
        <div className="score"><div className="n mono">{fmt(ov)}</div><div className="l">Live enterprise<br />maturity (of 5)</div></div>
      </section>

      <section className="card pad">
        <div className="sec-h"><div><h2>Engagement timeline</h2><p>Week {wk} of {eng.weeks} · {phaseAt(wk)}</p></div><Link className="btn sm" to={`/e/${eid}/scope`}>Edit engagement</Link></div>
        <div className="tl-wrap">
          <div className="tl" style={{ gridTemplateColumns: `repeat(${eng.weeks},minmax(0,1fr))` }}>
            {Array.from({ length: eng.weeks }, (_, i) => <div key={`w${i}`} className="wk">W{i + 1}{i + 1 === wk ? " ▾" : ""}</div>)}
            {PHASES.filter((p) => p[0] <= eng.weeks).map(([s, n, t, d]) => (
              <div key={t} className={`ph ${s + n - 1 < wk ? "done" : s <= wk ? "now" : ""}`} style={{ gridColumn: `${s}/span ${Math.min(n, eng.weeks - s + 1)}` }}>{t}<small>{d}</small></div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid g-kpi">
        {kpis.map(([l, v, u, d, mt]) => (
          <div key={l} className="card kpi">
            <div className="eyebrow">{l}</div><div className="v">{v}<small>{u}</small></div><div className="d">{d}</div>
            {mt != null && <div className="meter"><i style={{ width: `${Math.min(100, Math.round(mt * 100))}%` }} /></div>}
          </div>
        ))}
      </section>

      <section className="grid g-2">
        <div className="card pad">
          <div className="sec-h"><div><h2>Maturity by pillar</h2><p>{w.settings.weighting === "apps" ? "Weighted by application count" : "Equal entity weighting"} · ▏ marks target</p></div></div>
          {m.pillars.map((p, pi) => {
            const v = a.enterprise.pillars[pi];
            return (
              <div key={p.id} className="pbar">
                <div className="nm"><span className="dot" style={{ background: pillarColor(p.color) }} /><span>{p.short}</span></div>
                <div className="track"><div className="fill" style={{ width: `${((v || 0) / 5) * 100}%`, background: pillarColor(p.color) }} /><div className="tgt" style={{ left: `${(p.target / 5) * 100}%` }} title={`Target ${p.target}`} /></div>
                <div className="mono" style={{ textAlign: "right", fontWeight: 500 }}>{fmt(v)}</div>
              </div>
            );
          })}
          <div className="scale"><div /><div>{[0, 1, 2, 3, 4, 5].map((n) => <span key={n}>{n}</span>)}</div><div /></div>
          {insights.length > 0 && (
            <div className="ins" style={{ marginTop: 16 }}>
              {insights.map(([c, t, d]) => <div key={t} className="it"><i className="sev" style={{ background: `var(${c})` }} /><div><b>{t}</b><span>{d}</span></div></div>)}
            </div>
          )}
        </div>
        <div className="card pad">
          <div className="sec-h"><div><h2>Activity</h2><p>Every change to the assessment, as it happens</p></div></div>
          {acts.length ? (
            <div className="feed">
              {acts.slice(0, 9).map((x) => (
                <div key={x.id} className="it"><ActIcon kind={x.kind} /><div>{cap(x.text)}<time>{ago(x.created_at)}{x.user_id && names.get(x.user_id) ? ` · ${names.get(x.user_id)}` : ""}</time></div></div>
              ))}
            </div>
          ) : <p className="muted small">Changes to scope, interviews, evidence and scores appear here.</p>}
        </div>
      </section>

      <section>
        <div className="sec-h"><div><h2>Assessment scope</h2><p>Lines of business with their programs and applications. Open any entity to score it.</p></div><Link className="btn sm" to={`/e/${eid}/scope`}>+ Add entity</Link></div>
        {m.entities.length ? <div className="grid g-lob">{m.topLevel.map((e) => <EntityCard key={e.id} e={e} m={m} w={w} eid={eid} />)}</div> : <NoScope eid={eid} />}
      </section>
    </Page>
  );
}

function EntityCard({ e, m, w, eid }: { e: Entity; m: Model; w: Workspace; eid: number }) {
  const nav = useNavigate();
  const ea = w.analytics.entities[e.id];
  const kids = m.descendants(e.id).map((id) => m.entById.get(id)!).filter(Boolean);
  const open = (id: number) => nav(`/e/${eid}/assessment?entity=${id}`);
  return (
    <div className="card lob" role="button" tabIndex={0} onClick={() => open(e.id)} onKeyDown={(k) => (k.key === "Enter" || k.key === " ") && (k.preventDefault(), open(e.id))} aria-label={`Assess ${e.name}`}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "flex-start" }}><h3>{e.name}</h3><span className={`crit ${e.criticality === "High" ? "high" : ""}`}>{e.criticality}</span></div>
      <div className="meta"><EType e={e} /><span>{e.apps} apps</span><span>{e.art}</span></div>
      <div className="mini">{m.pillars.map((p, i) => { const v = ea?.pillars[i]; return <i key={p.id} style={{ height: `${v ? (v / 5) * 100 : 6}%`, background: v ? pillarColor(p.color) : "var(--hval)" }} title={`${p.short}: ${fmt(v)}`} />; })}</div>
      <div className="mini-l">{m.pillars.map((p, i) => <span key={p.id}>{fmt(ea?.pillars[i])}</span>)}</div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--ink2)" }}>
        <span>Maturity <b className="mono" style={{ color: "var(--ink)" }}>{fmt(ea?.overall)}</b></span>
        <span>Coverage <b className="mono" style={{ color: "var(--ink)" }}>{Math.round((ea?.coverage || 0) * 100)}%</b></span>
      </div>
      <div className="meter"><i style={{ width: `${Math.round((ea?.coverage || 0) * 100)}%` }} /></div>
      {kids.length > 0 && (
        <div className="kidlist">
          {kids.slice(0, 4).map((c) => (
            <button key={c.id} className="kid" onClick={(ev) => { ev.stopPropagation(); open(c.id); }}>
              <EType e={c} /><span>{c.name}</span><b className="mono">{fmt(w.analytics.entities[c.id]?.overall)}</b>
            </button>
          ))}
          {kids.length > 4 && <span className="small muted">+{kids.length - 4} more</span>}
        </div>
      )}
    </div>
  );
}
