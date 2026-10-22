import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Entity, Status } from "../types";
import { ESHORT, STATUS_LABEL, cellText, heatClass, pillarColor } from "../lib/format";
import type { Model } from "../lib/workspace";
import { Icons } from "./icons";

export function EType({ e }: { e: Pick<Entity, "type"> }) {
  return <span className={`etype t-${e.type}`}>{ESHORT[e.type]}</span>;
}

export function StatusPill({ status }: { status: Status }) {
  return <span className={`st ${status}`}>{STATUS_LABEL[status]}</span>;
}

export function HeatCell({ s, low, inh, onClick, label, style }: {
  s: number | null | undefined; low?: boolean; inh?: boolean; onClick?: () => void; label?: string; style?: React.CSSProperties;
}) {
  const cls = `cell ${heatClass(s)} ${low ? "lowc" : ""} ${inh ? "inh" : ""}`;
  return onClick ? (
    <button className={cls} onClick={onClick} aria-label={label} style={style}>{cellText(s)}</button>
  ) : (
    <span className={cls} style={style}>{cellText(s)}</span>
  );
}

export function Loading({ what = "Loading…" }: { what?: string }) {
  return <div className="loading"><span className="spin" style={{ display: "inline-block", verticalAlign: "middle", marginRight: 8 }} />{what}</div>;
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="card empty"><b>{title}</b>{children && <span>{children}</span>}{action}</div>;
}

export function NoScope({ eid }: { eid: number }) {
  return (
    <Empty title="Nothing in scope yet" action={<Link className="btn primary" to={`/e/${eid}/scope`}>Set up scope</Link>}>
      Add a line of business, program or application to start capturing evidence.
    </Empty>
  );
}

/** Two-step destructive button: first click asks, second confirms. */
export function ConfirmButton({ label, confirm = "Yes, delete", onConfirm, className = "btn danger", disabled, small }: {
  label: string; confirm?: string; onConfirm: () => void; className?: string; disabled?: boolean; small?: boolean;
}) {
  const [asking, setAsking] = useState(false);
  if (!asking) {
    return <button type="button" className={`${className} ${small ? "sm" : ""}`} disabled={disabled} onClick={() => setAsking(true)}>{label}</button>;
  }
  return (
    <span className="confirm">
      Are you sure?
      <button type="button" className={`btn sm danger`} onClick={() => { setAsking(false); onConfirm(); }}>{confirm}</button>
      <button type="button" className="btn sm" onClick={() => setAsking(false)}>No</button>
    </span>
  );
}

export function Drawer({ title, sub, onClose, children, footer, wide }: {
  title: string; sub?: ReactNode; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean;
}) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const first = ref.current?.querySelector<HTMLElement>("[autofocus], input, textarea, select") ?? ref.current?.querySelector<HTMLElement>(".x");
    first?.focus();
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={title} ref={ref} style={wide ? { width: "min(640px,100%)" } : undefined}>
        <header>
          <div style={{ minWidth: 0 }}><h3>{title}</h3>{sub && <div className="small muted">{sub}</div>}</div>
          <button className="x" onClick={onClose} aria-label="Close">✕</button>
        </header>
        <div className="db">{children}</div>
        {footer && <footer>{footer}</footer>}
      </aside>
    </>
  );
}

export function EntitySelect({ m, value, onChange, all, allLabel = "All entities", exclude = [], id, emptyLabel, style }: {
  m: Model; value: number | "all" | null; onChange: (v: number | "all" | null) => void; all?: boolean; allLabel?: string;
  exclude?: number[]; id?: string; emptyLabel?: string; style?: React.CSSProperties;
}) {
  return (
    <select className="inp" id={id} style={{ width: "auto", maxWidth: "100%", ...style }}
      value={value == null ? "" : String(value)}
      onChange={(e) => onChange(e.target.value === "all" ? "all" : e.target.value === "" ? null : Number(e.target.value))}>
      {all && <option value="all">{allLabel}</option>}
      {emptyLabel != null && <option value="">{emptyLabel}</option>}
      {m.tree.filter(({ e }) => !exclude.includes(e.id)).map(({ e, depth }) => (
        <option key={e.id} value={e.id}>{"   ".repeat(depth)}{depth ? "↳ " : ""}{e.name} ({ESHORT[e.type]})</option>
      ))}
    </select>
  );
}

export function FocusPicker({ m, value, onChange, disabled }: {
  m: Model; value: number[]; onChange: (v: number[]) => void; disabled?: boolean;
}) {
  return (
    <div className="picker">
      {m.pillars.map((p) => (
        <div className="pg" key={p.id} style={{ ["--pcol" as string]: pillarColor(p.color) }}>
          <span className="eyebrow" style={{ color: pillarColor(p.color) }}>{p.short}</span>
          <div>
            {p.focus_areas.map((f) => (
              <button type="button" key={f.id} disabled={disabled} aria-pressed={value.includes(f.id)}
                onClick={() => onChange(value.includes(f.id) ? value.filter((x) => x !== f.id) : [...value, f.id])}>
                {f.name}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function EntityCell({ m, id }: { m: Model; id: number | null }) {
  const e = id != null ? m.entById.get(id) : undefined;
  if (!e) return <span className="muted">—</span>;
  return (
    <>
      <div className="row" style={{ gap: 6, flexWrap: "nowrap" }}><EType e={e} /><span>{e.name}</span></div>
      {e.parent_id != null && m.entById.get(e.parent_id) && <div className="small muted">{m.path(e.parent_id)}</div>}
    </>
  );
}

export function FaTags({ m, ids, max = 3 }: { m: Model; ids: number[]; max?: number }) {
  return (
    <div className="tags">
      {ids.slice(0, max).map((f) => <span key={f}>{m.faById.get(f)?.name || "Removed focus area"}</span>)}
      {ids.length > max && <span>+{ids.length - max}</span>}
    </div>
  );
}

/** Minimal, safe Markdown: ## headings, - and 1. lists, **bold**, `code`, paragraphs. */
export function Markdown({ text }: { text: string }) {
  const inline = (s: string) =>
    s.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) =>
      part.startsWith("**") && part.endsWith("**") ? <b key={i}>{part.slice(2, -2)}</b>
        : part.startsWith("`") && part.endsWith("`") ? <code key={i}>{part.slice(1, -1)}</code>
          : <Fragment key={i}>{part}</Fragment>);
  const blocks: ReactNode[] = [];
  let list: { kind: "ul" | "ol"; items: string[] } | null = null;
  const flush = () => {
    if (!list) return;
    const L = list.kind;
    const items = list.items;
    blocks.push(L === "ul"
      ? <ul key={blocks.length}>{items.map((x, i) => <li key={i}>{inline(x)}</li>)}</ul>
      : <ol key={blocks.length}>{items.map((x, i) => <li key={i}>{inline(x)}</li>)}</ol>);
    list = null;
  };
  for (const raw of (text || "").split("\n")) {
    const l = raw.trim();
    let mm: RegExpMatchArray | null;
    if (!l) { flush(); continue; }
    if ((mm = l.match(/^#{1,4}\s+(.*)/))) { flush(); blocks.push(<h4 key={blocks.length}>{inline(mm[1])}</h4>); }
    else if ((mm = l.match(/^[-*•]\s+(.*)/))) { if (list?.kind !== "ul") { flush(); list = { kind: "ul", items: [] }; } list!.items.push(mm[1]); }
    else if ((mm = l.match(/^\d+[.)]\s+(.*)/))) { if (list?.kind !== "ol") { flush(); list = { kind: "ol", items: [] }; } list!.items.push(mm[1]); }
    else { flush(); blocks.push(<p key={blocks.length}>{inline(l)}</p>); }
  }
  flush();
  return <div className="md">{blocks}</div>;
}

export function Radar({ pillars }: { pillars: { short: string; color: number; target: number; score: number | null }[] }) {
  const n = pillars.length;
  if (n < 3) return null;
  const W = 320, H = 290, cx = 160, cy = 148, R = 98;
  const pt = (i: number, v: number) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    return [cx + Math.cos(a) * R * v / 5, cy + Math.sin(a) * R * v / 5] as const;
  };
  const poly = (f: (i: number) => number) => pillars.map((_, i) => pt(i, f(i)).join(",")).join(" ");
  return (
    <>
      <svg className="radar" viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: 340 }} role="img" aria-label="Current versus target maturity by pillar">
        {[1, 2, 3, 4, 5].map((r) => <polygon key={r} points={poly(() => r)} fill="none" stroke="var(--line)" />)}
        {pillars.map((_, i) => { const [x, y] = pt(i, 5); return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--line)" />; })}
        <polygon points={poly((i) => pillars[i].target)} fill="none" stroke="var(--ink2)" strokeDasharray="4 3" strokeWidth={1.5} />
        <polygon points={poly((i) => pillars[i].score || 0)} fill="var(--accent)" fillOpacity={0.22} stroke="var(--accent)" strokeWidth={2} />
        {pillars.map((p, i) => {
          const [x, y] = pt(i, p.score || 0);
          const [lx, ly] = pt(i, 6.1);
          return (
            <g key={i}>
              <circle cx={x} cy={y} r={3.5} fill={pillarColor(p.color)} />
              <text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle">{p.short}</text>
            </g>
          );
        })}
      </svg>
      <div className="legend" style={{ justifyContent: "center" }}>
        <span className="sw"><i style={{ background: "var(--accent)", opacity: 0.5 }} />Current</span>
        <span className="sw"><i style={{ border: "1.5px dashed var(--ink2)" }} />Target</span>
      </div>
    </>
  );
}

export function Trend({ points }: { points: { label: string; value: number | null; live?: boolean }[] }) {
  const W = 460, H = 150, px = 36, py = 18, n = points.length;
  const x = (i: number) => (n === 1 ? W / 2 : px + (i * (W - px * 2)) / (n - 1));
  const y = (v: number | null) => H - py - ((v || 0) / 5) * (H - py * 2);
  return (
    <svg className="trend" viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W }} role="img" aria-label="Enterprise maturity across published versions">
      {[0, 1, 2, 3, 4, 5].map((t) => (
        <g key={t}>
          <line x1={px - 8} x2={W - px + 8} y1={y(t)} y2={y(t)} stroke="var(--line)" />
          <text x={px - 14} y={y(t)} dominantBaseline="middle" textAnchor="end" style={{ fontSize: 9.5 }}>{t}</text>
        </g>
      ))}
      <path d={points.map((p, i) => `${i ? "L" : "M"}${x(i)} ${y(p.value)}`).join(" ")} fill="none" stroke="var(--accent)" strokeWidth={2} />
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={x(i)} cy={y(p.value)} r={p.live ? 5 : 3.5} fill={p.live ? "var(--accent)" : "var(--surface)"} stroke="var(--accent)" strokeWidth={2} />
          <text x={x(i)} y={H - 2} textAnchor="middle">{p.label}</text>
          <text x={x(i)} y={y(p.value) - 10} textAnchor="middle" style={{ fontFamily: "var(--f-mono)", fill: "var(--ink)" }}>{p.value == null ? "—" : p.value.toFixed(1)}</text>
        </g>
      ))}
    </svg>
  );
}

export function ActIcon({ kind }: { kind: string }) {
  const k = ({ interview: "interviews", evidence: "evidence", assessment: "assessment", report: "report", framework: "framework" } as Record<string, string>)[kind] || "scope";
  return <span className="av act">{Icons[k]}</span>;
}
