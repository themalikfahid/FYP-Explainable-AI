import { lazy, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, ArrowRight, BadgeCheck, Download, FlaskConical, HelpCircle, Lightbulb, Plus, Sliders, Trash2, X } from "lucide-react";
import SceneFrame from "../components/three/SceneFrame";
import { Alert, Badge, Button, Card, Gauge, PageHead, RiskBadge, Skeleton, usePageTitle, useToast } from "../components/ui";
import { api, type FieldSpec, type Prediction, type Task, type WhatIfResult } from "../lib/api";
import { dateTime, pct, riskColor, taskName } from "../lib/format";
import { useFeatureMeta } from "../lib/useMeta";

const RiskOrbScene = lazy(() => import("../components/three/Shapes").then((m) => ({ default: m.RiskOrb })));

function ConfidenceCard({ p }: { p: Prediction }) {
  const c = p.result.confidence;
  if (!c) return null;
  const ok = c.tier === "confident";
  return (
    <Card style={{ borderColor: ok ? "rgba(52,211,153,.4)" : "rgba(251,191,36,.45)" }}>
      <div className="spread" style={{ marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>{ok ? <BadgeCheck size={18} color="#34d399" /> : <HelpCircle size={18} color="#fbbf24" />} {ok ? "Confident result" : "Inconclusive result"}</h3>
        <Badge tone={ok ? "low" : "moderate"}>{pct(c.value)} model confidence</Badge>
      </div>
      <p style={{ margin: 0, fontSize: 14 }}>{c.note}</p>
      {c.threshold != null && (
        <div style={{ marginTop: 14 }}>
          <div className="bar" aria-hidden><i style={{ width: pct(c.value), background: ok ? "linear-gradient(90deg,#34d399,#22d3ee)" : "linear-gradient(90deg,#fbbf24,#fb7185)" }} /></div>
          <div className="spread faint" style={{ fontSize: 12, marginTop: 6 }}><span>0%</span><span>gate {pct(c.threshold)}</span><span>100%</span></div>
        </div>
      )}
    </Card>
  );
}

function Shap({ p, labels }: { p: Prediction; labels: Record<string, FieldSpec> }) {
  const e = p.result.explanation;
  if (!e) return null;
  const heart = p.disease === "heart" && e.any_disease;
  // Always express contributions toward the "disease present / positive" outcome so red = raises risk.
  const flip = !heart && e.explained_class === 0;
  const base = heart ? e.any_disease!.base_value : flip ? 1 - e.base_value : e.base_value;
  const items = heart
    ? Object.entries(e.any_disease!.shap).map(([feature, shap]) => ({ feature, shap, value: p.inputs[feature] }))
    : e.contributions.map((c) => (flip ? { ...c, shap: -c.shap } : c));
  const sorted = [...items].sort((a, b) => Math.abs(b.shap) - Math.abs(a.shap)).slice(0, 10);
  const max = Math.max(...sorted.map((i) => Math.abs(i.shap)), 0.01);
  const fmtVal = (f: string, v: number | null | undefined) => {
    const s = labels[f]; if (v == null) return "not given";
    if (s?.type === "select") return s.options?.find((o) => o.value === v)?.label ?? String(v);
    return `${v}${s?.unit ? " " + s.unit : ""}`;
  };
  return (
    <Card>
      <div className="card-title"><h3><Lightbulb size={18} color="#fbbf24" /> Why this score?</h3><Badge tone="violet">SHAP · {heart ? "any heart disease" : "positive screen"}</Badge></div>
      <p style={{ fontSize: 14 }}>Starting from an average baseline of <strong className="mono">{pct(base)}</strong>, each input pushed the estimated probability up (red) or down (green), in percentage points.</p>
      <div role="list" aria-label="Feature contributions">
        {sorted.map((c, i) => {
          const w = (Math.abs(c.shap) / max) * 50;
          const up = c.shap >= 0;
          return (
            <motion.div role="listitem" className="shap-row" key={c.feature} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * .04 }}>
              <div><div style={{ fontWeight: 500 }}>{labels[c.feature]?.label ?? c.feature}</div><div className="faint mono" style={{ fontSize: 12 }}>{fmtVal(c.feature, c.value)}</div></div>
              <div className="shap-track" aria-hidden>
                <motion.div className="shap-fill" initial={{ width: 0 }} animate={{ width: `${w}%` }} transition={{ duration: .8, delay: .1 + i * .04 }}
                  style={{ [up ? "left" : "right"]: "50%", background: up ? "linear-gradient(90deg,#fb7185aa,#fb7185)" : "linear-gradient(270deg,#34d399aa,#34d399)" } as any} />
              </div>
              <div className="mono" style={{ textAlign: "right", color: up ? "#fb7185" : "#34d399" }}>{up ? "+" : ""}{(c.shap * 100).toFixed(1)}</div>
            </motion.div>
          );
        })}
      </div>
      <hr className="sep" />
      <ul style={{ margin: 0, paddingLeft: 20, color: "var(--muted)", fontSize: 14 }}>
        {sorted.slice(0, 3).map((c) => (
          <li key={c.feature}>{labels[c.feature]?.label ?? c.feature} = {fmtVal(c.feature, c.value)} {c.shap >= 0 ? "raised" : "lowered"} the estimated {heart ? "heart-disease" : "positive-screen"} probability by {Math.abs(c.shap * 100).toFixed(1)} percentage points.</li>
        ))}
      </ul>
      <p className="faint" style={{ fontSize: 12.5, margin: "14px 0 0" }}>SHAP describes how the model behaves, not what causes disease.</p>
    </Card>
  );
}

function WhatIf({ p, spec }: { p: Prediction; spec: Record<string, FieldSpec> }) {
  const task = p.disease as Task;
  const editable = useMemo(() => Object.keys(spec).filter((f) => p.inputs[f] !== undefined), [spec, p.inputs]);
  const [picked, setPicked] = useState<Record<string, string>>({});
  const [res, setRes] = useState<WhatIfResult | null>(null);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const free = editable.filter((f) => !(f in picked));
  const ready = Object.entries(picked).filter(([, v]) => v !== "");

  async function run() {
    setBusy(true); setErr("");
    try {
      const changes = Object.fromEntries(ready.map(([k, v]) => [k, Number(v)]));
      setRes(await api.whatIf(task, p.inputs, changes));
    } catch (x: any) { setErr(x.message || "Could not run the simulation."); } finally { setBusy(false); }
  }
  useEffect(() => { setRes(null); }, [picked]);

  return (
    <Card>
      <div className="card-title"><h3><Sliders size={18} color="#22d3ee" /> What-if simulator</h3><Badge tone="cyan">model only</Badge></div>
      <p style={{ fontSize: 14 }}>Change inputs and see how the <em>model's</em> score responds. Nothing is saved.</p>
      <div className="stack">
        {Object.entries(picked).map(([f, v]) => {
          const s = spec[f];
          return (
            <div key={f} className="row" style={{ alignItems: "end", flexWrap: "nowrap" }}>
              <div style={{ flex: 1 }}>
                <div className="label">{s.label} <span className="faint" style={{ fontWeight: 400 }}>now {String(p.inputs[f] ?? "—")}</span></div>
                {s.type === "select" ? (
                  <select className="input" value={v} onChange={(e) => setPicked({ ...picked, [f]: e.target.value })} aria-label={s.label}>
                    <option value="">Choose…</option>{s.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                ) : <input className="input mono" type="number" value={v} min={s.min} max={s.max} step={s.step ?? "any"} onChange={(e) => setPicked({ ...picked, [f]: e.target.value })} aria-label={s.label} />}
              </div>
              <Button variant="ghost" className="icon" aria-label={`Remove ${s.label}`} onClick={() => { const n = { ...picked }; delete n[f]; setPicked(n); }}><X size={16} /></Button>
            </div>
          );
        })}
        {free.length > 0 && (
          <select className="input" value="" aria-label="Add an input to change" onChange={(e) => e.target.value && setPicked({ ...picked, [e.target.value]: "" })}>
            <option value="">+ Add an input to change…</option>{free.map((f) => <option key={f} value={f}>{spec[f].label}</option>)}
          </select>
        )}
        <Button variant="primary" icon={<Plus size={16} />} loading={busy} disabled={ready.length === 0} onClick={run}>Run scenario</Button>
        {err && <Alert tone="error">{err}</Alert>}
      </div>
      {res && (
        <div className="stack" style={{ marginTop: 18 }}>
          <div className="grid cols-2">
            {[["Current", res.baseline], ["Scenario", res.scenario]].map(([k, v]: any) => (
              <div key={k} className="card" style={{ padding: 16 }}>
                <div className="faint" style={{ fontSize: 12 }}>{k}</div>
                <div className="mono" style={{ fontSize: "1.8rem", fontWeight: 700, color: riskColor[v.risk_level as keyof typeof riskColor] }}>{pct(v.risk_score, 1)}</div>
                <RiskBadge level={v.risk_level} />
              </div>
            ))}
          </div>
          <Alert tone={res.delta < -0.005 ? "ok" : res.delta > 0.005 ? "warn" : "info"}>
            The model's score {Math.abs(res.delta) < 0.005 ? "barely changes" : res.delta < 0 ? `falls by ${(Math.abs(res.delta) * 100).toFixed(1)} points` : `rises by ${(res.delta * 100).toFixed(1)} points`}.
          </Alert>
          {res.per_change.length > 1 && <div className="chip-list">{res.per_change.map((c) => <span key={c.feature} className="badge">{c.label}: {c.delta >= 0 ? "+" : ""}{(c.delta * 100).toFixed(1)}</span>)}</div>}
          <p className="faint" style={{ fontSize: 12.5, margin: 0 }}>{res.note}</p>
        </div>
      )}
    </Card>
  );
}

export default function ResultPage() {
  const { id } = useParams(); const nav = useNavigate(); const toast = useToast();
  const { meta } = useFeatureMeta();
  const [p, setP] = useState<Prediction | null>(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  usePageTitle(p ? `${taskName(p.disease)} result` : "Result");
  useEffect(() => { api.prediction(Number(id)).then(setP).catch((e) => setErr(e.message)); }, [id]);

  if (err) return <Alert tone="error">{err} <Link to="/app/history">Back to history</Link></Alert>;
  if (!p || !meta) return <div className="stack"><Skeleton h={60} /><Skeleton h={340} /></div>;
  const r = p.result; const spec = meta[p.disease].spec;
  const probs = Object.entries(r.probabilities).map(([k, v]) => ({ k, name: p.disease === "heart" ? (k === "0" ? "No disease" : `Grade ${k}`) : k === "1" ? "Positive" : "Negative", v, top: Number(k) === r.predicted_class }));
  const comp = Object.keys(r.probabilities).map((k) => ({ name: p.disease === "heart" ? (k === "0" ? "No disease" : `Grade ${k}`) : k === "1" ? "Positive" : "Negative", RF: r.components.random_forest[k], ANN: r.components.ann[k] }));
  const cv = r.model.cross_validated;

  async function download() { setBusy(true); try { await api.downloadReport(p!.id!); } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); } }
  async function remove() {
    if (!window.confirm("Delete this assessment permanently?")) return;
    await api.deletePrediction(p!.id!); toast("Assessment deleted", "ok"); nav("/app/history");
  }

  return (
    <>
      <PageHead title={taskName(p.disease)} subtitle={`${dateTime(p.created_at)} · model ${r.model.production_model}`}
        actions={<><Button icon={<Download size={16} />} loading={busy} onClick={download}>PDF report</Button><Button variant="danger" icon={<Trash2 size={16} />} onClick={remove}>Delete</Button></>} />

      <div className="grid" style={{ gap: 20 }}>
        <div className="grid" style={{ gridTemplateColumns: "minmax(0,1.15fr) minmax(0,1fr)" }}>
          <Card glow large style={{ overflow: "hidden" }}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap" }}>
              <div className="stack" style={{ alignItems: "flex-start" }}>
                <RiskBadge level={p.risk_level} />
                <Gauge value={r.risk_score} level={p.risk_level} label={p.disease === "heart" ? "any heart disease" : p.disease === "cad" ? "coronary artery disease" : "positive screen"} />
              </div>
              <div className="risk-orb" style={{ width: 230, height: 230, flex: "none" }}>
                <SceneFrame camera={[0, 0, 4.4]} fov={42}><RiskOrbScene score={r.risk_score} level={p.risk_level} /></SceneFrame>
              </div>
            </div>
            <hr className="sep" />
            <div className="stack" style={{ gap: 6 }}>
              <div className="faint" style={{ fontSize: 12.5 }}>Most likely class</div>
              <div style={{ fontFamily: "var(--font-display)", fontSize: "1.35rem", fontWeight: 600 }}>{r.predicted_label}</div>
              <p style={{ margin: 0, fontSize: 13.5 }}>{r.risk_score_definition}. Bands: low &lt; {pct(r.risk_thresholds.low_below)}, high ≥ {pct(r.risk_thresholds.high_at_or_above)}.</p>
            </div>
          </Card>
          <div className="stack">
            <ConfidenceCard p={p} />
            {cv && (
              <Card>
                <h3>How accurate is this model?</h3>
                <div className="grid cols-2" style={{ gap: 12 }}>
                  <div><div className="faint" style={{ fontSize: 12 }}>Cross-validated accuracy</div><div className="mono" style={{ fontSize: "1.6rem", fontWeight: 700 }}>{pct(cv.cv_accuracy, 1)}</div></div>
                  {cv.confident_accuracy != null && <div><div className="faint" style={{ fontSize: 12 }}>When confident</div><div className="mono" style={{ fontSize: "1.6rem", fontWeight: 700, color: "#34d399" }}>{pct(cv.confident_accuracy, 1)}</div></div>}
                </div>
                <p className="faint" style={{ fontSize: 12.5, margin: "10px 0 0" }}>On public research data, not clinical accuracy. <Link to="/app/models">See full evaluation</Link></p>
              </Card>
            )}
            {r.warnings.map((w, i) => <Alert key={i} tone="warn">{w}</Alert>)}
          </div>
        </div>

        <div className="grid cols-2">
          <Card>
            <div className="card-title"><h3>Class probabilities</h3></div>
            <div style={{ height: 240 }}>
              <ResponsiveContainer><BarChart data={probs} layout="vertical" margin={{ left: 10, right: 20 }}>
                <CartesianGrid horizontal={false} /><XAxis type="number" domain={[0, 1]} tickFormatter={(v) => `${v * 100}%`} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" width={86} tickLine={false} axisLine={false} />
                <Tooltip formatter={(v: number) => pct(v, 1)} contentStyle={{ background: "#0e1830", border: "1px solid rgba(120,150,220,.3)", borderRadius: 12 }} />
                <Bar dataKey="v" radius={8} animationDuration={900}>{probs.map((d, i) => <Cell key={i} fill={d.top ? "#22d3ee" : "#475a8c"} />)}</Bar>
              </BarChart></ResponsiveContainer>
            </div>
          </Card>
          <Card>
            <div className="card-title"><h3>Random Forest vs neural network</h3><Badge tone="violet">hybrid inputs</Badge></div>
            <div style={{ height: 240 }}>
              <ResponsiveContainer><BarChart data={comp} margin={{ left: -14, right: 6 }}>
                <CartesianGrid vertical={false} /><XAxis dataKey="name" tickLine={false} axisLine={false} /><YAxis domain={[0, 1]} tickFormatter={(v) => `${v * 100}%`} tickLine={false} axisLine={false} />
                <Tooltip formatter={(v: number) => pct(v, 1)} contentStyle={{ background: "#0e1830", border: "1px solid rgba(120,150,220,.3)", borderRadius: 12 }} />
                <Bar dataKey="RF" fill="#7c83ff" radius={[6, 6, 0, 0]} /><Bar dataKey="ANN" fill="#22d3ee" radius={[6, 6, 0, 0]} />
              </BarChart></ResponsiveContainer>
            </div>
            <div className="legend"><span><i style={{ background: "#7c83ff" }} />Random Forest</span><span><i style={{ background: "#22d3ee" }} />Neural network</span><span>max disagreement {pct(r.components.max_disagreement)}</span></div>
          </Card>
        </div>

        <div className="grid cols-2" style={{ alignItems: "start" }}>
          <Shap p={p} labels={spec} />
          <WhatIf p={p} spec={spec} />
        </div>

        <Card>
          <div className="card-title"><h3><FlaskConical size={18} color="#34d399" /> Personalised next steps</h3></div>
          {r.recommendations.top_risk_factors?.length > 0 && <div className="chip-list" style={{ marginBottom: 16 }}>{r.recommendations.top_risk_factors.map((f) => <span key={f} className="badge high">{f}</span>)}</div>}
          <div className="grid cols-2">
            {r.recommendations.items.map((it, i) => (
              <div key={i} className={`rec ${it.priority}`}><div className="p" /><div><Badge tone={it.priority === "high" ? "high" : it.priority === "medium" ? "moderate" : "low"}>{it.category}</Badge><p style={{ margin: "8px 0 0", color: "var(--text)" }}>{it.text}</p><div className="src">{it.source}</div></div></div>
            ))}
          </div>
          {(r.recommendations.bmi || r.recommendations.lifestyle_score) && (
            <><hr className="sep" /><div className="grid cols-2">
              {r.recommendations.bmi && <div className="card" style={{ padding: 16 }}><div className="faint" style={{ fontSize: 12 }}>BMI</div><div className="mono" style={{ fontSize: "1.6rem", fontWeight: 700 }}>{r.recommendations.bmi.bmi.toFixed(1)}</div><div className="muted">{r.recommendations.bmi.category}</div></div>}
              {r.recommendations.lifestyle_score && <div className="card" style={{ padding: 16 }}><div className="faint" style={{ fontSize: 12 }}>Lifestyle score</div><div className="mono" style={{ fontSize: "1.6rem", fontWeight: 700 }}>{r.recommendations.lifestyle_score.score}/100</div><div className="muted">{r.recommendations.lifestyle_score.band}</div></div>}
            </div></>
          )}
        </Card>

        <Alert tone="warn" title="Please read">{r.recommendations.disclaimer}</Alert>
        <div className="row no-print"><Button to="/app/assess" icon={<ArrowRight size={16} />}>Run another assessment</Button><span className="faint row" style={{ fontSize: 13, gap: 8 }}><AlertTriangle size={14} /> {r.probability_note}</span></div>
      </div>
    </>
  );
}
