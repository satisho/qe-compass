import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Compass } from "../components/icons";
import type { User } from "../types";

export function Login() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["setup-status"], queryFn: () => api.get<{ needs_setup: boolean }>("/api/auth/status") });
  const setup = status.data?.needs_setup;
  const [f, setF] = useState({ name: "", email: "", password: "", confirm: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    if (setup && f.password !== f.confirm) return setErr("Passwords don’t match.");
    setBusy(true);
    try {
      const user = setup
        ? await api.post<User>("/api/auth/setup", { name: f.name, email: f.email, password: f.password })
        : await api.post<User>("/api/auth/login", { email: f.email, password: f.password });
      qc.setQueryData(["me"], user);
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
        <h1>{setup ? "Create the administrator account" : "Sign in"}</h1>
        {setup && <p className="small muted" style={{ margin: 0 }}>This is a new installation. The first account becomes the administrator, who can then add assessors and viewers.</p>}
        {setup && (
          <div className="field"><label htmlFor="su-name">Your name</label><input className="inp" id="su-name" value={f.name} onChange={set("name")} required autoFocus /></div>
        )}
        <div className="field"><label htmlFor="li-email">Email</label><input className="inp" id="li-email" type="email" autoComplete="username" value={f.email} onChange={set("email")} required autoFocus={!setup} /></div>
        <div className="field"><label htmlFor="li-pw">Password</label><input className="inp" id="li-pw" type="password" autoComplete={setup ? "new-password" : "current-password"} value={f.password} onChange={set("password")} required /></div>
        {setup && (
          <>
            <div className="field"><label htmlFor="su-pw2">Repeat password</label><input className="inp" id="su-pw2" type="password" autoComplete="new-password" value={f.confirm} onChange={set("confirm")} required /></div>
            <span className="small muted">At least 10 characters, with upper- and lower-case letters and a number.</span>
          </>
        )}
        {err && <div className="err-msg" role="alert">{err}</div>}
        <button className="btn primary" type="submit" disabled={busy || status.isLoading} style={{ justifyContent: "center", padding: "10px" }}>
          {busy ? <span className="spin" /> : setup ? "Create account and continue" : "Sign in"}
        </button>
        {!setup && <span className="small muted">Forgot your password? Ask an administrator to reset it.</span>}
      </form>
    </div>
  );
}
