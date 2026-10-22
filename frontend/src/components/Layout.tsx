import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../lib/auth";
import { phaseAt, weekOf } from "../lib/format";
import { useEvidence, useInterviews, useSnapshots, useWorkspace } from "../lib/workspace";
import type { Engagement } from "../types";
import { Compass, Icons } from "./icons";

const RUN = [
  ["overview", "Command Center"],
  ["interviews", "Interviews"],
  ["evidence", "Evidence Library"],
  ["assessment", "Assessment"],
  ["analyst", "AI Analyst"],
] as const;
const OUT = [["heatmap", "Maturity Map"], ["dashboards", "Dashboards"]] as const;
const CONF = [["scope", "Scope & Entities"], ["framework", "Framework"]] as const;

function EngagementNav({ eid }: { eid: number }) {
  const iv = useInterviews(eid).data?.length;
  const ev = useEvidence(eid).data?.length;
  const sn = useSnapshots(eid).data?.length;
  const counts: Record<string, number | undefined> = { interviews: iv, evidence: ev, dashboards: sn };
  const link = (to: string, label: string) => (
    <NavLink key={to} to={`/e/${eid}/${to}`} className={({ isActive }) => (isActive ? "active" : "")}>
      {Icons[to === "dashboards" ? "report" : to]}
      <span className="lb">{label}</span>
      {to === "analyst" ? <span className="tag">AI</span> : counts[to] ? <span className="cnt">{counts[to]}</span> : null}
    </NavLink>
  );
  return (
    <>
      <div className="navgrp">Run the assessment</div>
      {RUN.map(([t, l]) => link(t, l))}
      <div className="navgrp">Outputs</div>
      {OUT.map(([t, l]) => link(t, l))}
      <div className="navgrp">Configure</div>
      {CONF.map(([t, l]) => link(t, l))}
    </>
  );
}

export function Layout() {
  const { user, isAdmin, signOut } = useAuth();
  const { eid: eidParam } = useParams();
  const eid = eidParam ? Number(eidParam) : null;
  const nav = useNavigate();
  const engs = useQuery({ queryKey: ["engagements"], queryFn: () => api.get<Engagement[]>("/api/engagements") });
  return (
    <div className="app">
      <aside className="side">
        <div className="brand">
          <Compass />
          <div><b>QE Compass</b><small>Assessment workspace</small></div>
        </div>
        {eid != null && (
          <select className="engsel" aria-label="Engagement" value={eid}
            onChange={(e) => nav(e.target.value === "all" ? "/" : `/e/${e.target.value}/overview`)}>
            {(engs.data || []).map((e) => <option key={e.id} value={e.id}>{e.client} · {e.title}</option>)}
            <option value="all">All engagements…</option>
          </select>
        )}
        <nav className="nav">
          {eid != null ? <EngagementNav eid={eid} /> : (
            <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>{Icons.engagements}<span className="lb">Engagements</span></NavLink>
          )}
          <div className="navgrp">Workspace</div>
          {eid != null && <NavLink to="/" end>{Icons.engagements}<span className="lb">All engagements</span></NavLink>}
          {isAdmin && <NavLink to="/admin/users" className={({ isActive }) => (isActive ? "active" : "")}>{Icons.users}<span className="lb">Users</span></NavLink>}
          <NavLink to="/account" className={({ isActive }) => (isActive ? "active" : "")}>{Icons.account}<span className="lb">My account</span></NavLink>
        </nav>
        <div className="side-foot">
          <div className="userbox">
            <span className="av" style={{ background: "var(--accent)" }}>{(user?.name || "?").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase()}</span>
            <div><b>{user?.name}</b><small>{user?.role}</small></div>
            <button className="linkbtn" onClick={() => signOut().then(() => nav("/"))}>Sign out</button>
          </div>
          <div>Navigating IT Transformation with Quality as the Compass</div>
        </div>
      </aside>
      <main className="main"><Outlet /></main>
    </div>
  );
}

/** Page frame: top bar with title, subtitle and the engagement's week chip. */
export function Page({ title, sub, eid, actions, children }: {
  title: string; sub?: ReactNode; eid?: number; actions?: ReactNode; children: ReactNode;
}) {
  const ws = useWorkspace(eid || 0);
  const { canWrite } = useAuth();
  const eng = eid ? ws.data?.engagement : undefined;
  const wk = eng ? weekOf(eng.start_date, eng.weeks) : 0;
  return (
    <>
      <div className="top">
        <div style={{ minWidth: 0 }}><h1>{title}</h1>{sub && <div className="sub">{sub}</div>}</div>
        <div className="chips">
          {actions}
          {eng && <span className="chip live">Week {wk} of {eng.weeks} · {phaseAt(wk)}</span>}
          {!canWrite && <span className="chip">View only</span>}
        </div>
      </div>
      <div className="view">{children}</div>
    </>
  );
}
