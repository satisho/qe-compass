import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Page } from "../components/Layout";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";

export function Account({ forced }: { forced?: "password" | "mfa" }) {
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
      {forced === "password" && <div className="notice">Choose a new password to continue. Your administrator set a temporary one.</div>}
      {forced === "mfa" && <div className="notice">This installation requires two-step verification. Set it up below to continue.</div>}
      {forced !== "mfa" && (
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
      )}
      {forced !== "password" && <TwoStep />}
    </Page>
  );
}

function TwoStep() {
  const { user, refresh } = useAuth();
  const toast = useToast();
  const [setup, setSetup] = useState<{ secret: string; qr_svg: string } | null>(null);
  const [code, setCode] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<void>) => {
    setErr("");
    setBusy(true);
    try { await fn(); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };
  const start = () => run(async () => { setSetup(await api.post("/api/auth/mfa/setup")); setCode(""); });
  const enable = (e: FormEvent) => { e.preventDefault(); void run(async () => { await api.post("/api/auth/mfa/enable", { code }); setSetup(null); toast("Two-step verification is on"); refresh(); }); };
  const disable = (e: FormEvent) => { e.preventDefault(); void run(async () => { await api.post("/api/auth/mfa/disable", { password: pw }); setPw(""); toast("Two-step verification is off"); refresh(); }); };

  return (
    <section className="card pad" style={{ maxWidth: 560, display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="sec-h"><div><h2>Two-step verification</h2><p>A 6-digit code from an authenticator app on your phone, as well as your password</p></div>
        {user?.mfa_enabled ? <span className="badge ok">On</span> : <span className="badge">Off</span>}</div>
      {user?.mfa_enabled ? (
        user.require_mfa ? <p className="small muted" style={{ margin: 0 }}>Required for everyone on this installation. If you lose your phone, an administrator can reset it.</p> : (
          <form className="row" style={{ alignItems: "flex-end" }} onSubmit={disable}>
            <div className="field" style={{ flex: 1 }}><label htmlFor="mfa-pw">Your password, to turn it off</label><input className="inp" id="mfa-pw" type="password" autoComplete="current-password" required value={pw} onChange={(e) => setPw(e.target.value)} /></div>
            <button className="btn" type="submit" disabled={busy}>Turn off</button>
          </form>
        )
      ) : !setup ? (
        <div><button className="btn primary" onClick={start} disabled={busy}>Set up two-step verification</button></div>
      ) : (
        <form style={{ display: "flex", flexDirection: "column", gap: 12 }} onSubmit={enable}>
          <ol className="small" style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 4 }}>
            <li>Open an authenticator app (Microsoft Authenticator, Google Authenticator or similar).</li>
            <li>Scan this code, or enter the key by hand.</li>
            <li>Type the 6-digit code the app shows.</li>
          </ol>
          <div className="row" style={{ gap: 16, alignItems: "center" }}>
            <img src={setup.qr_svg} alt="QR code for your authenticator app" width={170} height={170} style={{ background: "#fff", borderRadius: 8 }} />
            <div className="field" style={{ minWidth: 0, flex: 1 }}><span className="lbl">Key</span><code className="mono small" style={{ wordBreak: "break-all" }}>{setup.secret.replace(/(.{4})/g, "$1 ").trim()}</code></div>
          </div>
          <div className="field"><label htmlFor="mfa-code">6-digit code</label><input className="inp mono" id="mfa-code" inputMode="numeric" autoComplete="one-time-code" maxLength={7} required autoFocus value={code} onChange={(e) => setCode(e.target.value.replace(/[^0-9 ]/g, ""))} style={{ maxWidth: 180, fontSize: 18, letterSpacing: 3 }} /></div>
          <div className="row"><button className="btn primary" type="submit" disabled={busy}>Turn on</button><button className="btn" type="button" onClick={() => setSetup(null)}>Cancel</button></div>
        </form>
      )}
      {err && <div className="err-msg" role="alert">{err}</div>}
    </section>
  );
}
