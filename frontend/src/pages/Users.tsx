import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../api";
import { Page } from "../components/Layout";
import { Drawer, Loading } from "../components/ui";
import { useAuth } from "../lib/auth";
import { ago } from "../lib/format";
import { useToast } from "../lib/toast";
import type { Role, SecurityEvent, User } from "../types";

const ROLE_DESC: Record<Role, string> = {
  admin: "Everything, plus users and deleting engagements",
  assessor: "Captures interviews, evidence and scores; edits scope and framework; publishes dashboards",
  viewer: "Reads everything and uses the AI Analyst; cannot change data",
};

export function Users() {
  const { isAdmin, user: me } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["users"], queryFn: () => api.get<User[]>("/api/users"), enabled: isAdmin });
  const [nf, setNf] = useState({ name: "", email: "", role: "assessor" as Role, password: "" });
  const [reset, setReset] = useState<{ user: User; password: string } | null>(null);
  const done = (msg: string) => { qc.invalidateQueries({ queryKey: ["users"] }); qc.invalidateQueries({ queryKey: ["directory"] }); toast(msg); };
  const create = useMutation({ mutationFn: () => api.post<User>("/api/users", nf), onSuccess: (u) => { done(`${u.name} added. Share the temporary password with them directly.`); setNf({ name: "", email: "", role: "assessor", password: "" }); }, onError: (e: Error) => toast(e.message, "error") });
  const update = useMutation({ mutationFn: ({ id, ...b }: { id: number; role?: Role; active?: boolean }) => api.patch(`/api/users/${id}`, b), onSuccess: () => done("User updated"), onError: (e: Error) => toast(e.message, "error") });
  const resetMfa = useMutation({ mutationFn: (u: User) => api.post(`/api/users/${u.id}/reset-mfa`), onSuccess: () => done("Two-step verification reset. They can set it up again at next sign-in."), onError: (e: Error) => toast(e.message, "error") });
  const doReset = useMutation({ mutationFn: () => api.post(`/api/users/${reset!.user.id}/reset-password`, { password: reset!.password }), onSuccess: () => { done("Password reset. They’ll choose a new one at next sign-in."); setReset(null); }, onError: (e: Error) => toast(e.message, "error") });

  if (!isAdmin) return <Navigate to="/" replace />;
  const submit = (e: FormEvent) => { e.preventDefault(); create.mutate(); };
  return (
    <Page title="Users" sub="Who can sign in to this installation, and what they can do">
      <section className="card">
        {!q.data ? <Loading /> : (
          <div className="tbl-wrap"><table>
            <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Two-step</th><th>Last sign-in</th><th /></tr></thead>
            <tbody>{q.data.map((u) => (
              <tr key={u.id}>
                <td><b>{u.name}</b>{u.id === me?.id && <span className="muted small"> (you)</span>}</td>
                <td className="small">{u.email}</td>
                <td><select className="inp" style={{ width: "auto" }} value={u.role} aria-label={`Role for ${u.name}`} onChange={(e) => update.mutate({ id: u.id, role: e.target.value as Role })}>
                  <option value="admin">Administrator</option><option value="assessor">Assessor</option><option value="viewer">Viewer</option></select></td>
                <td>{u.active ? <span className="badge ok">Active</span> : <span className="badge err">Deactivated</span>}{u.must_change_password && <> <span className="badge warn">Must change password</span></>}</td>
                <td>{u.mfa_enabled ? <span className="badge ok">On</span> : <span className="badge">Off</span>}</td>
                <td className="small muted">{u.last_login_at ? ago(u.last_login_at) : "Never"}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <button className="btn sm" onClick={() => setReset({ user: u, password: "" })}>Reset password</button>{" "}
                  {u.mfa_enabled && u.id !== me?.id && <><button className="btn sm" onClick={() => resetMfa.mutate(u)}>Reset two-step</button>{" "}</>}
                  {u.id !== me?.id && <button className="btn sm" onClick={() => update.mutate({ id: u.id, active: !u.active })}>{u.active ? "Deactivate" : "Reactivate"}</button>}
                </td>
              </tr>))}</tbody>
          </table></div>
        )}
      </section>
      <section className="card pad">
        <div className="sec-h"><div><h2>Add a user</h2><p>They sign in with this temporary password and must choose their own on first sign-in</p></div></div>
        <form className="fgrid" onSubmit={submit}>
          <div className="field"><label htmlFor="nu-name">Name</label><input className="inp" id="nu-name" required value={nf.name} onChange={(e) => setNf({ ...nf, name: e.target.value })} /></div>
          <div className="field"><label htmlFor="nu-email">Email</label><input className="inp" id="nu-email" type="email" required value={nf.email} onChange={(e) => setNf({ ...nf, email: e.target.value })} /></div>
          <div className="field"><label htmlFor="nu-role">Role</label>
            <select className="inp" id="nu-role" value={nf.role} onChange={(e) => setNf({ ...nf, role: e.target.value as Role })}>
              <option value="assessor">Assessor</option><option value="viewer">Viewer</option><option value="admin">Administrator</option></select>
            <span className="small muted">{ROLE_DESC[nf.role]}</span></div>
          <div className="field"><label htmlFor="nu-pw">Temporary password</label><input className="inp" id="nu-pw" type="text" autoComplete="off" required value={nf.password} onChange={(e) => setNf({ ...nf, password: e.target.value })} />
            <span className="small muted">10+ characters with upper- and lower-case letters and a number</span></div>
          <div className="field full" style={{ alignItems: "flex-end" }}><button className="btn primary" type="submit" disabled={create.isPending}>Add user</button></div>
        </form>
      </section>
      <SecurityLog />
      {reset && (
        <Drawer title={`Reset password · ${reset.user.name}`} onClose={() => setReset(null)}
          footer={<><button className="btn" onClick={() => setReset(null)}>Cancel</button><button className="btn primary" disabled={!reset.password || doReset.isPending} onClick={() => doReset.mutate()}>Reset password</button></>}>
          <div className="field"><label htmlFor="rp-pw">Temporary password</label><input className="inp" id="rp-pw" autoFocus type="text" autoComplete="off" value={reset.password} onChange={(e) => setReset({ ...reset, password: e.target.value })} /></div>
          <p className="small muted">This signs them out everywhere. They must choose a new password at next sign-in.</p>
        </Drawer>
      )}
    </Page>
  );
}

const KINDS: [string, string][] = [
  ["", "All events"], ["login_failed", "Failed sign-ins"], ["login_blocked", "Blocked sign-ins"], ["login_success", "Sign-ins"],
  ["user_updated", "User changes"], ["member_added", "Access granted"], ["data_export", "Exports"],
];

function SecurityLog() {
  const [kind, setKind] = useState("");
  const q = useQuery({
    queryKey: ["security-events", kind],
    queryFn: () => api.get<SecurityEvent[]>(`/api/security-events?limit=200${kind ? `&kind=${kind}` : ""}`),
    refetchInterval: 30_000,
  });
  return (
    <section className="card">
      <div className="sec-h" style={{ padding: "16px 16px 0" }}>
        <div><h2>Security log</h2><p>Sign-ins, account and access changes, and exports. Kept permanently; also written to the server log.</p></div>
        <select className="inp" style={{ width: "auto" }} aria-label="Filter events" value={kind} onChange={(e) => setKind(e.target.value)}>
          {KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </div>
      {!q.data ? <Loading /> : !q.data.length ? <p className="small muted" style={{ padding: 16 }}>No events.</p> : (
        <div className="tbl-wrap" style={{ maxHeight: 420, overflow: "auto" }}><table>
          <thead><tr><th>When</th><th>Event</th><th>Account</th><th>Address</th><th>Detail</th></tr></thead>
          <tbody>{q.data.map((e) => (
            <tr key={e.id}>
              <td className="small" style={{ whiteSpace: "nowrap" }} title={new Date(e.created_at).toLocaleString()}>{ago(e.created_at)}</td>
              <td className="small"><span className={`badge ${/failed|blocked|rejected/.test(e.kind) ? "warn" : ""}`}>{e.label}</span></td>
              <td className="small">{e.email || "—"}</td>
              <td className="small mono muted">{e.ip || "—"}</td>
              <td className="small muted">{e.detail}</td>
            </tr>))}</tbody>
        </table></div>
      )}
    </section>
  );
}
