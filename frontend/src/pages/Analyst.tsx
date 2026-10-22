import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../api";
import { Page } from "../components/Layout";
import { Spark } from "../components/icons";
import { EntitySelect, Loading, Markdown } from "../components/ui";
import { fmt } from "../lib/format";
import { useToast } from "../lib/toast";
import { base, useEid, useEvidence, useInterviews, useModel, useWorkspace } from "../lib/workspace";

type Msg = { role: "user" | "assistant"; content: string; meta?: string };
const PROMPTS = [
  "Where are the biggest gaps?", "What evidence is still missing?", "Draft follow-up interview questions",
  "Any conflicting signals?", "Quick wins for the next 90 days", "Strengths we can scale", "Compare entities", "Write an executive summary",
];
const chats = new Map<number, Msg[]>(); // keep the conversation while navigating within the session

export function Analyst() {
  const eid = useEid();
  const ws = useWorkspace(eid);
  const m = useModel(ws.data);
  const ivs = useInterviews(eid).data || [];
  const evs = useEvidence(eid).data || [];
  const toast = useToast();
  const [scope, setScope] = useState<number | "all">("all");
  const [msgs, setMsgs] = useState<Msg[]>(() => chats.get(eid) || []);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const sum = useQuery({
    queryKey: ["summary", eid, scope],
    queryFn: () => api.get<{ overall: number | null; coverage: number; evidence_gaps: number; conflicts: number; gap_focus_areas: number }>(
      `${base(eid)}/summary${scope === "all" ? "" : `?scope=${scope}`}`),
  });
  useEffect(() => { chats.set(eid, msgs); logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" }); }, [msgs, eid]);

  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    const next = [...msgs, { role: "user" as const, content: question }];
    setMsgs(next);
    setQ("");
    setBusy(true);
    try {
      const r = await api.post<{ answer: string; engine: string; scope_name: string }>(`${base(eid)}/analyst`, {
        question, scope: scope === "all" ? null : scope, history: next.slice(-8).map(({ role, content }) => ({ role, content })),
      });
      setMsgs([...next, { role: "assistant", content: r.answer, meta: `${r.engine === "rules" ? "analysis engine" : r.engine} · ${r.scope_name}` }]);
    } catch (e) {
      toast((e as Error).message, "error");
      setMsgs(next);
    } finally {
      setBusy(false);
    }
  };
  const submit = (e: FormEvent) => { e.preventDefault(); ask(q); };

  if (!ws.data) return <Page title="AI Analyst" eid={eid}><Loading /></Page>;
  const s = sum.data;
  return (
    <Page title="AI Analyst" sub="Interrogate everything captured so far" eid={eid}>
      <div className="an">
        <section className="card chat">
          <div style={{ padding: "13px 20px", borderBottom: "1px solid var(--line)", display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 180 }}>
              <b style={{ fontFamily: "var(--f-display)" }}>QE Compass Analyst</b> <span className="badge ai">Built-in engine</span>
              <div className="small muted">Reads every score, note, interview and artifact in this engagement</div>
            </div>
            <div className="row"><label className="small muted" htmlFor="scopeSel">Scope</label>
              <EntitySelect m={m} id="scopeSel" value={scope} all allLabel="Enterprise (all entities)" onChange={(v) => setScope(v as number | "all")} />
            </div>
          </div>
          <div className="chat-log" ref={logRef} aria-live="polite">
            {!msgs.length && (
              <div className="msg ai"><div className="ava"><span style={{ color: "#3bb4c9" }}><Spark /></span></div>
                <div className="md"><div className="meta">analyst · ready</div>
                  <p>I can see {m.entities.length} entities in scope, {ivs.filter((i) => i.status === "completed").length} completed interviews and {evs.length} artifacts. Ask me where the gaps are, what evidence is missing, or what to ask in the next interviews. Mention an entity or focus area by name to focus the answer.</p>
                </div></div>
            )}
            {msgs.map((x, i) => x.role === "user"
              ? <div key={i} className="msg me">{x.content}</div>
              : <div key={i} className="msg ai"><div className="ava"><span style={{ color: "#3bb4c9" }}><Spark /></span></div><div style={{ minWidth: 0 }}><div className="meta">{x.meta}</div><Markdown text={x.content} /></div></div>)}
            {busy && <div className="msg ai"><div className="ava"><span style={{ color: "#3bb4c9" }}><Spark /></span></div><p className="cursor muted">Reading the workspace…</p></div>}
          </div>
          <div className="composer">
            <div className="prompts">{PROMPTS.map((p) => <button key={p} onClick={() => ask(p)} disabled={busy}>{p}</button>)}</div>
            <form className="cbar" onSubmit={submit}>
              <input className="inp" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about any LOB, program, application or focus area…" aria-label="Question" />
              <button className="btn primary" type="submit" disabled={busy || !q.trim()}>Ask</button>
            </form>
          </div>
        </section>
        <aside className="card pad">
          <div className="eyebrow">Signals · {scope === "all" ? "Enterprise" : m.entById.get(scope)?.name}</div>
          <div className="sig"><div className="v mono">{fmt(s?.overall)}</div><span>Live maturity (of 5)</span></div>
          <div className="sig"><div className="v mono">{s ? Math.round(s.coverage * 100) : "—"}%</div><span>Evidence coverage, medium+ confidence</span></div>
          <div className="sig"><div className="v mono" style={{ color: "var(--val)" }}>{s?.evidence_gaps ?? "—"}</div><span>Evidence gaps to close</span></div>
          <div className="sig"><div className="v mono" style={{ color: "var(--partial)" }}>{s?.conflicts ?? "—"}</div><span>Conflicting signals</span></div>
          <div className="sig"><div className="v mono" style={{ color: "var(--gap)" }}>{s?.gap_focus_areas ?? "—"}</div><span>Focus areas flagged as potential gap</span></div>
        </aside>
      </div>
    </Page>
  );
}
