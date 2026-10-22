import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, download } from "../api";
import { Page } from "../components/Layout";
import { Drawer, Loading, Markdown, NoScope, Radar, StatusPill, Trend } from "../components/ui";
import { useAuth } from "../lib/auth";
import { HORIZON, fdatetime, fmt, pillarColor, weekOf } from "../lib/format";
import { base, useDirectory, useEid, useModel, useMut, useSnapshots, useWorkspace } from "../lib/workspace";
import type { Snapshot, SnapshotData, Status } from "../types";

export function Dashboards() {
  const eid = useEid();
  const ws = useWorkspace(eid);
  const m = useModel(ws.data);
  const snaps = useSnapshots(eid);
  const names = useDirectory();
  const { canWrite } = useAuth();
  const [sel, setSel] = useState<number | "live">("live");
  const [pub, setPub] = useState<{ note: string; narrative: string } | null>(null);
  const live = useQuery({ queryKey: ["live", eid, ws.dataUpdatedAt], queryFn: () => api.get<{ data: SnapshotData; narrative: string }>(`${base(eid)}/report/live`), enabled: sel === "live" });
  const snap = useQuery({ queryKey: ["snapshot", eid, sel], queryFn: () => api.get<Snapshot>(`${base(eid)}/snapshots/${sel}`), enabled: sel !== "live" });
  const publish = useMut(eid, (b: { note: string; narrative: string }) => api.post<Snapshot>(`${base(eid)}/snapshots`, b), {
    also: ["snapshots"], success: (r) => `Dashboard v${r.version} published`, onSuccess: (r) => { setPub(null); setSel(r.id); },
  });

  if (!ws.data || !snaps.data) return <Page title="Dashboards" eid={eid}><Loading /></Page>;
  if (!m.entities.length) return <Page title="Dashboards" eid={eid}><NoScope eid={eid} /></Page>;
  const eng = ws.data.engagement;
  const list = snaps.data;
  const s = sel === "live" ? live.data?.data : snap.data?.data;
  const narrative = sel === "live" ? live.data?.narrative : snap.data?.narrative;
  const trend = [...list.map((x) => ({ label: `v${x.version}`, value: x.overall })), { label: "Live", value: ws.data.analytics.enterprise.overall, live: true }];

  return (
    <Page title="Dashboards" sub="Publish versioned dashboards and the assessment report" eid={eid}
      actions={<button className="btn sm no-print" onClick={() => window.print()}>Print / save as PDF</button>}>
      <section className="card pad no-print">
        <div className="sec-h">
          <div><h2>Dashboard versions</h2><p>Publish a snapshot whenever findings are ready to share. Earlier versions stay intact for comparison.</p></div>
          <div className="row">
            <button className="btn sm" onClick={() => download(`${base(eid)}/export.csv`)}>Export CSV</button>
            {canWrite && <button className="btn primary" onClick={() => setPub({ note: `Week ${weekOf(eng.start_date, eng.weeks)} readout`, narrative: live.data?.narrative || "" })}>Publish dashboard</button>}
          </div>
        </div>
        <div className="grid g-2" style={{ alignItems: "center" }}>
          <div className="vers" role="group" aria-label="Version">
            <button aria-pressed={sel === "live"} onClick={() => setSel("live")}>Live draft<small>Updates as the team works</small></button>
            {[...list].reverse().map((x) => (
              <button key={x.id} aria-pressed={sel === x.id} onClick={() => setSel(x.id)}>v{x.version} · {fmt(x.overall)}<small>{x.note} · {new Date(x.created_at).toLocaleDateString("en-CA", { month: "short", day: "numeric" })}</small></button>
            ))}
          </div>
          <div><Trend points={trend} /></div>
        </div>
      </section>

      {!s ? <Loading what="Preparing the report…" /> : (
        <article className="card report">
          <header className="rep-head">
            <div>
              <div className="eyebrow">{eng.client} · {eng.title}</div>
              <h2>Current-State QE Assessment</h2>
              <div className="small muted" style={{ marginTop: 4 }}>
                {sel === "live" ? `Live draft · ${new Date().toLocaleDateString("en-CA", { dateStyle: "medium" })}`
                  : `Published v${snap.data!.version}${snap.data!.created_by && names.get(snap.data!.created_by) ? ` by ${names.get(snap.data!.created_by)}` : ""} · ${fdatetime(snap.data!.created_at)}`}
                {" "}· {s.interviews} interviews, {s.evidence} artifacts
              </div>
            </div>
            {sel === "live" ? <span className="badge">Draft</span> : <span className="badge ok">Published</span>}
          </header>
          <div className="rep-body">
            <section><h3><span className="n">01</span>Executive summary</h3><div className="exec"><Markdown text={narrative || ""} /></div></section>
            <section className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))" }}>
              <div className="kpi" style={{ padding: 0 }}><div className="eyebrow">Enterprise maturity</div><div className="v">{fmt(s.overall)}<small> / 5</small></div><div className="d">{s.level}</div></div>
              <div className="kpi" style={{ padding: 0 }}><div className="eyebrow">Evidence coverage</div><div className="v">{Math.round(s.coverage * 100)}<small>%</small></div><div className="d">medium+ confidence</div></div>
              <div className="kpi" style={{ padding: 0 }}><div className="eyebrow">Potential gaps</div><div className="v" style={{ color: "var(--gap)" }}>{s.counts.gap}<small> / {s.total}</small></div><div className="d">focus-area assessments</div></div>
              <div className="kpi" style={{ padding: 0 }}><div className="eyebrow">To validate</div><div className="v" style={{ color: "var(--val)" }}>{s.counts.val}</div><div className="d">{s.evidence_gaps} evidence gaps open</div></div>
            </section>
            <section className="rep-split">
              <div style={{ textAlign: "center" }}><Radar pillars={s.pillars} /></div>
              <div><h3><span className="n">02</span>Pillar maturity by top-level entity</h3>
                <div className="tbl-wrap"><table>
                  <thead><tr><th>Pillar</th>{s.entities.map((e) => <th key={e.name} className="num" title={e.name}>{e.name.split(/[ &]/)[0]}</th>)}<th className="num">Ent.</th><th className="num">Target</th></tr></thead>
                  <tbody>{s.pillars.map((p, pi) => (
                    <tr key={p.name}><td style={{ whiteSpace: "nowrap" }}><span className="dot" style={{ background: pillarColor(p.color) }} /> {p.short}</td>
                      {s.entities.map((e) => <td key={e.name} className="num">{fmt(e.pillars[pi])}</td>)}
                      <td className="num"><b>{fmt(p.score)}</b></td><td className="num muted">{p.target.toFixed(1)}</td></tr>
                  ))}</tbody>
                </table></div></div>
            </section>
            <section><h3><span className="n">03</span>Priority gaps</h3>
              <div className="tbl-wrap"><table>
                <thead><tr><th>Focus area</th><th>Pillar</th><th className="num">Score</th><th>Status</th><th>Recommendation</th></tr></thead>
                <tbody>{s.gaps.map((g) => (
                  <tr key={g.name}><td><b>{g.name}</b></td><td>{g.pillar}</td><td className="num">{fmt(g.score)}</td>
                    <td><StatusPill status={(g.status || (g.score <= ws.data!.settings.thresholds.gap ? "gap" : "partial")) as Status} /></td><td>{g.rec}</td></tr>
                ))}</tbody>
              </table></div></section>
            <section><h3><span className="n">04</span>Strengths to scale</h3>
              <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
                {s.strengths.map((x) => <li key={x.name}><b>{x.name}</b> ({fmt(x.score)}){x.best ? `, strongest in ${x.best}` : ""}. Codify as an enterprise pattern.</li>)}
              </ul></section>
            <section><h3><span className="n">05</span>Transformation roadmap</h3>
              <div className="road">{(["now", "next", "later"] as const).map((k) => (
                <div key={k} className="col"><h4>{HORIZON[k][0]}</h4><div className="w">{HORIZON[k][1]}</div>
                  <ol>{(s.roadmap[k] || []).length ? s.roadmap[k].map((x) => <li key={x.name}>{x.rec}<small>{x.name} · {fmt(x.score)} → {x.target.toFixed(1)}</small></li>) : <li className="muted">Nothing scored yet</li>}</ol>
                </div>))}</div></section>
            <section><h3><span className="n">06</span>Next steps</h3>
              <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
                <li>Close {s.evidence_gaps} evidence gaps through follow-up interviews and tool-data access.</li>
                <li>Validate {s.conflicts} conflicting signal{s.conflicts === 1 ? "" : "s"} with entity owners in the findings workshop.</li>
                <li>Co-create the target operating model and confirm roadmap sequencing with executive sponsors.</li>
              </ul></section>
          </div>
        </article>
      )}

      {pub && (
        <Drawer wide title="Publish dashboard" sub={`Creates v${(list[list.length - 1]?.version || 0) + 1}. Everyone with access sees it under Dashboards.`} onClose={() => setPub(null)}
          footer={<><button className="btn" onClick={() => setPub(null)}>Cancel</button><button className="btn primary" disabled={publish.isPending} onClick={() => publish.mutate(pub)}>Publish v{(list[list.length - 1]?.version || 0) + 1}</button></>}>
          <div className="field"><label htmlFor="pb-note">Version note</label><input className="inp" id="pb-note" autoFocus value={pub.note} onChange={(e) => setPub({ ...pub, note: e.target.value })} /></div>
          <div className="field"><label htmlFor="pb-narr">Executive summary</label>
            <textarea className="inp" id="pb-narr" rows={10} value={pub.narrative} onChange={(e) => setPub({ ...pub, narrative: e.target.value })} />
            <span className="small muted">Drafted by the analysis engine from the live scores. Edit it before publishing; leave it empty to use the generated draft.</span></div>
          <dl className="kv">
            <dt>Enterprise</dt><dd className="mono">{fmt(ws.data.analytics.enterprise.overall)} / 5{list.length ? ` (v${list[list.length - 1].version}: ${fmt(list[list.length - 1].overall)})` : ""}</dd>
            <dt>Coverage</dt><dd className="mono">{Math.round(ws.data.analytics.enterprise.coverage * 100)}%</dd>
          </dl>
        </Drawer>
      )}
    </Page>
  );
}
