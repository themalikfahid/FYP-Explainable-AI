import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as { state?: { from?: string; message?: string } };
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!email || !password) { setError("Enter your email and password."); return; }
    setBusy(true); setError("");
    try {
      await login(email.trim(), password);
      nav(loc.state?.from ?? "/dashboard", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Log in failed.");
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit} noValidate aria-labelledby="login-h">
        <h1 id="login-h">Log in</h1>
        {loc.state?.message && <p className="banner info" role="status">{loc.state.message}</p>}
        {error && <p className="banner error" role="alert">{error}</p>}
        <div className="field"><label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
        <div className="field"><label htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></div>
        <button className="btn wide" disabled={busy}>{busy ? "Logging in…" : "Log in"}</button>
        <p className="fine">New here? <Link to="/register">Create an account</Link></p>
      </form>
    </div>
  );
}

export function Register() {
  const nav = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  function validate() {
    const e: Record<string, string> = {};
    if (!form.full_name.trim()) e.full_name = "Enter your name.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = "Enter a valid email address.";
    if (form.password.length < 8) e.password = "Use at least 8 characters.";
    else if (!/[A-Za-z]/.test(form.password) || !/\d/.test(form.password)) e.password = "Include at least one letter and one number.";
    if (form.confirm !== form.password) e.confirm = "Passwords don't match.";
    return e;
  }

  async function submit(ev: FormEvent) {
    ev.preventDefault();
    const e = validate();
    setErrors(e);
    if (Object.keys(e).length) return;
    setBusy(true); setError("");
    try {
      await api.register({ full_name: form.full_name.trim(), email: form.email.trim(), password: form.password });
      nav("/login", { state: { message: "Account created. Log in to continue." } });
    } catch (err) {
      if (err instanceof ApiError && err.fieldErrors.length) {
        setErrors(Object.fromEntries(err.fieldErrors.map((f) => [f.field, f.message.replace(/^Value error, /, "")])));
      }
      setError(err instanceof ApiError ? err.message : "Registration failed.");
      setBusy(false);
    }
  }

  const f = (k: keyof typeof form, label: string, type: string, auto: string) => (
    <div className={errors[k] ? "field has-error" : "field"}>
      <label htmlFor={k}>{label}</label>
      <input id={k} type={type} autoComplete={auto} value={form[k]} onChange={set(k)} aria-invalid={!!errors[k]}
        aria-describedby={errors[k] ? `${k}-err` : undefined} />
      {errors[k] && <p className="err" id={`${k}-err`} role="alert">{errors[k]}</p>}
    </div>
  );

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit} noValidate aria-labelledby="reg-h">
        <h1 id="reg-h">Create an account</h1>
        <p className="fine">Your assessments are stored on this server and are visible only to you.</p>
        {error && <p className="banner error" role="alert">{error}</p>}
        {f("full_name", "Full name", "text", "name")}
        {f("email", "Email", "email", "email")}
        {f("password", "Password (8+ characters, with a letter and a number)", "password", "new-password")}
        {f("confirm", "Confirm password", "password", "new-password")}
        <button className="btn wide" disabled={busy}>{busy ? "Creating account…" : "Create account"}</button>
        <p className="fine">Already registered? <Link to="/login">Log in</Link></p>
      </form>
    </div>
  );
}
