import { useState } from "react";
import { api } from "../api";
import { Page } from "../components/Layout";
import { ConfirmButton, Drawer, EntityCell, EntitySelect, FaTags, FocusPicker, HeatCell, Loading, NoScope } from "../components/ui";
import { Spark } from "../components/icons";
import { useAuth } from "../lib/auth";
import { CONF, ago, fdate, today } from "../lib/format";
import { base, useEid, useInterviews, useModel, useMut, useWorkspace, type Model } from "../lib/workspace";
import type { Interview } from "../types";

type Form = { entity_id: number | null; date: string; stakeholder: string; type: string; status: "scheduled" | "completed"; notes: string; focus_area_ids: number[] };

export function Interviews() {
  const eid = useEid();
  const ws = useWorkspace(eid);
  const m = useModel(ws.data);
  const ivq = useInterviews(eid);
  const { canWrite } = useAuth();
  const [filter, setFilter] = useState<number | "all">("all");
  const [open, setOpen] = useState<{ id?: number; f: Form } | null>(null);

  if (!ws.data || !ivq.data) return <Page title="Interviews" eid={eid}><Loading /></Page>;
  const all = ivq.data;
  const list = all.filter((i) => m.inScope(filter, i.entity_id));
  const done = all.filter((i) => i.status === "completed").length;
  const planned = ws.data.engagement.interviews_planned;

  const newForm = (): Form => ({ entity_id: filter !== "all" ? filter : m.tree[0]?.e.id ?? null, date: today(), stakeholder: "", type: "Interview", status: "scheduled", notes: "", focus_area_ids: [] });
  const openIv = (i: Interview) => setOpen({ id: i.id, f: { entity_id: i.entity_id, date: i.date, stakeholder: i.stakeholder, type: i.type, status: i.status, notes: i.notes, focus_area_ids: i.focus_area_ids } });

  return (
    <Page title="Interviews" sub="Schedule, log and mine stakeholder interviews" eid={eid}>
      {!m.entities.length ? <NoScope eid={eid} /> : (
        <>
          <section className="row" style={{ justifyContent: "space-between" }}>
            <div className="row"><label className="lbl" htmlFor="ivFilter">Entity</label><EntitySelect m={m} id="ivFilter" value={filter} all onChange={(v) => setFilter(v as number | "all")} /></div>
            {canWrite && <button className="btn primary" onClick={() => setOpen({ f: newForm() })}>+ Log interview</button>}
          </section>
          <section className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))" }}>
            <div className="card kpi"><div className="eyebrow">Completed</div><div className="v">{done}<small> / {planned}</small></div><div className="meter"><i style={{ width: `${Math.min(100, (done / planned) * 100)}%` }} /></div></div>
            <div className="card kpi"><div className="eyebrow">Scheduled</div><div className="v">{all.length - done}</div><div className="d">Upcoming sessions</div></div>
            <div className="card kpi"><div className="eyebrow">Findings applied</div><div className="v">{all.reduce((s, i) => s + i.applied, 0)}</div><div className="d">Scores fed by interviews</div></div>
            <div className="card kpi"><div className="eyebrow">Entities covered</div><div className="v">{new Set(all.map((i) => i.entity_id).filter(Boolean)).size}<small> / {m.entities.length}</small></div><div className="d">{new Set(all.flatMap((i) => i.focus_area_ids)).size} of {m.fas.length} focus areas touched</div></div>
          </section>
          <section className="card">
            {list.length ? (
              <div className="tbl-wrap"><table>
                <thead><tr><th>Date</th><th>Stakeholder</th><th>Entity</th><th>Type</th><th>Status</th><th>Focus areas</th></tr></thead>
                <tbody>
                  {list.map((i) => (
                    <tr key={i.id} className="click" tabIndex={0} onClick={() => openIv(i)} onKeyDown={(e) => e.key === "Enter" && openIv(i)}>
                      <td className="mono" style={{ whiteSpace: "nowrap" }}>{fdate(i.date)}</td>
                      <td><b>{i.stakeholder}</b></td>
                      <td><EntityCell m={m} id={i.entity_id} /></td>
                      <td>{i.type}</td>
                      <td><span className={`badge ${i.status === "completed" ? "ok" : "warn"}`}>{i.status === "completed" ? "Completed" : "Scheduled"}</span>{i.applied > 0 && <> <span className="badge ai">{i.applied} applied</span></>}</td>
                      <td><FaTags m={m} ids={i.focus_area_ids} /></td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
            ) : (
              <div className="empty"><b>No interviews logged{filter !== "all" ? " for this entity" : ""}</b><span>Log a scheduled session now and add notes after it happens. Then extract findings to turn the notes into scores.</span></div>
            )}
          </section>
        </>
      )}
      {open && <InterviewDrawer key={open.id ?? "new"} eid={eid} m={m} id={open.id} initial={open.f} onClose={() => setOpen(null)} onCreated={openIv} />}
    </Page>
  );
}

function InterviewDrawer({ eid, m, id, initial, onClose, onCreated }: {
  eid: number; m: Model; id?: number; initial: Form; onClose: () => void; onCreated: (iv: Interview) => void;
}) {
  const { canWrite } = useAuth();
  const ivq = useInterviews(eid);
  const iv = id ? ivq.data?.find((x) => x.id === id) : undefined;
  const [f, setF] = useState<Form>(initial);
  const [baseline, setBaseline] = useState<Form>(initial);
  const url = `${base(eid)}/interviews`;
  const save = useMut(eid, (body: Form) => (id ? api.patch<Interview>(`${url}/${id}`, body) : api.post<Interview>(url, body)), {
    also: ["interviews"],
    success: () => (id ? "Interview saved" : f.status === "completed" ? "Saved. Extract findings next." : "Interview scheduled"),
    onSuccess: (r) => {
      if (!id && f.status === "completed") onCreated(r);
      else if (f.status !== "completed") onClose();
      else setBaseline(f);
    },
  });
  const extract = useMut(eid, () => api.post<Interview>(`${url}/${id}/extract`), {
    also: ["interviews"],
    success: (r) => `${r.findings?.length || 0} findings extracted`,
    onSuccess: (r) => { setF((p) => ({ ...p, focus_area_ids: r.focus_area_ids })); setBaseline((p) => ({ ...p, focus_area_ids: r.focus_area_ids })); },
  });
  const apply = useMut(eid, (indexes: number[]) => api.post<Interview>(`${url}/${id}/apply`, { indexes }), {
    also: ["interviews"], success: (_, v) => (v.length > 1 ? "Findings applied to the assessment" : "Finding applied to the assessment"),
  });
  const del = useMut(eid, () => api.del(`${url}/${id}`), { also: ["interviews"], success: "Interview deleted", onSuccess: onClose });

  const dirty = JSON.stringify(f) !== JSON.stringify(baseline);
  const findings = iv?.findings;
  const open = (findings || []).map((x, i) => (!x.applied ? i : -1)).filter((i) => i >= 0);
  const dis = !canWrite;

  return (
    <Drawer wide title={id ? "Interview" : "Log interview"} onClose={onClose}
      sub={id && iv ? `${m.path(iv.entity_id) || "No entity"} · logged ${ago(iv.created_at)}` : "Capture the session and the entity the stakeholder belongs to"}
      footer={<>
        {id && canWrite && <span style={{ marginRight: "auto" }}><ConfirmButton label="Delete" onConfirm={() => del.mutate(undefined)} /></span>}
        <button className="btn" onClick={onClose}>{id && !dirty ? "Close" : "Cancel"}</button>
        {canWrite && <button className="btn primary" disabled={!f.stakeholder.trim() || save.isPending || (!!id && !dirty)} onClick={() => save.mutate(f)}>{id ? "Save changes" : "Save interview"}</button>}
      </>}>
      <div className="fgrid">
        <div className="field"><label htmlFor="iv-ent">Entity (LOB, program or application)</label><EntitySelect m={m} id="iv-ent" value={f.entity_id} onChange={(v) => setF({ ...f, entity_id: v as number | null })} emptyLabel="Not set" style={{ width: "100%" }} /></div>
        <div className="field"><label htmlFor="iv-date">Date</label><input className="inp" type="date" id="iv-date" disabled={dis} value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></div>
        <div className="field"><label htmlFor="iv-who">Stakeholder (role)</label><input className="inp" id="iv-who" disabled={dis} autoFocus={!id} value={f.stakeholder} onChange={(e) => setF({ ...f, stakeholder: e.target.value })} placeholder="e.g. QE Lead, Reservations ART" /></div>
        <div className="field"><label htmlFor="iv-type">Type</label>
          <select className="inp" id="iv-type" disabled={dis} value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>{["Interview", "Workshop", "Walkthrough", "Questionnaire"].map((t) => <option key={t}>{t}</option>)}</select></div>
        <div className="field full"><span className="lbl">Status</span>
          <div className="toggle" role="group">
            <button type="button" disabled={dis} aria-pressed={f.status === "scheduled"} onClick={() => setF({ ...f, status: "scheduled" })}>Scheduled</button>
            <button type="button" disabled={dis} aria-pressed={f.status === "completed"} onClick={() => setF({ ...f, status: "completed" })}>Completed</button>
          </div></div>
        <div className="field full"><label htmlFor="iv-notes">Notes</label><textarea className="inp" id="iv-notes" rows={8} disabled={dis} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} placeholder="Type or paste interview notes. Extracting findings turns them into scores against the framework." /></div>
        <div className="field full"><span className="lbl">Focus areas covered</span><FocusPicker m={m} value={f.focus_area_ids} disabled={dis} onChange={(v) => setF({ ...f, focus_area_ids: v })} /></div>
      </div>

      {id && iv?.status === "completed" && (
        <section style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <b>AI findings</b>
            {canWrite && <button className="btn" disabled={extract.isPending || dirty || !iv.notes.trim()} onClick={() => extract.mutate(undefined)} title={dirty ? "Save your changes first" : undefined}>
              {extract.isPending ? <><span className="spin" /> Reading notes…</> : <><Spark /> {findings ? "Extract again" : "Extract findings"}</>}
            </button>}
          </div>
          {dirty && <p className="small muted" style={{ margin: 0 }}>Save your changes before extracting findings.</p>}
          {!iv.entity_id && findings && <div className="notice">Set the entity this stakeholder belongs to, then save, before applying findings.</div>}
          {findings ? findings.length ? (
            <>
              {findings.map((x, i) => {
                const fa = m.faById.get(x.focus_area_id);
                return (
                  <div key={i} className={`finding ${x.applied ? "applied" : ""}`}>
                    <div className="row" style={{ justifyContent: "space-between" }}><b className="small">{fa?.name || "Removed focus area"}</b>{x.score ? <HeatCell s={x.score} style={{ width: 28, height: 28 }} /> : <span className="badge">No level yet</span>}</div>
                    <div className="small">{x.finding}</div>
                    {x.followup && <div className="small muted">Follow-up: {x.followup}</div>}
                    <div className="row">
                      <span className="badge">{CONF[x.confidence]} confidence</span>
                      {x.applied ? <span className="badge ok">Applied to assessment</span>
                        : canWrite && <button className="btn sm primary" disabled={!iv.entity_id || apply.isPending} onClick={() => apply.mutate([i])}>Apply to assessment</button>}
                    </div>
                  </div>
                );
              })}
              {open.length > 1 && canWrite && <button className="btn" disabled={!iv.entity_id || apply.isPending} onClick={() => apply.mutate(open)}>Apply all {open.length} findings</button>}
            </>
          ) : <p className="small muted">No findings matched the framework. Add more detail to the notes and extract again.</p>
            : <p className="small muted">Turns these notes into findings for each focus area discussed, with a suggested maturity level. You review and apply each one.</p>}
        </section>
      )}
    </Drawer>
  );
}
