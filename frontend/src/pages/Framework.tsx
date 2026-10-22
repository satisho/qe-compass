import { useEffect, useState } from "react";
import { api } from "../api";
import { Page } from "../components/Layout";
import { ConfirmButton, Drawer, Loading } from "../components/ui";
import { useAuth } from "../lib/auth";
import { pillarColor } from "../lib/format";
import { base, useEid, useMut, useWorkspace } from "../lib/workspace";
import type { FocusArea, FrameworkSettings, Horizon, Pillar } from "../types";

type FaForm = { name: string; description: string; question: string; recommendation: string; horizon: Horizon };
type Editing =
  | { kind: "fa"; pillar: Pillar; fa?: FocusArea; f: FaForm }
  | { kind: "pillar"; pillar?: Pillar; f: { name: string; short: string } };

export function Framework() {
  const eid = useEid();
  const ws = useWorkspace(eid);
  const { canWrite } = useAuth();
  const [settings, setSettings] = useState<FrameworkSettings | null>(null);
  const [edit, setEdit] = useState<Editing | null>(null);
  useEffect(() => { if (ws.data) setSettings(structuredClone(ws.data.settings)); }, [ws.data?.settings]); // eslint-disable-line react-hooks/exhaustive-deps

  const fw = `${base(eid)}/framework`;
  const saveSettings = useMut(eid, (body: Partial<FrameworkSettings>) => api.patch(`${fw}/settings`, body), { success: "Framework updated" });
  const patchPillar = useMut(eid, ({ id, ...b }: { id: number; target?: number; weight?: number; name?: string; short?: string }) => api.patch(`${fw}/pillars/${id}`, b), { success: "Pillar updated" });
  const addPillar = useMut(eid, (b: { name: string; short: string }) => api.post(`${fw}/pillars`, b), { success: "Pillar added" });
  const delPillar = useMut(eid, (id: number) => api.del(`${fw}/pillars/${id}`), { success: "Pillar removed" });
  const addFa = useMut(eid, ({ pid, ...b }: FaForm & { pid: number }) => api.post(`${fw}/pillars/${pid}/focus-areas`, b), { success: "Focus area added" });
  const patchFa = useMut(eid, ({ id, ...b }: FaForm & { id: number }) => api.patch(`${fw}/focus-areas/${id}`, b), { success: "Focus area updated" });
  const delFa = useMut(eid, (id: number) => api.del(`${fw}/focus-areas/${id}`), { success: "Focus area removed" });

  if (!ws.data || !settings) return <Page title="Framework" eid={eid}><Loading /></Page>;
  const pillars = ws.data.pillars;
  const dis = !canWrite;

  const close = () => setEdit(null);
  const save = () => {
    if (!edit) return;
    if (edit.kind === "pillar") {
      if (edit.pillar) patchPillar.mutate({ id: edit.pillar.id, ...edit.f }, { onSuccess: close });
      else addPillar.mutate(edit.f, { onSuccess: close });
    } else if (edit.fa) patchFa.mutate({ id: edit.fa.id, ...edit.f }, { onSuccess: close });
    else addFa.mutate({ pid: edit.pillar.id, ...edit.f }, { onSuccess: close });
  };

  return (
    <Page title="Framework" sub="Pillars, focus areas, maturity scale and scoring rules for this engagement" eid={eid}>
      <div className="banner">This engagement has its own copy of the framework. Changes apply instantly to scores, heatmaps and new dashboards; published dashboards keep the framework they were published with.</div>

      <section className="card pad">
        <div className="sec-h"><div><h2>Maturity scale</h2><p>What each level means. Assessors score against these descriptors.</p></div>
          {canWrite && <button className="btn sm primary" onClick={() => saveSettings.mutate({ scale: settings.scale })}>Save scale</button>}</div>
        <div className="scale-ed">
          {settings.scale.map((s, i) => (
            <div key={i} style={{ display: "contents" }}>
              <span className={`cell c${i + 1}`} style={{ width: 30, height: 30 }}>{i + 1}</span>
              <input className="inp" aria-label={`Level ${i + 1} label`} disabled={dis} value={s.label} onChange={(e) => { const sc = [...settings.scale]; sc[i] = { ...s, label: e.target.value }; setSettings({ ...settings, scale: sc }); }} />
              <input className="inp d" aria-label={`Level ${i + 1} descriptor`} disabled={dis} value={s.description} onChange={(e) => { const sc = [...settings.scale]; sc[i] = { ...s, description: e.target.value }; setSettings({ ...settings, scale: sc }); }} />
            </div>
          ))}
        </div>
      </section>

      <section className="card pad">
        <div className="sec-h"><div><h2>Scoring rules</h2><p>How scores roll up to pillars, entities and the enterprise. Programs and applications fill in their parent wherever the parent isn’t scored directly.</p></div>
          {canWrite && <button className="btn sm primary" onClick={() => saveSettings.mutate({ thresholds: settings.thresholds, weighting: settings.weighting })}>Save rules</button>}</div>
        <div className="fgrid">
          <div className="field"><label htmlFor="r-w">Enterprise roll-up</label>
            <select className="inp" id="r-w" disabled={dis} value={settings.weighting} onChange={(e) => setSettings({ ...settings, weighting: e.target.value as FrameworkSettings["weighting"] })}>
              <option value="apps">Weight entities by application count</option><option value="equal">Weight entities equally</option>
            </select></div>
          <div className="field"><span className="lbl">Status thresholds</span>
            <div className="row">
              <span className="st gap" /><label className="small" htmlFor="r-gap">Gap at or below</label>
              <input className="inp mono" style={{ width: 80 }} type="number" step={0.25} min={1} max={5} id="r-gap" disabled={dis} value={settings.thresholds.gap} onChange={(e) => setSettings({ ...settings, thresholds: { ...settings.thresholds, gap: Number(e.target.value) } })} />
              <span className="st strong" /><label className="small" htmlFor="r-str">Strength from</label>
              <input className="inp mono" style={{ width: 80 }} type="number" step={0.25} min={1} max={5} id="r-str" disabled={dis} value={settings.thresholds.strong} onChange={(e) => setSettings({ ...settings, thresholds: { ...settings.thresholds, strong: Number(e.target.value) } })} />
            </div></div>
          <div className="field full"><span className="lbl">Evidence confidence</span><span className="small muted">Set automatically from linked evidence on the entity and its children: 3+ completed interviews or artifacts = High, 2 = Medium, fewer = Low. Assessors can override it per focus area.</span></div>
        </div>
      </section>

      {pillars.map((p) => (
        <section key={p.id} className="card fw-p">
          <div className="fw-ph" style={{ background: pillarColor(p.color) }}>
            <h3>{p.name}</h3>
            <label>Target <input className="inp mono" type="number" step={0.5} min={1} max={5} disabled={dis} defaultValue={p.target} key={`t${p.target}`}
              onBlur={(e) => Number(e.target.value) !== p.target && patchPillar.mutate({ id: p.id, target: Number(e.target.value) })} /></label>
            <label>Weight <input className="inp mono" type="number" step={0.5} min={0} max={10} disabled={dis} defaultValue={p.weight} key={`w${p.weight}`}
              onBlur={(e) => Number(e.target.value) !== p.weight && patchPillar.mutate({ id: p.id, weight: Number(e.target.value) })} /></label>
            {canWrite && <button className="btn sm" style={{ background: "rgba(255,255,255,.16)", color: "#fff", borderColor: "transparent" }} onClick={() => setEdit({ kind: "pillar", pillar: p, f: { name: p.name, short: p.short } })}>Edit</button>}
          </div>
          {p.focus_areas.map((f) => (
            <div key={f.id} className="fw-fa">
              <div><b>{f.name}</b><p>{f.description}</p></div>
              {canWrite && <button className="btn sm" onClick={() => setEdit({ kind: "fa", pillar: p, fa: f, f: { name: f.name, description: f.description, question: f.question, recommendation: f.recommendation, horizon: f.horizon } })}>Edit</button>}
            </div>
          ))}
          {canWrite && <div className="fw-fa"><div /><button className="btn sm primary" onClick={() => setEdit({ kind: "fa", pillar: p, f: { name: "", description: "", question: "", recommendation: "", horizon: "next" } })}>+ Focus area</button></div>}
        </section>
      ))}
      {canWrite && <div><button className="btn" onClick={() => setEdit({ kind: "pillar", f: { name: "", short: "" } })}>+ Add pillar</button></div>}

      {edit && (
        <Drawer title={edit.kind === "pillar" ? (edit.pillar ? "Edit pillar" : "New pillar") : edit.fa ? "Edit focus area" : `New focus area · ${edit.pillar.short}`} onClose={close}
          footer={<>
            {edit.kind === "fa" && edit.fa && <span style={{ marginRight: "auto" }}><ConfirmButton label="Delete" onConfirm={() => delFa.mutate(edit.fa!.id, { onSuccess: close })} /></span>}
            {edit.kind === "pillar" && edit.pillar && <span style={{ marginRight: "auto" }}><ConfirmButton label="Delete pillar" onConfirm={() => delPillar.mutate(edit.pillar!.id, { onSuccess: close })} /></span>}
            <button className="btn" onClick={close}>Cancel</button>
            <button className="btn primary" onClick={save} disabled={!edit.f.name.trim()}>Save</button>
          </>}>
          {edit.kind === "pillar" ? (
            <>
              <div className="field"><label htmlFor="pl-name">Pillar name</label><input className="inp" id="pl-name" autoFocus value={edit.f.name} onChange={(e) => setEdit({ ...edit, f: { ...edit.f, name: e.target.value } })} /></div>
              <div className="field"><label htmlFor="pl-short">Short label</label><input className="inp" id="pl-short" maxLength={40} value={edit.f.short} onChange={(e) => setEdit({ ...edit, f: { ...edit.f, short: e.target.value } })} /></div>
              {edit.pillar && <p className="small muted">Deleting a pillar removes its focus areas and every score recorded against them.</p>}
            </>
          ) : (
            <>
              <div className="field"><label htmlFor="fa-name">Name</label><input className="inp" id="fa-name" autoFocus value={edit.f.name} onChange={(e) => setEdit({ ...edit, f: { ...edit.f, name: e.target.value } })} /></div>
              <div className="field"><label htmlFor="fa-desc">What it covers</label><input className="inp" id="fa-desc" value={edit.f.description} onChange={(e) => setEdit({ ...edit, f: { ...edit.f, description: e.target.value } })} /></div>
              <div className="field"><label htmlFor="fa-q">Guiding question for assessors</label><textarea className="inp" id="fa-q" value={edit.f.question} onChange={(e) => setEdit({ ...edit, f: { ...edit.f, question: e.target.value } })} /></div>
              <div className="field"><label htmlFor="fa-rec">Recommendation when this is a gap</label><textarea className="inp" id="fa-rec" value={edit.f.recommendation} onChange={(e) => setEdit({ ...edit, f: { ...edit.f, recommendation: e.target.value } })} /></div>
              <div className="field"><label htmlFor="fa-h">Roadmap horizon</label>
                <select className="inp" id="fa-h" value={edit.f.horizon} onChange={(e) => setEdit({ ...edit, f: { ...edit.f, horizon: e.target.value as Horizon } })}>
                  <option value="now">Now · 0–3 months</option><option value="next">Next · 3–9 months</option><option value="later">Later · 9–18 months</option>
                </select></div>
              {edit.fa && <p className="small muted">Deleting a focus area removes every score recorded against it.</p>}
            </>
          )}
        </Drawer>
      )}
    </Page>
  );
}
