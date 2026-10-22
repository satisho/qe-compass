import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Page } from "../components/Layout";
import { Icons } from "../components/icons";
import { Drawer, EType, HeatCell, Loading, NoScope, StatusPill } from "../components/ui";
import { CONF, STATUS_DESC, STATUS_LABEL, ago, fmt, pillarColor } from "../lib/format";
import { useEid, useEvidence, useInterviews, useModel, useWorkspace } from "../lib/workspace";
import type { Status } from "../types";

export function Heatmap() {
  const eid = useEid();
  const ws = useWorkspace(eid);
  const m = useModel(ws.data);
  const [mode, setMode] = useState<"fa" | "pillar">("fa");
  const [cell, setCell] = useState<[number, number] | null>(null);
  if (!ws.data) return <Page title="Maturity Map" eid={eid}><Loading /></Page>;
  if (!m.entities.length) return <Page title="Maturity Map" eid={eid}><NoScope eid={eid} /></Page>;
  const a = ws.data.analytics;
  const wide = mode === "pillar";
  const rowHead = (id: number, depth: number) => {
    const e = m.entById.get(id)!;
    return <td className="rowh" style={{ paddingLeft: 2 + depth * 16 }}>{depth ? <span className="muted">↳ </span> : null}{e.name} <EType e={e} /></td>;
  };

  return (
    <Page title="Maturity Map" sub="Current-state maturity by entity and focus area" eid={eid}>
      <section className="card pad">
        <div className="sec-h"><div><h2>Current-state maturity map</h2><p>Live from the Assessment workspace</p></div>
          <div className="toggle" role="group" aria-label="Granularity">
            <button aria-pressed={!wide} onClick={() => setMode("fa")}>Focus areas</button>
            <button aria-pressed={wide} onClick={() => setMode("pillar")}>Pillars</button>
          </div></div>
        <div className="hm-wrap">
          <table className={`hm ${wide ? "wide" : ""}`}>
            <thead>
              {!wide && <tr><th />{m.pillars.map((p) => <th key={p.id} className="pg" colSpan={p.focus_areas.length} style={{ background: pillarColor(p.color) }}>{p.short}</th>)}<th /></tr>}
              <tr><th />
                {wide ? m.pillars.map((p) => <th key={p.id} className="pg" style={{ background: pillarColor(p.color) }}>{p.short}</th>)
                  : m.fas.map((f) => <th key={f.id} className="rot" title={f.name}><div>{f.name}</div></th>)}
                <th style={{ verticalAlign: "bottom", textAlign: "center" }}>Overall</th></tr>
            </thead>
            <tbody>
              {m.tree.map(({ e, depth }) => {
                const ea = a.entities[e.id];
                return (
                  <tr key={e.id}>{rowHead(e.id, depth)}
                    {wide ? m.pillars.map((p, pi) => <td key={p.id}><HeatCell s={ea?.pillars[pi]} /></td>)
                      : m.fas.map((f) => { const c = ea?.cells[f.id]; return (
                        <td key={f.id}><HeatCell s={c?.score} low={c?.confidence === "low"} inh={c?.inherited} onClick={() => setCell([e.id, f.id])}
                          label={`${e.name}, ${f.name}: ${c?.score == null ? "not assessed" : fmt(c.score)}${c?.inherited ? " (rolled up)" : ""}`} /></td>); })}
                    <td><HeatCell s={ea?.overall} style={wide ? undefined : { width: 46 }} /></td>
                  </tr>
                );
              })}
              <tr><td className="rowh muted">Enterprise roll-up</td>
                {wide ? a.enterprise.pillars.map((v, i) => <td key={i}><HeatCell s={v} /></td>)
                  : m.fas.map((f) => <td key={f.id}><HeatCell s={a.enterprise.cells[f.id]} style={{ fontSize: 10.5 }} /></td>)}
                <td><HeatCell s={a.enterprise.overall} style={wide ? undefined : { width: 46 }} /></td></tr>
            </tbody>
          </table>
        </div>
        <div className="legend" style={{ marginTop: 14 }}>
          {[1, 2, 3, 4, 5].map((n) => <span key={n} className="sw"><i className={`c${n}`} />{n} {m.level(n)}</span>)}
          <span className="sw"><i className="cnull" />Not assessed</span>
          {!wide && <><span className="sw">● = low confidence</span><span className="sw"><i className="c3 inh" />rolled up from child entities</span></>}
        </div>
        {!wide && <p className="small muted" style={{ margin: "10px 0 0" }}>Select any cell to see the evidence behind it. Summary counts and the enterprise row use top-level entities.</p>}
      </section>
      <section className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))" }}>
        {(Object.keys(STATUS_LABEL) as Status[]).map((k) => (
          <div key={k} className="card kpi"><StatusPill status={k} /><div className="v">{a.enterprise.counts[k]}<small> / {a.enterprise.total}</small></div><div className="d">{STATUS_DESC[k]}</div></div>
        ))}
      </section>
      {cell && <CellDrawer eid={eid} entityId={cell[0]} faId={cell[1]} onClose={() => setCell(null)} />}
    </Page>
  );
}

function CellDrawer({ eid, entityId, faId, onClose }: { eid: number; entityId: number; faId: number; onClose: () => void }) {
  const ws = useWorkspace(eid);
  const m = useModel(ws.data);
  const ivs = useInterviews(eid).data || [];
  const evs = useEvidence(eid).data || [];
  const nav = useNavigate();
  const e = m.entById.get(entityId), fa = m.faById.get(faId);
  if (!e || !fa || !ws.data) return null;
  const c = m.cell(entityId, faId);
  const a = m.assessment(entityId, faId);
  const ids = new Set([entityId, ...m.descendants(entityId)]);
  const li = ivs.filter((i) => i.status === "completed" && i.entity_id != null && ids.has(i.entity_id) && i.focus_area_ids.includes(faId));
  const ld = evs.filter((d) => d.entity_id != null && ids.has(d.entity_id) && d.focus_area_ids.includes(faId));
  return (
    <Drawer title={fa.name} sub={`${m.pillars[fa.pi].name} · ${m.path(entityId)}`} onClose={onClose}
      footer={<button className="btn primary" onClick={() => nav(`/e/${eid}/assessment?entity=${entityId}`)}>Edit in Assessment</button>}>
      <div className="row" style={{ gap: 14 }}>
        <HeatCell s={c?.score} style={{ width: 54, height: 54, fontSize: 20 }} />
        <div><b>{m.level(c?.score)}</b><div><StatusPill status={c?.status || "val"} /></div></div>
      </div>
      {c?.score != null && <p className="small muted" style={{ margin: 0 }}>{ws.data.settings.scale[Math.round(c.score) - 1]?.description}</p>}
      <dl className="kv">
        <dt>Confidence</dt><dd>{c?.confidence ? CONF[c.confidence] : "—"}{a?.confidence ? " (override)" : " (auto)"}</dd>
        <dt>Enterprise avg</dt><dd className="mono">{fmt(ws.data.analytics.enterprise.cells[faId])}</dd>
        {a?.updated_at && <><dt>Last updated</dt><dd>{ago(a.updated_at)}</dd></>}
        {c?.inherited && <><dt>Source</dt><dd>Rolled up from {m.children(entityId).map((k) => k.name).join(", ")}</dd></>}
      </dl>
      <div><div className="eyebrow">Notes</div><p style={{ margin: "4px 0 0", whiteSpace: "pre-wrap" }}>{a?.notes || <span className="muted">No notes yet.</span>}</p></div>
      <div><div className="eyebrow">Linked evidence</div>
        <div className="links" style={{ marginTop: 6 }}>
          {li.map((i) => <span key={`i${i.id}`} className="lk">{Icons.talk}<span>{i.stakeholder}</span></span>)}
          {ld.map((d) => <span key={`d${d.id}`} className="lk">{Icons.doc}<span>{d.name}</span></span>)}
          {!li.length && !ld.length && <span className="small muted">None</span>}
        </div></div>
      <div className="ai-sug"><span><b>Recommendation:</b> {fa.recommendation}.</span></div>
    </Drawer>
  );
}
