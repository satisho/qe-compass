import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Page } from "../components/Layout";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";

export function Account({ forced }: { forced?: boolean }) {
  const { user, refresh } = useAuth();
  const toast = useToast();
  const [f, setF] = useState({ current: "", next: "", confirm: "" });
  const [err, setErr] = useState("");
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    if (f.next !== f.confirm) return setErr("New passwords don’t match.");
    try {
      await api.post("/api/auth/change-password", { current_password: f.current, new_password: f.next });
      toast("Password changed");
      setF({ current: "", next: "", confirm: "" });
      refresh();
    } catch (x) {
      setErr((x as Error).message);
    }
  };
  return (
    <Page title="My account" sub={`${user?.name} · ${user?.email} · ${user?.role}`}>
      {forced && <div className="notice">Choose a new password to continue. Your administrator set a temporary one.</div>}
      <section className="card pad" style={{ maxWidth: 560 }}>
        <div className="sec-h"><div><h2>Change password</h2><p>Signing in elsewhere ends when you change it</p></div></div>
        <form style={{ display: "flex", flexDirection: "column", gap: 12 }} onSubmit={submit}>
          <div className="field"><label htmlFor="cp-cur">Current password</label><input className="inp" id="cp-cur" type="password" autoComplete="current-password" required value={f.current} onChange={(e) => setF({ ...f, current: e.target.value })} /></div>
          <div className="field"><label htmlFor="cp-new">New password</label><input className="inp" id="cp-new" type="password" autoComplete="new-password" required value={f.next} onChange={(e) => setF({ ...f, next: e.target.value })} /><span className="small muted">10+ characters with upper- and lower-case letters and a number</span></div>
          <div className="field"><label htmlFor="cp-new2">Repeat new password</label><input className="inp" id="cp-new2" type="password" autoComplete="new-password" required value={f.confirm} onChange={(e) => setF({ ...f, confirm: e.target.value })} /></div>
          {err && <div className="err-msg" role="alert">{err}</div>}
          <div><button className="btn primary" type="submit">Change password</button></div>
        </form>
      </section>
    </Page>
  );
}
