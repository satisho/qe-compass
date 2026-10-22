import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Page } from "../components/Layout";
import { Icons, Spark } from "../components/icons";
import { EType, EntitySelect, Loading, NoScope, StatusPill } from "../components/ui";
import { useAuth } from "../lib/auth";
import { CONF, ago, fdate, fmt, pillarColor } from "../lib/format";
import { base, useDirectory, useEid, useEvidence, useInterviews, useModel, useMut, useWorkspace, type Model } from "../lib/workspace";
import type { Confidence, Evidence, FocusArea, Interview, Workspace } from "../types";

export function Assessment() {
  const eid = useEid();
  const ws = useWorkspace(eid);
  const m = useModel(ws.data);
  const ivs = useInterviews(eid).data || [];
  const evs = useEvidence(eid).data || [];
  const [params, setParams] = useSearchParams();
  const [pi, setPi] = useState(0);

  if (!ws.data) return <Page title="Assessment" eid={eid}><Loading /></Page>;
  if (!m.entities.length) return <Page title="Assessment" eid={eid}><NoScope eid={eid} /></Page>;
  const requested = Number(params.get("entity"));
  const entity = m.entById.get(requested) || m.tree[0].e;
  const ea = ws.data.analytics.entities[entity.id];
  const pillar = m.pillars[Math.min(pi, m.pillars.length - 1)];
  const kids = m.children(entity.id);

  return (
    <Page title="Assessment" sub={`${entity.name} · Score each focus area, backed by evidence`} eid={eid}>
      <section className="row" style={{ justifyContent: "space-between" }}>
        <div className="row">
          <label className="lbl" htmlFor="capSel">Entity</label>
          <EntitySelect m={m} id="capSel" value={entity.id} onChange={(v) => setParams({ entity: String(v) })} />
          <EType e={entity} />
          {entity.parent_id != null && m.entById.get(entity.parent_id) && <span className="small muted">rolls into {m.path(entity.parent_id)}</span>}
          {kids.length > 0 && <span className="small muted">{kids.length} child {kids.length > 1 ? "entities" : "entity"} roll up here</span>}
        </div>
        <div className="row small muted">Maturity <b className="mono" style={{ color: "var(--ink)" }}>{fmt(ea?.overall)}</b> · coverage <b className="mono" style={{ color: "var(--ink)" }}>{Math.round((ea?.coverage || 0) * 100)}%</b></div>
      </section>
      <div className="ptabs" role="tablist">
        {m.pillars.map((p, i) => (
          <button key={p.id} className="ptab" role="tab" aria-selected={p.id === pillar.id} onClick={() => setPi(i)} style={{ ["--pc" as string]: pillarColor(p.color) }}>
            {p.short}<span className="mono">{fmt(ea?.pillars[i])}</span>
          </button>
        ))}
      </div>
      <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {pillar.focus_areas.map((f) => (
          <FaCard key={`${entity.id}-${f.id}`} eid={eid} w={ws.data!} m={m} entityId={entity.id} fa={f} color={pillarColor(pillar.color)} ivs={ivs} evs={evs} />
        ))}
        {!pillar.focus_areas.length && <div className="card empty"><b>No focus areas in this pillar</b><Link to={`/e/${eid}/framework`} className="btn">Add focus areas in Framework</Link></div>}
      </section>
    </Page>
  );
}

function FaCard({ eid, w, m, entityId, fa, color, ivs, evs }: {
  eid: number; w: Workspace; m: Model; entityId: number; fa: FocusArea; color: string; ivs: Interview[]; evs: Evidence[];
}) {
  const { canWrite } = useAuth();
  const names = useDirectory();
  const a = m.assessment(entityId, fa.id);
  const cell = m.cell(entityId, fa.id);
  const [notes, setNotes] = useState(a?.notes || "");
  const [saving, setSaving] = useState<"idle" | "saving" | "saved">("idle");
  const [showHist, setShowHist] = useState(false);
  const [sugg, setSugg] = useState<{ level: number | null; cues: string[] } | null>(null);
  const timer = useRef<number>();
  const lastSaved = useRef(a?.notes || "");
  const url = `${base(eid)}/assessments/${entityId}/${fa.id}`;

  // adopt remote changes when not editing locally
  useEffect(() => { if (notes === lastSaved.current && (a?.notes || "") !== notes) { setNotes(a?.notes || ""); lastSaved.current = a?.notes || ""; } }, [a?.notes]); // eslint-disable-line react-hooks/exhaustive-deps

  const put = useMut(eid, (body: Record<string, unknown>) => api.put(url, body), {});
  const scoreLabel = (v: number | null) => (v ? `${v} · ${m.level(v)}` : "not assessed");

  // suggestion from notes (debounced, server-side engine)
  useEffect(() => {
    if (notes.trim().length < 12) { setSugg(null); return; }
    const t = window.setTimeout(() => {
      api.post<{ level: number | null; cues: string[] }>(`${base(eid)}/suggest-level`, { notes }).then(setSugg).catch(() => setSugg(null));
    }, 500);
    return () => window.clearTimeout(t);
  }, [notes, eid]);

  const onNotes = (v: string) => {
    setNotes(v);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      setSaving("saving");
      put.mutate({ notes: v }, { onSuccess: () => { lastSaved.current = v; setSaving("saved"); }, onError: () => setSaving("idle") });
    }, 900);
  };
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const ids = new Set([entityId, ...m.descendants(entityId)]);
  const linkedIv = ivs.filter((i) => i.status === "completed" && i.entity_id != null && ids.has(i.entity_id) && i.focus_area_ids.includes(fa.id));
  const linkedEv = evs.filter((d) => d.entity_id != null && ids.has(d.entity_id) && d.focus_area_ids.includes(fa.id));
  const n = linkedIv.length + linkedEv.length;
  const score = a?.score ?? null;

  return (
    <article className="card fa" style={{ ["--pc" as string]: color }}>
      <div>
        <h3>{fa.name} <StatusPill status={cell?.status || "val"} /></h3>
        <div className="desc">{fa.description}</div>
        <div className="q"><b>Guiding question</b>{fa.question}</div>
        {score != null && <div className="small muted" style={{ marginTop: 8 }}><b>Level {score} · {m.level(score)}:</b> {w.settings.scale[score - 1]?.description}</div>}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0 }}>
        <div className="ctl-row">
          <div className="field"><span className="lbl">Current maturity</span>
            <div className="seg" role="group" aria-label={`Maturity score for ${fa.name}`}>
              {[1, 2, 3, 4, 5].map((v) => (
                <button key={v} data-v={v} aria-pressed={score === v} title={m.level(v)} disabled={!canWrite}
                  onClick={() => put.mutate({ score: v, set_score: true }, {})}>{v}</button>
              ))}
              <button data-v="null" aria-pressed={score == null} disabled={!canWrite} onClick={() => put.mutate({ score: null, set_score: true })}>N/A</button>
            </div>
          </div>
          <div className="field"><label htmlFor={`c-${fa.id}`}>Confidence</label>
            <select className="inp" id={`c-${fa.id}`} style={{ width: "auto" }} disabled={!canWrite} value={a?.confidence || ""}
              onChange={(e) => put.mutate({ confidence: e.target.value || null, set_confidence: true })}>
              <option value="">Auto · {cell?.confidence ? CONF[cell.confidence] : "—"}</option>
              {(["low", "med", "high"] as Confidence[]).map((c) => <option key={c} value={c}>{CONF[c]} (override)</option>)}
            </select>
          </div>
        </div>
        <div>
          <span className="lbl">Linked evidence · {n}</span>
          <div className="links" style={{ marginTop: 5 }}>
            {linkedIv.map((i) => <Link key={`i${i.id}`} className="lk" to={`/e/${eid}/interviews`} title={m.path(i.entity_id)}>{Icons.talk}<span>{i.stakeholder} · {fdate(i.date)}</span></Link>)}
            {linkedEv.map((d) => <Link key={`d${d.id}`} className="lk" to={`/e/${eid}/evidence`} title={m.path(d.entity_id)}>{Icons.doc}<span>{d.name}</span></Link>)}
            {!n && <span className="small muted">None yet. Link evidence from Interviews or the Evidence Library.</span>}
          </div>
        </div>
        <div className="field"><label htmlFor={`n-${fa.id}`}>Assessment notes {saving === "saving" ? <span className="muted">· saving…</span> : saving === "saved" ? <span className="muted">· saved</span> : null}</label>
          <textarea className="inp" id={`n-${fa.id}`} disabled={!canWrite} value={notes} onChange={(e) => onNotes(e.target.value)} placeholder="What did you observe? Paste interview notes or artifact findings…" />
        </div>
        {sugg && (sugg.level == null ? (
          <div className="ai-sug"><Spark /><span>Notes don’t yet indicate a level. Add specifics: tools used, coverage figures, how consistently it happens.</span></div>
        ) : (
          <div className="ai-sug"><Spark />
            <span>{sugg.level === score ? <>Notes are consistent with level <b>{scoreLabel(sugg.level)}</b></> : <>Notes read as level <b>{scoreLabel(sugg.level)}</b>{score ? ` (scored ${score})` : ""}</>}, based on {sugg.cues.map((c) => `“${c}”`).join(", ")}.{" "}
              {sugg.level !== score && canWrite && <button className="btn sm" onClick={() => put.mutate({ score: sugg.level, set_score: true, source: "suggestion" })}>Apply</button>}
            </span>
          </div>
        ))}
        {cell?.inherited && <div className="small muted">Rolled up from child entities: <b className="mono">{fmt(cell.score)}</b>. Score here to assess this entity directly.</div>}
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span className="stamp">{a?.updated_at ? `Last updated ${ago(a.updated_at)}${a.updated_by && names.get(a.updated_by) ? ` by ${names.get(a.updated_by)}` : ""}` : ""}</span>
          {a && <button className="btn sm ghost" onClick={() => setShowHist(!showHist)}>{showHist ? "Hide history" : "History"}</button>}
        </div>
        {showHist && <History eid={eid} entityId={entityId} faId={fa.id} m={m} />}
      </div>
    </article>
  );
}

function History({ eid, entityId, faId, m }: { eid: number; entityId: number; faId: number; m: Model }) {
  const names = useDirectory();
  const q = useQuery({
    queryKey: ["hist", eid, entityId, faId],
    queryFn: () => api.get<{ score: number | null; confidence: string | null; notes: string; source: string; changed_by: number | null; changed_at: string }[]>(
      `${base(eid)}/assessments/${entityId}/${faId}/history`),
  });
  if (!q.data) return <Loading />;
  const src: Record<string, string> = { manual: "scored", interview: "from interview", suggestion: "from suggestion" };
  return (
    <div className="hist">
      {q.data.filter((h, i, arr) => i === arr.length - 1 || h.score !== arr[i + 1].score).slice(0, 10).map((h, i) => (
        <div key={i}>
          <span className={`cell ${h.score ? `c${h.score}` : "cnull"}`} style={{ width: 24, height: 24, fontSize: 11 }}>{h.score ?? "·"}</span>
          <span className="muted">{m.level(h.score)} · {src[h.source] || h.source} · {ago(h.changed_at)}{h.changed_by && names.get(h.changed_by) ? ` · ${names.get(h.changed_by)}` : ""}</span>
        </div>
      ))}
    </div>
  );
}
