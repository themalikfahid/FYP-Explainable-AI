import { lazy, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, BadgeCheck, BrainCircuit, FileText, Gauge as GaugeIcon, HeartPulse, Layers, LineChart, Lock, Mail, Microscope, ScanSearch, ShieldAlert, SlidersHorizontal, Sparkles, Stethoscope, Droplets } from "lucide-react";
import { Brand } from "../components/layout/Brand";
import { AnimatedNumber, Badge, Button, Card, Reveal, usePageTitle } from "../components/ui";
import SceneFrame from "../components/three/SceneFrame";
import { api, type OofReport } from "../lib/api";
import { useAuth } from "../lib/auth";
import { pct } from "../lib/format";

const HeroScene = lazy(() => import("../components/three/Shapes").then((m) => ({ default: m.HeroScene })));

type Stats = { diabetes?: OofReport; heart?: OofReport };

export default function Landing() {
  usePageTitle("Explainable AI health screening");
  const { user } = useAuth();
  const [stats, setStats] = useState<Stats>({});
  useEffect(() => {
    Promise.allSettled([api.modelInfo("diabetes"), api.modelInfo("heart")]).then(([d, h]) =>
      setStats({ diabetes: d.status === "fulfilled" ? d.value.cross_validated : undefined, heart: h.status === "fulfilled" ? h.value.cross_validated : undefined }));
  }, []);
  const d = stats.diabetes, h = stats.heart;
  const dGate = d?.gate.table.find((r) => r.min_confidence === d.gate.threshold);
  const hGate = h?.gate.table.find((r) => r.min_confidence === h.gate.threshold);

  return (
    <>
      <header className="public-nav">
        <Brand />
        <nav aria-label="Primary">
          <a className="btn ghost sm" href="#how">How it works</a>
          <a className="btn ghost sm" href="#accuracy">Accuracy</a>
          <a className="btn ghost sm" href="#honesty">Limits</a>
          {user ? <Button size="sm" variant="primary" to="/app">Open dashboard</Button> : <>
            <Button size="sm" variant="ghost" to="/login">Sign in</Button>
            <Button size="sm" variant="primary" to="/register">Get started</Button></>}
        </nav>
      </header>

      <main id="main">
        <section className="hero">
          <div className="hero-canvas"><SceneFrame><HeroScene /></SceneFrame></div>
          <div className="container">
            <motion.div className="hero-copy" initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .8, ease: [.22, 1, .36, 1] }}>
              <span className="eyebrow"><Sparkles size={15} /> Hybrid Random Forest + Neural Network · SHAP explanations</span>
              <h1>Screening you can <span className="grad-text">understand</span>, not just trust.</h1>
              <p className="lead">Clarity Screen estimates diabetes and heart-disease risk with an explainable hybrid AI. Every score shows <em>why</em> it was given, how sure the model is, and what to ask a doctor next.</p>
              <div className="row" style={{ marginTop: 28 }}>
                <Button size="lg" variant="primary" to={user ? "/app/assess" : "/register"} icon={<ArrowRight size={18} />}>Start a free assessment</Button>
                <Button size="lg" to="#how" onClick={(e) => { e.preventDefault(); document.getElementById("how")?.scrollIntoView({ behavior: "smooth" }); }}>See how it works</Button>
              </div>
              <div className="row faint" style={{ marginTop: 26, gap: 22, fontSize: 13.5 }}>
                <span className="row" style={{ gap: 8 }}><Lock size={15} /> Private by design</span>
                <span className="row" style={{ gap: 8 }}><BadgeCheck size={15} /> Cross-validated</span>
                <span className="row" style={{ gap: 8 }}><ShieldAlert size={15} /> Not a diagnosis</span>
              </div>
            </motion.div>
          </div>
        </section>

        <section className="section" id="accuracy" style={{ paddingTop: 30 }}>
          <div className="container">
            <Reveal>
              <div className="metric-band" role="list" aria-label="Measured performance">
                <div role="listitem"><div className="faint">Diabetes screen · cross-validated accuracy</div><div className="v grad-text">{d ? <AnimatedNumber value={d.overall.accuracy * 100} decimals={1} suffix="%" /> : "…"}</div><div className="muted" style={{ fontSize: 13 }}>{d ? `${d.n_records} unique records, 5-fold × ${d.repeats}` : ""}</div></div>
                <div role="listitem"><div className="faint">Diabetes · confident predictions</div><div className="v grad-text">{dGate ? <AnimatedNumber value={dGate.accuracy * 100} decimals={1} suffix="%" /> : "…"}</div><div className="muted" style={{ fontSize: 13 }}>{dGate ? `answered for ${pct(dGate.coverage)} of cases` : ""}</div></div>
                <div role="listitem"><div className="faint">Heart · disease detection accuracy</div><div className="v">{h?.any_disease ? <AnimatedNumber value={h.any_disease.accuracy * 100} decimals={1} suffix="%" /> : "…"}</div><div className="muted" style={{ fontSize: 13 }}>{h?.any_disease ? `ROC-AUC ${h.any_disease.roc_auc.toFixed(2)}, 918 patients` : ""}</div></div>
                <div role="listitem"><div className="faint">Heart · confident predictions</div><div className="v grad-text">{hGate ? <AnimatedNumber value={hGate.accuracy * 100} decimals={1} suffix="%" /> : "…"}</div><div className="muted" style={{ fontSize: 13 }}>{hGate ? `answered for ${pct(hGate.coverage)} of cases` : ""}</div></div>
              </div>
            </Reveal>
            <p className="faint" style={{ fontSize: 13, marginTop: 14 }}>Out-of-fold results on public research datasets, not clinical accuracy. When the model is unsure it says “inconclusive” instead of guessing.</p>
          </div>
        </section>

        <section className="section" id="how">
          <div className="container">
            <Reveal><div className="section-head"><Badge tone="cyan">Pipeline</Badge><h2 style={{ marginTop: 14 }}>From a few inputs to an answer you can check.</h2><p>Every step is visible, measured and documented.</p></div></Reveal>
            <div className="pipeline">
              {[["Enter data", "Symptoms or routine clinical measurements. Optional lifestyle details add BMI and a lifestyle score."], ["Hybrid AI", "A Random Forest and a neural network each vote; their probabilities are blended."], ["Explain", "SHAP shows which inputs pushed the score up or down, in plain percentage points."], ["Confidence gate", "Low-confidence cases are marked inconclusive rather than forced into an answer."], ["Act", "Personalised, source-referenced next steps, a PDF report and optional email alerts."]].map(([t, p], i) => (
                <Reveal key={t} delay={i * .07}><div><h4>{t}</h4><p>{p}</p></div></Reveal>
              ))}
            </div>
          </div>
        </section>

        <section className="section">
          <div className="container">
            <Reveal><div className="section-head"><Badge tone="violet">Capabilities</Badge><h2 style={{ marginTop: 14 }}>Built like a clinical-grade product.</h2></div></Reveal>
            <div className="grid cols-3">
              {[
                [HeartPulse, "Multiclass heart disease", "Five angiographic grades plus an overall disease probability, from the UCI four-hospital cohort."],
                [Stethoscope, "Coronary artery screen", "Risk factors, ECG and optional labs estimate coronary artery disease, trained on angiography-confirmed cases (Z-Alizadeh Sani)."],
                [Droplets, "Diabetes symptom screen", "Fourteen symptoms and age/sex produce a calibrated screening probability."],
                [Microscope, "Type 1 pattern indicator", "A transparent clinical-rule score with an emergency (DKA) warning and lab-range checks."],
                [ScanSearch, "Explainable by default", "Per-prediction SHAP bars and global importance charts for each model."],
                [SlidersHorizontal, "What-if simulator", "Change blood pressure, cholesterol or other inputs and watch the model’s score respond."],
                [LineChart, "Personal analytics", "Track assessments over time with trends, risk mix and top drivers."],
                [Layers, "Hybrid ensemble", "Random Forest + neural network combined and validated without data leakage."],
                [FileText, "PDF reports", "Printable summary with probabilities, explanation and recommendations."],
                [Mail, "High-risk email alerts", "Optional alerts without any health values in the email body."],
              ].map(([Icon, t, p], i) => (
                <Reveal key={String(t)} delay={(i % 3) * .07}>
                  <Card className="feature"><div className="icon-chip">{(() => { const I = Icon as typeof HeartPulse; return <I size={20} />; })()}</div><h3>{String(t)}</h3><p>{String(p)}</p></Card>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section className="section" id="honesty">
          <div className="container grid cols-2" style={{ alignItems: "center" }}>
            <Reveal>
              <Badge tone="moderate">Transparency</Badge>
              <h2 style={{ marginTop: 14 }}>We tell you what this is, and what it is not.</h2>
              <p>The public datasets behind these models are small and come from specific hospitals. We publish the limits next to the results so nobody mistakes a screening aid for a diagnosis.</p>
              <div className="row"><Button to={user ? "/app/models" : "/register"} icon={<BrainCircuit size={16} />}>Inspect the models</Button></div>
            </Reveal>
            <Reveal delay={.1}>
              <Card large glow>
                <div className="stack">
                  {[["Not a medical device", "Educational screening only; always confirm with a clinician."], ["Heart grades are hard", "Disease present vs absent is far more reliable than the exact grade 1–4."], ["Type 1 is rule-based", "No public dataset pairs Type 1 patients with healthy controls, so we don’t pretend to a trained model."], ["Population limits", "Data comes from 1980s US/European hospitals and a Bangladeshi clinic."]].map(([t, p]) => (
                    <div key={t} className="row" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}><Stethoscope size={18} color="#22d3ee" style={{ marginTop: 4, flex: "none" }} /><div><strong>{t}</strong><p style={{ margin: 0, fontSize: 14 }}>{p}</p></div></div>
                  ))}
                </div>
              </Card>
            </Reveal>
          </div>
        </section>

        <section className="section" style={{ paddingTop: 20 }}>
          <div className="container">
            <Reveal>
              <Card large glow style={{ textAlign: "center", padding: "56px 24px" }}>
                <GaugeIcon size={34} color="#22d3ee" />
                <h2 style={{ marginTop: 14 }}>Check your risk in about two minutes.</h2>
                <p style={{ maxWidth: 520, marginInline: "auto" }}>Create a free account, answer a short form and get a result you can understand and take to your doctor.</p>
                <Button size="lg" variant="primary" to={user ? "/app/assess" : "/register"} icon={<ArrowRight size={18} />}>Get started</Button>
              </Card>
            </Reveal>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="container spread">
          <span>© {new Date().getFullYear()} Clarity Screen · UCP Final Year Project F26DS003</span>
          <span>Educational use only. Not medical advice. <Link to="/login">Sign in</Link></span>
        </div>
      </footer>
    </>
  );
}
