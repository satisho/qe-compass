import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, download } from "../api";
import { Page } from "../components/Layout";
import { EngagementTeam } from "../components/Team";
import { ConfirmButton, Drawer, EType, EntitySelect, Loading } from "../components/ui";
import { useAuth } from "../lib/auth";
import { ETYPE, fmt } from "../lib/format";
import { base, useEid, useMut, useModel, useWorkspace, type Model } from "../lib/workspace";
import type { Engagement, Entity, EntityType } from "../types";

type EntityForm = { name: string; type: EntityType; parent_id: number | null; apps: number; art: string; owner: string; criticality: Entity["criticality"] };
const blank = (type: EntityType = "lob", parent_id: number | null = null): EntityForm =>
  ({ name: "", type, parent_id, apps: type === "app" ? 1 : type === "program" ? 4 : 8, art: "", owner: "", criticality: "Medium" });

export function Scope() {
  const eid = useEid();
  const ws = useWorkspace(eid);
  const m = useModel(ws.data);
  const { canWrite, isAdmin } = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();
  const [meta, setMeta] = useState<Partial<Engagement>>({});
  const [nf, setNf] = useState<EntityForm>(blank());
  const [edit, setEdit] = useState<(EntityForm & { id: number }) | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => { if (ws.data) setMeta(ws.data.engagement); }, [ws.data?.engagement]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveMeta = useMut(eid, () => api.patch(`${base(eid)}`, {
    client: meta.client, title: meta.title, start_date: meta.start_date, weeks: meta.weeks, interviews_planned: meta.interviews_planned,
  }), { success: "Engagement saved", onSuccess: () => qc.invalidateQueries({ queryKey: ["engagements"] }) });
  const addEnt = useMut(eid, (f: EntityForm) => api.post<Entity>(`${base(eid)}/entities`, f), {
    success: (e) => `${e.name} added to scope`, onSuccess: () => setNf(blank()),
  });
  const updEnt = useMut(eid, ({ id, ...f }: EntityForm & { id: number }) =>
    api.patch(`${base(eid)}/entities/${id}`, { ...f, clear_parent: f.parent_id == null }), { success: "Entity updated", onSuccess: () => setEdit(null) });
  const delEnt = useMut(eid, (id: number) => api.del(`${base(eid)}/entities/${id}`), { success: "Removed from scope", onSuccess: () => setEdit(null) });
  const delEng = useMut(eid, () => api.del(`${base(eid)}`), {
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["engagements"] }); nav("/"); },
  });

  if (!ws.data) return <Page title="Scope & Entities" eid={eid}><Loading /></Page>;
  const a = ws.data.analytics;
  const counts = (["lob", "program", "app"] as EntityType[]).map((t) => [t, m.entities.filter((e) => e.type === t).length] as const);

  const addChild = (p: Entity) => {
    setNf(blank(p.type === "lob" ? "program" : "app", p.id));
    setTimeout(() => { nameRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); nameRef.current?.focus(); }, 50);
  };
  const submitNew = (e: FormEvent) => { e.preventDefault(); addEnt.mutate(nf); };

  return (
    <Page title="Scope & Entities" sub="Engagement details, lines of business, programs and applications" eid={eid}>
      <section className="card pad">
        <div className="sec-h"><div><h2>Engagement</h2><p>Drives the timeline and interview targets across the workspace</p></div></div>
        <form className="fgrid" onSubmit={(e) => { e.preventDefault(); saveMeta.mutate(undefined); }}>
          <div className="field"><label htmlFor="m-client">Client</label><input className="inp" id="m-client" disabled={!canWrite} value={meta.client || ""} onChange={(e) => setMeta({ ...meta, client: e.target.value })} /></div>
          <div className="field"><label htmlFor="m-title">Engagement</label><input className="inp" id="m-title" disabled={!canWrite} value={meta.title || ""} onChange={(e) => setMeta({ ...meta, title: e.target.value })} /></div>
          <div className="field"><label htmlFor="m-start">Start date (week 1)</label><input className="inp" type="date" id="m-start" disabled={!canWrite} value={meta.start_date || ""} onChange={(e) => setMeta({ ...meta, start_date: e.target.value })} /></div>
          <div className="field"><label htmlFor="m-weeks">Duration (weeks)</label><input className="inp" type="number" min={1} max={52} id="m-weeks" disabled={!canWrite} value={meta.weeks || 8} onChange={(e) => setMeta({ ...meta, weeks: Number(e.target.value) })} /></div>
          <div className="field"><label htmlFor="m-ivp">Interviews planned</label><input className="inp" type="number" min={1} id="m-ivp" disabled={!canWrite} value={meta.interviews_planned || 1} onChange={(e) => setMeta({ ...meta, interviews_planned: Number(e.target.value) })} /></div>
          <div className="field" style={{ justifyContent: "flex-end" }}><button className="btn primary" type="submit" disabled={!canWrite || saveMeta.isPending}>Save engagement</button></div>
        </form>
      </section>
      <EngagementTeam eid={eid} />

      <section className="card pad">
        <div className="sec-h">
          <div><h2>Assessment scope</h2><p>Every entity is assessed against all {m.fas.length} focus areas. Programs and applications roll up into their parent; top-level entities roll up to the enterprise.</p></div>
          <span className="chip">{counts.filter(([, n]) => n).map(([t, n]) => `${n} ${t === "lob" ? "LOB" : t}${n > 1 ? "s" : ""}`).join(" · ") || "None yet"}</span>
        </div>
        {m.tree.length ? (
          <div className="tbl-wrap"><table>
            <thead><tr><th>Entity</th><th>Type</th><th>ART / programme</th><th>Owner / SPOC (role)</th><th className="num">Apps</th><th>Criticality</th><th className="num">Coverage</th><th className="num">Maturity</th><th /></tr></thead>
            <tbody>
              {m.tree.map(({ e, depth }) => (
                <tr key={e.id}>
                  <td style={{ paddingLeft: 10 + depth * 22 }}><b>{depth ? <span className="muted">↳ </span> : null}{e.name}</b></td>
                  <td><EType e={e} /></td><td>{e.art}</td><td>{e.owner}</td><td className="num">{e.apps}</td>
                  <td><span className={`crit ${e.criticality === "High" ? "high" : ""}`}>{e.criticality}</span></td>
                  <td className="num">{Math.round((a.entities[e.id]?.coverage || 0) * 100)}%</td>
                  <td className="num">{fmt(a.entities[e.id]?.overall)}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {canWrite && <button className="btn sm" onClick={() => setEdit({ ...e, id: e.id })}>Edit</button>}{" "}
                    <Link className="btn sm" to={`/e/${eid}/assessment?entity=${e.id}`}>Assess</Link>{" "}
                    {canWrite && e.type !== "app" && <button className="btn sm" onClick={() => addChild(e)} title={`Add a program or application under ${e.name}`}>+ Child</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        ) : <p className="muted">Nothing in scope yet. Add the first entity below.</p>}
      </section>

      {canWrite && (
        <section className="card pad">
          <div className="sec-h"><div><h2>Add an entity</h2><p>A line of business, a program or a single application. New entities start with every focus area “to be validated”.</p></div></div>
          <EntityFields m={m} f={nf} set={setNf} prefix="nl" nameRef={nameRef} />
          <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
            <button className="btn primary" onClick={submitNew} disabled={!nf.name.trim() || addEnt.isPending}>Add entity</button>
          </div>
        </section>
      )}

      <section className="card pad">
        <div className="sec-h"><div><h2>Data</h2><p>Exports include every score, interview, artifact record and published dashboard</p></div></div>
        <div className="row">
          <button className="btn" onClick={() => download(`${base(eid)}/export.csv`)}>Export scores (CSV)</button>
          <button className="btn" onClick={() => download(`${base(eid)}/export.json`)}>Export engagement (JSON)</button>
          {isAdmin && <ConfirmButton label="Delete engagement" confirm="Yes, delete everything" onConfirm={() => delEng.mutate(undefined)} />}
        </div>
        <p className="small muted" style={{ marginBottom: 0 }}>A JSON export can be imported into another QE Compass installation from the Engagements page. Uploaded files stay in this installation’s data folder.</p>
      </section>

      {edit && (
        <Drawer title="Edit entity" onClose={() => setEdit(null)} footer={<>
          <span style={{ marginRight: "auto" }}><ConfirmButton label="Remove from scope" confirm="Yes, remove" onConfirm={() => delEnt.mutate(edit.id)} /></span>
          <button className="btn" onClick={() => setEdit(null)}>Cancel</button>
          <button className="btn primary" disabled={!edit.name.trim() || updEnt.isPending} onClick={() => updEnt.mutate(edit)}>Save</button>
        </>}>
          <EntityFields m={m} f={edit} set={(f) => setEdit({ ...f, id: edit.id })} prefix="el" exclude={[edit.id, ...m.descendants(edit.id)]} />
          <p className="small muted">Removing an entity deletes its scores. Its programs and applications move up to its parent.</p>
        </Drawer>
      )}
    </Page>
  );
}

function EntityFields({ m, f, set, prefix, exclude = [], nameRef }: {
  m: Model; f: EntityForm; set: (f: EntityForm) => void; prefix: string; exclude?: number[]; nameRef?: React.Ref<HTMLInputElement>;
}) {
  return (
    <div className="fgrid">
      <div className="field"><label htmlFor={`${prefix}-type`}>Entity type</label>
        <select className="inp" id={`${prefix}-type`} value={f.type} onChange={(e) => set({ ...f, type: e.target.value as EntityType })}>
          {Object.entries(ETYPE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select></div>
      <div className="field"><label htmlFor={`${prefix}-parent`}>Part of</label>
        <EntitySelect m={m} id={`${prefix}-parent`} value={f.parent_id} onChange={(v) => set({ ...f, parent_id: v as number | null })} emptyLabel="Nothing (top level, rolls up to enterprise)" exclude={exclude} style={{ width: "100%" }} /></div>
      <div className="field"><label htmlFor={`${prefix}-name`}>Name</label><input ref={nameRef} className="inp" id={`${prefix}-name`} value={f.name} onChange={(e) => set({ ...f, name: e.target.value })} placeholder="e.g. Fleet Operations, Fare Modernization program, Maximo Mobile" /></div>
      <div className="field"><label htmlFor={`${prefix}-apps`}>Applications covered</label><input className="inp" type="number" min={1} id={`${prefix}-apps`} value={f.apps} onChange={(e) => set({ ...f, apps: Math.max(1, Number(e.target.value) || 1) })} /></div>
      <div className="field"><label htmlFor={`${prefix}-art`}>ART / programme</label><input className="inp" id={`${prefix}-art`} value={f.art} onChange={(e) => set({ ...f, art: e.target.value })} placeholder="e.g. Marine Operations ART" /></div>
      <div className="field"><label htmlFor={`${prefix}-owner`}>Owner / SPOC (role)</label><input className="inp" id={`${prefix}-owner`} value={f.owner} onChange={(e) => set({ ...f, owner: e.target.value })} placeholder="e.g. Director, Marine IT" /></div>
      <div className="field"><label htmlFor={`${prefix}-crit`}>Criticality</label>
        <select className="inp" id={`${prefix}-crit`} value={f.criticality} onChange={(e) => set({ ...f, criticality: e.target.value as Entity["criticality"] })}>
          <option>High</option><option>Medium</option><option>Low</option>
        </select></div>
    </div>
  );
}
