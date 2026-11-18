import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { KeyRound, LogOut, Trash2, UserCog } from "lucide-react";
import { Alert, Button, Card, Field, PageHead, ToggleCard, usePageTitle, useToast } from "../components/ui";
import { api, ApiError, setToken } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function Settings() {
  usePageTitle("Settings");
  const { user, setUser, logout } = useAuth(); const toast = useToast(); const nav = useNavigate();
  const [name, setName] = useState(user?.full_name ?? ""); const [alerts, setAlerts] = useState(!!user?.email_alerts_enabled);
  const [cur, setCur] = useState(""); const [nw, setNw] = useState(""); const [pwErr, setPwErr] = useState("");
  const [delPw, setDelPw] = useState(""); const [delErr, setDelErr] = useState("");
  const em = (x: unknown) => x instanceof ApiError ? (x.fieldErrors.map((f) => f.message).join(" · ") || x.message) : "Request failed.";

  async function saveProfile(e: FormEvent) { e.preventDefault(); try { setUser(await api.updateMe({ full_name: name, email_alerts_enabled: alerts })); toast("Profile saved", "ok"); } catch (x) { toast(em(x), "error"); } }
  async function changePw(e: FormEvent) { e.preventDefault(); setPwErr(""); try { await api.changePassword(cur, nw); setCur(""); setNw(""); toast("Password changed", "ok"); } catch (x) { setPwErr(em(x)); } }
  async function del() {
    setDelErr("");
    if (!window.confirm("Permanently delete your account and all assessments?")) return;
    try { await api.deleteAccount(delPw); setToken(null); setUser(null); nav("/"); } catch (x) { setDelErr(em(x)); }
  }

  return (
    <>
      <PageHead title="Settings" subtitle={user?.email} actions={<Button icon={<LogOut size={16} />} onClick={async () => { await logout(); nav("/"); }}>Sign out</Button>} />
      <div className="grid cols-2" style={{ alignItems: "start" }}>
        <Card large>
          <h3><UserCog size={18} color="#22d3ee" /> Profile</h3>
          <form className="stack" onSubmit={saveProfile}>
            <Field label="Full name" htmlFor="s-n"><input id="s-n" className="input" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} /></Field>
            <ToggleCard title="High-risk email alerts" help="Get an email (without health values) after a high-risk result" on={alerts} onClick={() => setAlerts(!alerts)} />
            <Button variant="primary" type="submit">Save changes</Button>
          </form>
        </Card>
        <Card large>
          <h3><KeyRound size={18} color="#a78bfa" /> Change password</h3>
          <form className="stack" onSubmit={changePw}>
            {pwErr && <Alert tone="error">{pwErr}</Alert>}
            <Field label="Current password" htmlFor="s-c"><input id="s-c" className="input" type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} required /></Field>
            <Field label="New password" htmlFor="s-p" hint="At least 8 characters with a letter and a number."><input id="s-p" className="input" type="password" autoComplete="new-password" value={nw} onChange={(e) => setNw(e.target.value)} required /></Field>
            <Button type="submit">Update password</Button>
          </form>
        </Card>
        <Card large style={{ borderColor: "rgba(251,113,133,.35)" }}>
          <h3><Trash2 size={18} color="#fb7185" /> Delete account</h3>
          <p style={{ fontSize: 14 }}>Removes your account and every saved assessment. This cannot be undone.</p>
          <div className="stack">
            {delErr && <Alert tone="error">{delErr}</Alert>}
            <Field label="Confirm with your password" htmlFor="s-d"><input id="s-d" className="input" type="password" autoComplete="current-password" value={delPw} onChange={(e) => setDelPw(e.target.value)} /></Field>
            <Button variant="danger" disabled={!delPw} onClick={del}>Delete my account</Button>
          </div>
        </Card>
      </div>
    </>
  );
}
