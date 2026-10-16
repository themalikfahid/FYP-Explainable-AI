import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, setToken } from "../api";
import { useAuth } from "../auth";

export default function Settings() {
  const { user, setUser } = useAuth();
  const nav = useNavigate();
  const [name, setName] = useState(user?.full_name ?? "");
  const [msg, setMsg] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const [pw, setPw] = useState({ current: "", next: "" });
  const [delPw, setDelPw] = useState("");

  const fail = (e: unknown) => setMsg({ kind: "error", text: e instanceof ApiError ? e.message : "Something went wrong." });

  async function saveProfile(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) { setMsg({ kind: "error", text: "Name can't be empty." }); return; }
    try { setUser(await api.updateMe({ full_name: name.trim() })); setMsg({ kind: "info", text: "Name saved." }); } catch (e) { fail(e); }
  }
  async function toggleAlerts() {
    try {
      const u = await api.updateMe({ email_alerts_enabled: !user!.email_alerts_enabled });
      setUser(u);
      setMsg({ kind: "info", text: u.email_alerts_enabled ? "High-risk email alerts turned on." : "High-risk email alerts turned off." });
    } catch (e) { fail(e); }
  }
  async function changePw(e: FormEvent) {
    e.preventDefault();
    if (pw.next.length < 8 || !/[A-Za-z]/.test(pw.next) || !/\d/.test(pw.next)) {
      setMsg({ kind: "error", text: "New password needs 8+ characters with a letter and a number." }); return;
    }
    try {
      await api.changePassword(pw.current, pw.next);
      setToken(null); setUser(null);
      nav("/login", { state: { message: "Password changed. Log in with your new password." } });
    } catch (e) { fail(e); }
  }
  async function deleteAccount(e: FormEvent) {
    e.preventDefault();
    if (!window.confirm("Delete your account and every saved assessment permanently?")) return;
    try {
      await api.deleteAccount(delPw);
      setToken(null); setUser(null);
      nav("/", { replace: true });
    } catch (e) { fail(e); }
  }

  if (!user) return null;
  return (
    <div className="page narrow">
      <h1>Account</h1>
      {msg && <p className={`banner ${msg.kind}`} role={msg.kind === "error" ? "alert" : "status"}>{msg.text}</p>}
      <section className="panel">
        <h2>Profile</h2>
        <form onSubmit={saveProfile} className="row-form">
          <div className="field"><label htmlFor="name">Full name</label>
            <input id="name" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} /></div>
          <div className="field"><label htmlFor="em">Email</label><input id="em" value={user.email} disabled /></div>
          <button className="btn">Save name</button>
        </form>
      </section>
      <section className="panel">
        <h2>Email alerts</h2>
        <p>When an assessment is rated high risk, we can email you a short note asking you to sign in. The email never contains your results.</p>
        <label className="check-line"><input type="checkbox" checked={user.email_alerts_enabled} onChange={toggleAlerts} />
          Send me high-risk alerts</label>
      </section>
      <section className="panel">
        <h2>Change password</h2>
        <form onSubmit={changePw} className="row-form">
          <div className="field"><label htmlFor="cur">Current password</label>
            <input id="cur" type="password" autoComplete="current-password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} /></div>
          <div className="field"><label htmlFor="new">New password</label>
            <input id="new" type="password" autoComplete="new-password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} /></div>
          <button className="btn">Change password</button>
        </form>
      </section>
      <section className="panel danger-zone">
        <h2>Delete account</h2>
        <p>This permanently removes your account, all saved assessments and reports.</p>
        <form onSubmit={deleteAccount} className="row-form">
          <div className="field"><label htmlFor="delpw">Confirm with your password</label>
            <input id="delpw" type="password" autoComplete="current-password" value={delPw} onChange={(e) => setDelPw(e.target.value)} /></div>
          <button className="btn danger" disabled={!delPw}>Delete my account</button>
        </form>
      </section>
    </div>
  );
}
