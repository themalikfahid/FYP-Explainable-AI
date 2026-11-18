import { useState } from "react";
import { motion } from "framer-motion";
import { AlertOctagon, CheckCircle2, Microscope, Send } from "lucide-react";
import { Alert, Badge, Button, Card, Field, PageHead, Segmented, ToggleCard, usePageTitle } from "../components/ui";
import { api, ApiError, type T1DInput, type T1DResult } from "../lib/api";

const SYMPTOMS: [keyof T1DInput, string, string][] = [
  ["polyuria", "Frequent urination", "Passing urine much more often, especially at night"],
  ["polydipsia", "Extreme thirst", "Constant, unquenchable thirst"],
  ["weight_loss", "Unexplained weight loss", "Weight dropping without trying"],
  ["fatigue", "Unusual tiredness", "Exhausted despite resting"],
  ["blurred_vision", "Blurred vision", "Vision going out of focus"],
  ["bedwetting", "New bedwetting", "In a child who was previously dry"],
  ["recurrent_infections", "Recurrent infections", "Thrush or skin infections that keep returning"],
  ["abdominal_pain_vomiting", "Stomach pain or vomiting", "Nausea, vomiting or abdominal pain"],
  ["fruity_breath_or_fast_breathing", "Fruity breath / fast breathing", "Sweet-smelling breath or deep rapid breathing"],
  ["family_history_t1d", "Family history of Type 1", "A parent or sibling has Type 1 diabetes"],
  ["other_autoimmune", "Other autoimmune condition", "e.g. thyroid disease or coeliac disease"],
];

const num = (s: string) => (s === "" ? null : Number(s));

export default function T1DAssess() {
  usePageTitle("Type 1 pattern check");
  const [age, setAge] = useState("");
  const [on, setOn] = useState<Record<string, 0 | 1>>({});
  const [weeks, setWeeks] = useState(""); const [bmi, setBmi] = useState<T1DInput["bmi_category"]>("unknown");
  const [fg, setFg] = useState(""); const [rg, setRg] = useState(""); const [a1c, setA1c] = useState("");
  const [res, setRes] = useState<T1DResult | null>(null);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);

  async function run() {
    setErr("");
    const a = Number(age);
    if (!age || !Number.isFinite(a) || a < 1 || a > 100) { setErr("Enter an age between 1 and 100."); return; }
    setBusy(true);
    const flag = (k: string): 0 | 1 => on[k] ?? 0;
    const body: T1DInput = { age: a, polyuria: flag("polyuria"), polydipsia: flag("polydipsia"), weight_loss: flag("weight_loss"), fatigue: flag("fatigue"),
      blurred_vision: flag("blurred_vision"), bedwetting: flag("bedwetting"), recurrent_infections: flag("recurrent_infections"),
      abdominal_pain_vomiting: flag("abdominal_pain_vomiting"), fruity_breath_or_fast_breathing: flag("fruity_breath_or_fast_breathing"),
      symptom_weeks: num(weeks), family_history_t1d: flag("family_history_t1d"), other_autoimmune: flag("other_autoimmune"), bmi_category: bmi,
      fasting_glucose: num(fg), random_glucose: num(rg), hba1c: num(a1c) };
    try { setRes(await api.t1d(body)); window.scrollTo({ top: 0, behavior: "smooth" }); }
    catch (x) { setErr(x instanceof ApiError ? (x.fieldErrors.map((f) => `${f.field}: ${f.message}`).join(" · ") || x.message) : "Request failed."); }
    finally { setBusy(false); }
  }

  const tone = res ? (res.band === "strong" ? "high" : res.band === "possible" ? "moderate" : "low") as "high" | "moderate" | "low" : "low";
  return (
    <>
      <PageHead title="Type 1 pattern check" subtitle="A transparent clinical-criteria score, not a trained model: no public dataset has Type 1 patients with healthy controls." />
      {res && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="stack" style={{ marginBottom: 24 }}>
          {res.emergency_warning && <Alert tone="error" title="Possible emergency (DKA)"><strong>Seek urgent medical care now.</strong> {res.emergency_signs.join(" · ")}</Alert>}
          <Card glow large>
            <div className="spread" style={{ flexWrap: "wrap" }}>
              <div><div className="faint" style={{ fontSize: 12.5 }}>Pattern score</div><div className="mono" style={{ fontSize: "3rem", fontWeight: 700 }}>{res.score}<span className="faint" style={{ fontSize: "1.2rem" }}>/100</span></div></div>
              <Badge tone={tone}>{res.band === "strong" ? "Strong match" : res.band === "possible" ? "Possible match" : "Low match"}</Badge>
            </div>
            <div className="bar" style={{ margin: "14px 0" }}><i style={{ width: `${res.score}%` }} /></div>
            <p>{res.summary}</p>
            {res.meets_diagnostic_range && <Alert tone="warn">A lab value you entered is in the diagnostic range for diabetes. Please see a clinician promptly.</Alert>}
          </Card>
          <div className="grid cols-2" style={{ alignItems: "start" }}>
            <Card><h3>What contributed</h3>
              {res.contributions.length === 0 ? <p>No contributing factors.</p> : res.contributions.map((c) => <div key={c.label} className="spread" style={{ padding: "6px 0" }}><span>{c.label}</span><span className="mono">+{c.points}</span></div>)}
              {res.lab_flags.length > 0 && <div className="chip-list" style={{ marginTop: 12 }}>{res.lab_flags.map((f) => <Badge key={f.label} tone={f.level === "high" ? "high" : "moderate"}>{f.label}</Badge>)}</div>}
            </Card>
            <Card><h3>Next steps</h3><ul style={{ margin: 0, paddingLeft: 20 }}>{res.next_steps.map((s) => <li key={s} style={{ color: "var(--muted)", marginBottom: 6 }}>{s}</li>)}</ul></Card>
          </div>
          {res.cohort_comparison.length > 0 && (
            <Card><h3>How common are these symptoms in diagnosed children?</h3><p style={{ fontSize: 14 }}>{res.cohort_note}</p>
              {res.cohort_comparison.map((c) => <div key={c.symptom} style={{ marginBottom: 10 }}><div className="spread" style={{ fontSize: 14 }}><span>{c.symptom}</span><span className="mono">{(c.share_of_cohort * 100).toFixed(0)}%</span></div><div className="bar"><i style={{ width: `${c.share_of_cohort * 100}%` }} /></div></div>)}
            </Card>
          )}
          <Alert tone="info" title="Limitations">{res.limitations.join(" ")}</Alert>
          <div><Button onClick={() => setRes(null)}>Start over</Button></div>
        </motion.div>
      )}

      {!res && (
        <Card large>
          <div className="stack" style={{ gap: 24 }}>
            <div className="form-grid">
              <Field label="Age" unit="years" htmlFor="t1d-age"><input id="t1d-age" className="input mono" type="number" value={age} onChange={(e) => setAge(e.target.value)} min={1} max={100} /></Field>
              <Field label="Symptoms present for (optional)" unit="weeks" htmlFor="t1d-w"><input id="t1d-w" className="input mono" type="number" value={weeks} onChange={(e) => setWeeks(e.target.value)} min={0} max={520} /></Field>
              <Field label="Body size"><Segmented label="Body size" value={bmi} onChange={setBmi} options={[{ value: "unknown", label: "Unknown" }, { value: "underweight", label: "Under" }, { value: "normal", label: "Normal" }, { value: "overweight", label: "Over" }, { value: "obese", label: "Obese" }]} /></Field>
            </div>
            <div><h3 style={{ marginBottom: 12 }}><Microscope size={18} color="#a78bfa" /> Symptoms and history</h3>
              <div className="form-grid">{SYMPTOMS.map(([k, t, h]) => <ToggleCard key={k} title={t} help={h} on={on[k] === 1} onClick={() => setOn({ ...on, [k]: on[k] === 1 ? 0 : 1 })} />)}</div></div>
            <div><h3 style={{ marginBottom: 12 }}>Lab values (optional)</h3>
              <div className="form-grid">
                <Field label="Fasting glucose" unit="mg/dL" htmlFor="fg"><input id="fg" className="input mono" type="number" value={fg} onChange={(e) => setFg(e.target.value)} /></Field>
                <Field label="Random glucose" unit="mg/dL" htmlFor="rg"><input id="rg" className="input mono" type="number" value={rg} onChange={(e) => setRg(e.target.value)} /></Field>
                <Field label="HbA1c" unit="%" htmlFor="a1c"><input id="a1c" className="input mono" type="number" step="0.1" value={a1c} onChange={(e) => setA1c(e.target.value)} /></Field>
              </div></div>
            {err && <Alert tone="error">{err}</Alert>}
            <div className="spread"><span className="faint row" style={{ gap: 8, fontSize: 13 }}><AlertOctagon size={14} /> Severe vomiting, fast breathing or drowsiness is an emergency.</span>
              <Button variant="primary" size="lg" loading={busy} icon={<Send size={16} />} onClick={run}>Check pattern</Button></div>
          </div>
        </Card>
      )}
      <p className="faint" style={{ fontSize: 12.5, marginTop: 14 }}><CheckCircle2 size={13} style={{ verticalAlign: -2 }} /> Educational only. Only a clinician can diagnose diabetes.</p>
    </>
  );
}
