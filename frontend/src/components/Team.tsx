import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../lib/auth";
import { base, useDirectoryList, useMut } from "../lib/workspace";

const ROLE: Record<string, string> = { admin: "Administrator", assessor: "Assessor", viewer: "Viewer" };

/** Who can open this engagement. Administrators and the creator always can. */
export function EngagementTeam({ eid }: { eid: number }) {
  const { canWrite } = useAuth();
  const dir = useDirectoryList().data || [];
  const q = useQuery({ queryKey: ["members", eid], queryFn: () => api.get<{ created_by: number | null; members: number[] }>(`${base(eid)}/members`) });
  const [pick, setPick] = useState("");
  const add = useMut(eid, (user_id: number) => api.post(`${base(eid)}/members`, { user_id }), { also: ["members"], success: "Access granted", onSuccess: () => setPick("") });
  const remove = useMut(eid, (uid: number) => api.del(`${base(eid)}/members/${uid}`), { also: ["members"], success: "Access removed" });
  if (!q.data) return null;
  const { created_by, members } = q.data;
  const why = (u: { id: number; role: string }) =>
    u.role === "admin" ? "Always has access" : u.id === created_by ? "Created this engagement" : members.includes(u.id) ? "Member" : null;
  const withAccess = dir.filter((u) => u.active && why(u));
  const addable = dir.filter((u) => u.active && !why(u));
  return (
    <section className="card pad">
      <div className="sec-h"><div><h2>Engagement team</h2><p>Only these people can open this engagement. Administrators always can.</p></div></div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {withAccess.map((u) => (
          <div key={u.id} className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap", padding: "6px 10px", background: "var(--surface2)", borderRadius: 8 }}>
            <span><b>{u.name}</b> <span className="small muted">· {ROLE[u.role] || u.role} · {why(u)}</span></span>
            {canWrite && members.includes(u.id) && u.role !== "admin" && u.id !== created_by && (
              <button className="btn sm ghost" onClick={() => remove.mutate(u.id)} aria-label={`Remove ${u.name}`}>Remove</button>
            )}
          </div>
        ))}
      </div>
      {canWrite && addable.length > 0 && (
        <div className="row" style={{ marginTop: 12 }}>
          <select className="inp" style={{ width: "auto", minWidth: 220 }} aria-label="Add a person" value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">Add a person…</option>
            {addable.map((u) => <option key={u.id} value={u.id}>{u.name} · {ROLE[u.role] || u.role}</option>)}
          </select>
          <button className="btn" disabled={!pick || add.isPending} onClick={() => add.mutate(Number(pick))}>Give access</button>
        </div>
      )}
    </section>
  );
}
