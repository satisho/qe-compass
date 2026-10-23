import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Compass } from "../components/icons";
import { useAuth } from "../lib/auth";
import type { Me } from "../types";

export function Login() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["setup-status"], queryFn: () => api.get<{ needs_setup: boolean }>("/api/auth/status") });
  const setup = status.data?.needs_setup;
  const [f, setF] = useState({ name: "", email: "", password: "", confirm: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState<string | null>(null); // two-step step: null = not asked yet
  const { endedReason } = useAuth();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    if (setup && f.password !== f.confirm) return setErr("Passwords don’t match.");
    setBusy(true);
    try {
      const r = setup
        ? await api.post<Me>("/api/auth/setup", { name: f.name, email: f.email, password: f.password })
        : await api.post<Me | { mfa_required: true }>("/api/auth/login", { email: f.email, password: f.password, ...(code != null ? { code } : {}) });
      if ("mfa_required" in r) {
        setCode("");
        return;
      }
      qc.setQueryData(["me"], r);
    } catch (x) {
      setErr((x as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand"><Compass /><div><b>QE Compass</b><small>Enterprise QE assessment platform</small></div></div>
        <h1>{setup ? "Create the administrator account" : code != null ? "Two-step verification" : "Sign in"}</h1>
        {!setup && endedReason && code == null && <div className="notice" role="status">{endedReason}</div>}
        {setup && <p className="small muted" style={{ margin: 0 }}>This is a new installation. The first account becomes the administrator, who can then add assessors and viewers.</p>}
        {setup && (
          <div className="field"><label htmlFor="su-name">Your name</label><input className="inp" id="su-name" value={f.name} onChange={set("name")} required autoFocus /></div>
        )}
        {code != null ? (
          <div className="field"><label htmlFor="li-code">6-digit code from your authenticator app</label>
            <input className="inp mono" id="li-code" inputMode="numeric" autoComplete="one-time-code" maxLength={7} autoFocus required
              value={code} onChange={(e) => setCode(e.target.value.replace(/[^0-9 ]/g, ""))} style={{ fontSize: 20, letterSpacing: 4 }} />
          </div>
        ) : <>
        <div className="field"><label htmlFor="li-email">Email</label><input className="inp" id="li-email" type="email" autoComplete="username" value={f.email} onChange={set("email")} required autoFocus={!setup} /></div>
        <div className="field"><label htmlFor="li-pw">Password</label><input className="inp" id="li-pw" type="password" autoComplete={setup ? "new-password" : "current-password"} value={f.password} onChange={set("password")} required /></div>
        </>}
        {setup && (
          <>
            <div className="field"><label htmlFor="su-pw2">Repeat password</label><input className="inp" id="su-pw2" type="password" autoComplete="new-password" value={f.confirm} onChange={set("confirm")} required /></div>
            <span className="small muted">At least 10 characters, with upper- and lower-case letters and a number.</span>
          </>
        )}
        {err && <div className="err-msg" role="alert">{err}</div>}
        <button className="btn primary" type="submit" disabled={busy || status.isLoading} style={{ justifyContent: "center", padding: "10px" }}>
          {busy ? <span className="spin" /> : setup ? "Create account and continue" : code != null ? "Verify" : "Sign in"}
        </button>
        {code != null && <button type="button" className="linkbtn" onClick={() => { setCode(null); setErr(""); }}>Back</button>}
        {!setup && code == null && <span className="small muted">Forgot your password? Ask an administrator to reset it.</span>}
        {code != null && <span className="small muted">Lost your phone? Ask an administrator to reset two-step verification.</span>}
      </form>
    </div>
  );
}
