import { lazy, useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Lock, Mail, ShieldCheck, User as UserIcon } from "lucide-react";
import { Brand } from "../components/layout/Brand";
import SceneFrame from "../components/three/SceneFrame";
import { Alert, Button, Card, Field, usePageTitle } from "../components/ui";
import { api, ApiError, setToken } from "../lib/api";
import { useAuth } from "../lib/auth";

const AuthScene = lazy(() => import("../components/three/Shapes").then((m) => ({ default: m.AuthScene })));

function Shell({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <main id="main" className="auth-wrap">
      <div className="auth-visual">
        <div className="canvas"><SceneFrame camera={[0, 0, 7]}><AuthScene /></SceneFrame></div>
        <div style={{ position: "relative", maxWidth: 420 }}>
          <Brand />
          <h2 style={{ marginTop: 18 }}>AI that shows its <span className="grad-text">working</span>.</h2>
          <p>Every risk score comes with the factors behind it, a confidence level and clear next steps.</p>
          <div className="row faint" style={{ gap: 18, fontSize: 13 }}><span className="row" style={{ gap: 6 }}><ShieldCheck size={15} /> Encrypted passwords</span><span className="row" style={{ gap: 6 }}><Lock size={15} /> Owner-only records</span></div>
        </div>
      </div>
      <div className="auth-panel">
        <motion.div className="auth-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5 }}>
          <Card large glow>
            <h1 style={{ fontSize: "2rem" }}>{title}</h1>
            <p>{subtitle}</p>
            {children}
          </Card>
        </motion.div>
      </div>
    </main>
  );
}

export function Login() {
  usePageTitle("Sign in");
  const { user, login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as { state?: { from?: string; registered?: boolean } };
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/app" replace />;
  async function submit(e: FormEvent) {
    e.preventDefault(); setErr(""); setBusy(true);
    try { await login(email.trim(), password); nav(loc.state?.from ?? "/app", { replace: true }); }
    catch (x) { setErr(x instanceof ApiError ? x.message : "Sign-in failed."); setToken(null); }
    finally { setBusy(false); }
  }
  return (
    <Shell title="Welcome back" subtitle="Sign in to see your dashboard and past assessments.">
      <form className="stack" onSubmit={submit} noValidate>
        {loc.state?.registered && <Alert tone="ok">Account created. Please sign in.</Alert>}
        {err && <Alert tone="error">{err}</Alert>}
        <Field label="Email" htmlFor="email"><div className="input-wrap"><input id="email" className="input" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="you@example.com" /></div></Field>
        <Field label="Password" htmlFor="password"><input id="password" className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></Field>
        <Button variant="primary" size="lg" loading={busy} type="submit" icon={<Mail size={16} />}>Sign in</Button>
        <p style={{ textAlign: "center", margin: 0 }}>New here? <Link to="/register">Create an account</Link></p>
      </form>
    </Shell>
  );
}

export function Register() {
  usePageTitle("Create account");
  const { user } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ full_name: "", email: "", password: "", confirm: "" });
  const [err, setErr] = useState(""); const [fields, setFields] = useState<Record<string, string>>({}); const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/app" replace />;
  async function submit(e: FormEvent) {
    e.preventDefault(); setErr(""); setFields({});
    if (f.password !== f.confirm) { setFields({ confirm: "Passwords do not match" }); return; }
    setBusy(true);
    try { await api.register({ full_name: f.full_name, email: f.email.trim(), password: f.password }); nav("/login", { state: { registered: true } }); }
    catch (x) {
      if (x instanceof ApiError) { setErr(x.message); const m: Record<string, string> = {}; x.fieldErrors.forEach((fe) => { m[fe.field] = fe.message; }); setFields(m); }
      else setErr("Registration failed.");
    } finally { setBusy(false); }
  }
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <Shell title="Create your account" subtitle="Free. Your records stay private and you can delete them any time.">
      <form className="stack" onSubmit={submit} noValidate>
        {err && <Alert tone="error">{err}</Alert>}
        <Field label="Full name" htmlFor="name" error={fields.full_name}><input id="name" className="input" autoComplete="name" value={f.full_name} onChange={set("full_name")} required /></Field>
        <Field label="Email" htmlFor="email" error={fields.email}><input id="email" className="input" type="email" autoComplete="email" value={f.email} onChange={set("email")} required /></Field>
        <Field label="Password" htmlFor="pw" error={fields.password} hint="At least 8 characters with a letter and a number."><input id="pw" className="input" type="password" autoComplete="new-password" value={f.password} onChange={set("password")} required /></Field>
        <Field label="Confirm password" htmlFor="pw2" error={fields.confirm}><input id="pw2" className="input" type="password" autoComplete="new-password" value={f.confirm} onChange={set("confirm")} required /></Field>
        <Button variant="primary" size="lg" loading={busy} type="submit" icon={<UserIcon size={16} />}>Create account</Button>
        <p style={{ textAlign: "center", margin: 0 }}>Already registered? <Link to="/login">Sign in</Link></p>
      </form>
    </Shell>
  );
}
