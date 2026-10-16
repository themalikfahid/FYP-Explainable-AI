import { useState, type FormEvent } from "react";
import { api, ApiError, type BMIResult, type LifestyleScore } from "../api";
import { LIFESTYLE_SPEC, LifestyleFields, SMOKING_SPEC, lifestyleFrom, validateAll, type Values } from "../components/Fields";

const COMPONENT_NAMES: Record<string, string> = {
  physical_activity: "Physical activity", sleep: "Sleep", diet_fruit_veg: "Fruit and vegetables", smoking: "Smoking", alcohol: "Alcohol",
};

export default function Tools() {
  const [values, setValues] = useState<Values>({ asian_bmi_cutoffs: "0" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [res, setRes] = useState<{ lifestyle_score: LifestyleScore; bmi: BMIResult } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const errs = validateAll({ ...LIFESTYLE_SPEC, smoking: SMOKING_SPEC }, values);
    setErrors(errs);
    if (Object.keys(errs).length) { setError("Please fix the highlighted fields."); return; }
    setBusy(true); setError("");
    try { setRes(await api.lifestyleScore(lifestyleFrom(values))); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Calculation failed."); }
    setBusy(false);
  }

  return (
    <div className="page narrow">
      <h1>BMI and lifestyle score</h1>
      <p className="lede">A quick check of body mass index and five everyday habits. Nothing on this page is saved.</p>
      <form onSubmit={submit} noValidate>
        {error && <p className="banner error" role="alert">{error}</p>}
        <LifestyleFields values={values} errors={errors} set={(k, v) => { setValues((old) => ({ ...old, [k]: v })); setErrors((e) => { const n = { ...e }; delete n[k]; return n; }); }} />
        <div className="form-foot"><button className="btn" disabled={busy}>{busy ? "Calculating…" : "Calculate"}</button></div>
      </form>
      {res && (
        <section className="panel" aria-live="polite" aria-labelledby="res-h">
          <h2 id="res-h">Your results</h2>
          <div className="scorecards">
            <div className="scorecard"><span className="sc-num">{res.bmi.bmi}</span><span className="sc-label">BMI: {res.bmi.category}</span></div>
            <div className="scorecard"><span className="sc-num">{res.lifestyle_score.score}<small>/100</small></span><span className="sc-label">Lifestyle score: {res.lifestyle_score.band}</span></div>
          </div>
          <p>Healthy weight range for your height ({res.bmi.cutoffs}): <strong>{res.bmi.healthy_weight_range_kg[0]} to {res.bmi.healthy_weight_range_kg[1]} kg</strong>.</p>
          <ul className="components">
            {Object.entries(res.lifestyle_score.components).map(([k, c]) => (
              <li key={k}><span>{COMPONENT_NAMES[k]}</span>
                <span className="imp-track"><span style={{ width: `${(c.points / c.max) * 100}%` }} /></span>
                <span>{c.points} of {c.max}</span></li>
            ))}
          </ul>
          <p className="fine">{res.bmi.note}</p>
          <p className="fine">{res.lifestyle_score.note}</p>
        </section>
      )}
    </div>
  );
}
