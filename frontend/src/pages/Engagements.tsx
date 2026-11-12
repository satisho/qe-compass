import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { Page } from "../components/Layout";
import { Empty, Loading } from "../components/ui";
import { useAuth } from "../lib/auth";
import { fdate, phaseAt, today, weekOf } from "../lib/format";
import { useToast } from "../lib/toast";
import type { Engagement } from "../types";

export function Engagements() {
  const { canWrite, isAdmin } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["engagements"], queryFn: () => api.get<Engagement[]>("/api/engagements") });
  const [f, setF] = useState({ client: "", title: "Enterprise Quality Engineering Assessment", start_date: today(), weeks: 8, interviews_planned: 30 });
  const fileRef = useRef<HTMLInputElement>(null);

  const done = (e: { id: number }, msg: string) => {
    qc.invalidateQueries({ queryKey: ["engagements"] });
    toast(msg);
    nav(`/e/${e.id}/overview`);
  };
  const create = useMutation({
    mutationFn: () => api.post<Engagement>("/api/engagements", f),
    onSuccess: (e) => done(e, "Engagement created with the standard framework"),
    onError: (e: Error) => toast(e.message, "error"),
  });
  const sample = useMutation({
    mutationFn: () => api.post<Engagement>("/api/engagements/sample"),
    onSuccess: (e) => done(e, "Sample engagement loaded"),
    onError: (e: Error) => toast(e.message, "error"),
  });
  const imp = useMutation({
    mutationFn: (file: File) => { const fd = new FormData(); fd.append("file", file); return api.upload<{ id: number }>("/api/engagements/import", fd); },
    onSuccess: (e) => done(e, "Engagement imported"),
    onError: (e: Error) => toast(e.message, "error"),
  });

  const submit = (e: FormEvent) => { e.preventDefault(); create.mutate(); };
  const list = q.data || [];

  return (
    <Page title="Engagements" sub="Each engagement has its own framework, scope, evidence and dashboards">
      {q.isLoading ? <Loading /> : list.length ? (
        <section className="grid g-lob">
          {list.map((e) => {
            const wk = weekOf(e.start_date, e.weeks);
            return (
              <Link key={e.id} to={`/e/${e.id}/overview`} className="card eng-card">
                <div className="eyebrow">{e.client}{e.archived ? " · archived" : ""}</div>
                <h3>{e.title}</h3>
                <div className="small muted">Started {fdate(e.start_date)} · week {wk} of {e.weeks} · {phaseAt(wk)}</div>
                <div className="stats">
                  <span><b>{e.entities}</b> entities</span><span><b>{e.interviews}</b> interviews</span>
                  <span><b>{e.evidence}</b> artifacts</span><span><b>{e.snapshots}</b> dashboards</span>
                </div>
              </Link>
            );
          })}
        </section>
      ) : (
        <Empty title="No engagements yet">
          Create the first engagement below{isAdmin ? ", or load the sample engagement to explore the platform" : ""}.
        </Empty>
      )}

      {canWrite && (
        <section className="card pad">
          <div className="sec-h"><div><h2>Start a new engagement</h2><p>Begins with the standard 5-pillar, 25-focus-area framework, which you can tailor afterwards</p></div></div>
          <form className="fgrid" onSubmit={submit}>
            <div className="field"><label htmlFor="ne-client">Client</label><input className="inp" id="ne-client" required value={f.client} onChange={(e) => setF({ ...f, client: e.target.value })} placeholder="e.g. Contoso Ltd" /></div>
            <div className="field"><label htmlFor="ne-title">Engagement</label><input className="inp" id="ne-title" required value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></div>
            <div className="field"><label htmlFor="ne-start">Start date (week 1)</label><input className="inp" id="ne-start" type="date" required value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} /></div>
            <div className="field"><label htmlFor="ne-weeks">Duration (weeks)</label><input className="inp" id="ne-weeks" type="number" min={1} max={52} value={f.weeks} onChange={(e) => setF({ ...f, weeks: Number(e.target.value) })} /></div>
            <div className="field"><label htmlFor="ne-iv">Interviews planned</label><input className="inp" id="ne-iv" type="number" min={1} value={f.interviews_planned} onChange={(e) => setF({ ...f, interviews_planned: Number(e.target.value) })} /></div>
            <div className="field" style={{ justifyContent: "flex-end" }}><button className="btn primary" type="submit" disabled={create.isPending}>Create engagement</button></div>
          </form>
          <div className="row" style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--line)" }}>
            <button className="btn" onClick={() => fileRef.current?.click()} disabled={imp.isPending}>Import from export file</button>
            <input ref={fileRef} type="file" accept=".json,application/json" hidden onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) imp.mutate(file); }} />
            {isAdmin && <button className="btn" onClick={() => sample.mutate()} disabled={sample.isPending}>Load sample engagement</button>}
            <span className="small muted">Imports bring in an engagement exported from another QE Compass installation.</span>
          </div>
        </section>
      )}
    </Page>
  );
}
