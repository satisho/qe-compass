import type { Confidence, EntityType, Status } from "../types";

export const fmt = (v: number | null | undefined) => (v == null || Number.isNaN(v) ? "—" : v.toFixed(1));
export const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}`);
export const cellText = (s: number | null | undefined) => (s == null ? "·" : Number.isInteger(s) ? String(s) : s.toFixed(1));
export const heatClass = (s: number | null | undefined) =>
  s == null ? "cnull" : `c${Math.max(1, Math.min(5, Math.round(s)))}`;

export const ETYPE: Record<EntityType, string> = { lob: "Line of business", program: "Program", app: "Application" };
export const ESHORT: Record<EntityType, string> = { lob: "LOB", program: "Program", app: "App" };
export const CONF: Record<Confidence, string> = { low: "Low", med: "Medium", high: "High" };
export const STATUS_LABEL: Record<Status, string> = {
  gap: "Potential gap",
  partial: "Partial capability",
  val: "To be validated",
  strong: "Strength",
};
export const STATUS_DESC: Record<Status, string> = {
  gap: "Early evidence indicates material improvement opportunity",
  partial: "Capability evident; consistency to be validated",
  val: "Insufficient evidence to form a hypothesis",
  strong: "Repeatable, measured practice",
};
export const HORIZON: Record<string, [string, string]> = {
  now: ["Now", "0–3 months · quick wins"],
  next: ["Next", "3–9 months · scale foundations"],
  later: ["Later", "9–18 months · future-ready QE"],
};

export const pillarColor = (color: number) => `var(--p${(((color % 7) + 7) % 7) + 1})`;

/* Server timestamps are UTC. SQLite returns them without a zone, so treat a zone-less date-time as UTC. */
export function ts(s: string): Date {
  return new Date(/T\d{2}:\d{2}/.test(s) && !/(Z|[+-]\d{2}:?\d{2})$/.test(s) ? `${s}Z` : s);
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return "";
  const t = ts(iso).getTime();
  const d = (Date.now() - t) / 1000;
  if (d < 60) return "just now";
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  if (d < 86400 * 6) return `${Math.floor(d / 86400)}d ago`;
  return new Date(t).toLocaleDateString("en-CA", { month: "short", day: "numeric" });
}

export function fdate(s: string | null | undefined): string {
  if (!s) return "";
  const d = s.length === 10 ? new Date(`${s}T12:00:00`) : ts(s);
  return Number.isNaN(d.getTime()) ? s : d.toLocaleDateString("en-CA", { month: "short", day: "numeric", year: "numeric" });
}

export function fdatetime(s: string): string {
  return ts(s).toLocaleString("en-CA", { dateStyle: "medium", timeStyle: "short" });
}

export const today = () => new Date().toISOString().slice(0, 10);

export function weekOf(start: string, weeks: number): number {
  const s = new Date(`${start}T00:00:00`).getTime();
  const w = Math.floor((Date.now() - s) / (7 * 864e5)) + 1;
  return Math.max(1, Math.min(weeks, w));
}

export const PHASES: [number, number, string, string][] = [
  [1, 1, "Planning", "Kickoff, scope, SPOC"],
  [2, 3, "Interviews / Data Gathering", "LOBs, programs, applications"],
  [5, 1, "Analysis", "Scoring & maturity maps"],
  [6, 1, "Findings", "Recommendations"],
  [7, 2, "Readout & Signoff", "Executive readout"],
];

export function phaseAt(week: number): string {
  const p = PHASES.find(([s, n]) => week >= s && week < s + n);
  return p ? p[2] : PHASES[PHASES.length - 1][2];
}

export const plural = (n: number, word: string, many = `${word}s`) => `${n} ${n === 1 ? word : many}`;
export const cap = (t: string) => (t ? t.charAt(0).toUpperCase() + t.slice(1) : t);
export const bytes = (n: number) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
