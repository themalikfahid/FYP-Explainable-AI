import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { animate, motion, useInView, useMotionValue, useTransform } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, OctagonAlert } from "lucide-react";
import type { FieldSpec, RiskLevel } from "../../lib/api";
import { riskColor } from "../../lib/format";

/* ---------------------------------------------------------------- buttons */
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "danger" | "default"; size?: "sm" | "md" | "lg"; to?: string; loading?: boolean; icon?: ReactNode;
};
export function Button({ variant = "default", size = "md", to, loading, icon, children, className = "", ...rest }: BtnProps) {
  const cls = `btn ${variant === "default" ? "" : variant} ${size === "md" ? "" : size} ${className}`.trim();
  if (to) return <Link className={cls} to={to}>{icon}{children}</Link>;
  return (
    <button className={cls} disabled={loading || rest.disabled} {...rest}>
      {loading ? <span className="spinner" aria-hidden /> : icon}{children}
    </button>
  );
}

/* ----------------------------------------------------------------- layout */
export function Card({ children, className = "", glow = false, large = false, ...rest }: { children: ReactNode; className?: string; glow?: boolean; large?: boolean } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`card ${glow ? "glow" : ""} ${large ? "pad-lg" : ""} ${className}`} {...rest}>{children}</div>;
}
export function PageHead({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>
      {actions && <div className="row">{actions}</div>}
    </div>
  );
}
export function Badge({ tone = "default", children, dot }: { tone?: "default" | "low" | "moderate" | "high" | "cyan" | "violet"; children: ReactNode; dot?: boolean }) {
  return <span className={`badge ${tone === "default" ? "" : tone}`}>{dot && <i className="dot" />}{children}</span>;
}
export function RiskBadge({ level }: { level: RiskLevel }) {
  const label = { low: "Low risk", moderate: "Moderate risk", high: "High risk" }[level];
  return <Badge tone={level} dot>{label}</Badge>;
}
export function Spinner() { return <span className="spinner" role="status" aria-label="Loading" />; }
export function Skeleton({ h = 20, w = "100%", r = 12 }: { h?: number; w?: number | string; r?: number }) {
  return <div className="skeleton" style={{ height: h, width: w, borderRadius: r }} aria-hidden />;
}
export function Empty({ icon, title, children, action }: { icon: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="empty"><div className="icon-chip">{icon}</div><h3 style={{ justifyContent: "center" }}>{title}</h3><p>{children}</p>{action}</div>;
}

type AlertTone = "info" | "warn" | "error" | "ok" | "emergency";
export function Alert({ tone = "info", title, children }: { tone?: AlertTone; title?: string; children?: ReactNode }) {
  const Icon = { info: Info, warn: AlertTriangle, error: OctagonAlert, ok: CheckCircle2, emergency: OctagonAlert }[tone];
  return (
    <div className={`alert ${tone === "info" ? "" : tone}`} role={tone === "error" || tone === "emergency" ? "alert" : "status"}>
      <Icon size={18} aria-hidden />
      <div>{title && <strong style={{ display: "block", marginBottom: 2 }}>{title}</strong>}<p>{children}</p></div>
    </div>
  );
}

/* ------------------------------------------------------------------ toasts */
type Toast = { id: number; text: string; tone: "ok" | "error" | "info" };
const ToastCtx = createContext<(text: string, tone?: Toast["tone"]) => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: Toast["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s, { id, text, tone }]);
    setTimeout(() => setItems((s) => s.filter((t) => t.id !== id)), 4200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => (
          <motion.div key={t.id} className={`toast ${t.tone}`} initial={{ opacity: 0, y: 14, scale: .96 }} animate={{ opacity: 1, y: 0, scale: 1 }}>{t.text}</motion.div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* --------------------------------------------------------------- animation */
export function AnimatedNumber({ value, decimals = 0, suffix = "", duration = 1.1 }: { value: number; decimals?: number; suffix?: string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) => `${v.toFixed(decimals)}${suffix}`);
  useEffect(() => {
    if (!inView) return;
    const c = animate(mv, value, { duration, ease: "easeOut" });
    return () => c.stop();
  }, [inView, value, duration, mv]);
  return <motion.span ref={ref} className="mono">{text}</motion.span>;
}
export function Reveal({ children, delay = 0, y = 24, className = "" }: { children: ReactNode; delay?: number; y?: number; className?: string }) {
  return (
    <motion.div className={className} initial={{ opacity: 0, y }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }} transition={{ duration: .6, delay, ease: [.22, 1, .36, 1] }}>{children}</motion.div>
  );
}

/* -------------------------------------------------------------------- gauge */
export function Gauge({ value, level, size = 230, label }: { value: number; level: RiskLevel; size?: number; label?: string }) {
  const r = size / 2 - 16, c = 2 * Math.PI * r, arc = c * 0.75;
  const color = riskColor[level];
  const id = useId();
  return (
    <div className="gauge-wrap" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: "rotate(135deg)" }} aria-hidden>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor={color} stopOpacity=".5" /><stop offset="1" stopColor={color} /></linearGradient>
          <filter id={`${id}g`}><feGaussianBlur stdDeviation="5" /></filter>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(120,150,220,.16)" strokeWidth="14" strokeLinecap="round" strokeDasharray={`${arc} ${c}`} />
        <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="14" strokeLinecap="round" filter={`url(#${id}g)`} opacity=".55"
          initial={{ strokeDasharray: `0 ${c}` }} animate={{ strokeDasharray: `${arc * value} ${c}` }} transition={{ duration: 1.4, ease: "easeOut" }} />
        <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={`url(#${id})`} strokeWidth="14" strokeLinecap="round"
          initial={{ strokeDasharray: `0 ${c}` }} animate={{ strokeDasharray: `${arc * value} ${c}` }} transition={{ duration: 1.4, ease: "easeOut" }} />
      </svg>
      <div className="gauge-center">
        <div className="big" style={{ color }}><AnimatedNumber value={value * 100} suffix="%" /></div>
        <div className="muted" style={{ fontSize: 13, marginTop: 6 }}>{label ?? "estimated risk"}</div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------- inputs */
export function Field({ label, hint, error, unit, children, htmlFor }: { label: ReactNode; hint?: ReactNode; error?: string; unit?: string; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="field">
      <label htmlFor={htmlFor}><span>{label}</span>{unit && <span className="faint" style={{ fontWeight: 500 }}>{unit}</span>}</label>
      {children}
      {error ? <span className="err" role="alert">{error}</span> : hint ? <span className="hint">{hint}</span> : null}
    </div>
  );
}

export function SpecField({ name, spec, value, onChange, error }: {
  name: string; spec: FieldSpec; value: string; onChange: (v: string) => void; error?: string;
}) {
  const id = `f-${name}`;
  const hint = spec.help ?? (spec.type === "number" && spec.min !== undefined ? `Between ${spec.min} and ${spec.max}${spec.unit ? " " + spec.unit : ""}` : undefined);
  const label = <>{spec.label}{!spec.required && <span className="faint" style={{ fontWeight: 400 }}> (optional)</span>}</>;
  if (spec.type === "select") {
    const opts = spec.options ?? [];
    if (opts.length <= 3) {
      return (
        <Field label={label} error={error} hint={hint}>
          <div className="seg" role="group" aria-label={spec.label}>
            {opts.map((o) => (
              <button type="button" key={o.value} aria-pressed={value === String(o.value)} onClick={() => onChange(value === String(o.value) && !spec.required ? "" : String(o.value))}>{o.label}</button>
            ))}
          </div>
        </Field>
      );
    }
    return (
      <Field label={label} error={error} hint={hint} htmlFor={id}>
        <select id={id} className="input" value={value} aria-invalid={!!error} onChange={(e) => onChange(e.target.value)}>
          <option value="">{spec.required ? "Select…" : "Not available"}</option>
          {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </Field>
    );
  }
  return (
    <Field label={label} error={error} hint={hint} htmlFor={id}>
      <div className="input-wrap">
        <input id={id} className={`input mono ${spec.unit ? "has-unit" : ""}`} inputMode="decimal" type="number" value={value} step={spec.step ?? "any"} min={spec.min} max={spec.max}
          aria-invalid={!!error} onChange={(e) => onChange(e.target.value)} placeholder={spec.required ? "" : "optional"} />
        {spec.unit && <span className="unit">{spec.unit}</span>}
      </div>
    </Field>
  );
}

export function ToggleCard({ title, help, on, onClick }: { title: string; help?: string; on: boolean; onClick: () => void }) {
  return (
    <button type="button" className="toggle-card" aria-pressed={on} onClick={onClick}>
      <span><span className="tc-title">{title}</span>{help && <><br /><span className="tc-help">{help}</span></>}</span>
      <span className="switch" aria-hidden />
    </button>
  );
}

export function Segmented<T extends string | number>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => <button type="button" key={String(o.value)} aria-pressed={value === o.value} onClick={() => onChange(o.value)}>{o.label}</button>)}
    </div>
  );
}

export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div className="stepper" aria-label="Progress">
      {steps.map((s, i) => (
        <div key={s} className={`step ${i === current ? "active" : i < current ? "done" : ""}`} aria-current={i === current ? "step" : undefined}>
          <span className="n">{i < current ? "✓" : i + 1}</span>{s}
        </div>
      ))}
    </div>
  );
}

export function Stat({ icon, label, value, sub }: { icon?: ReactNode; label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="stat">
      <div className="k">{icon}{label}</div>
      <div className="v">{value}</div>
      {sub && <div className="s">{sub}</div>}
    </div>
  );
}

export function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}

export const usePageTitle = (t: string) => useEffect(() => { document.title = `${t} | Clarity Screen`; }, [t]);
export const useMemoObj = <T,>(v: T) => useMemo(() => v, [v]);
