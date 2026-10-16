import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type Contribution, type FeatureMeta, type Prediction } from "../api";
import { ProbabilityTable, RiskBadge, ShapLedger, formatValue } from "./Explain";

const CATEGORY_NAMES: Record<string, string> = {
  follow_up: "Follow-up", risk_mitigation: "Lower your risk", diet: "Diet", activity: "Physical activity", sleep: "Sleep",
};
const ALERT_TEXT: Record<string, string> = {
  sent: "A high-risk alert email was accepted by the mail server.",
  written_to_file: "A high-risk alert was written to the local test outbox (email is in test mode).",
  disabled: "Email alerts are switched off on this server, so no email was sent.",
  failed: "The high-risk alert email could not be sent. Check the server's email settings.",
  pending: "A high-risk alert email is being prepared.",
};

export default function PredictionView({ p, meta, onDeleted }: { p: Prediction; meta: FeatureMeta; onDeleted?: () => void }) {
  const r = p.result;
  const task = meta[p.disease];
  const exp = r.explanation;
  const [view, setView] = useState<string>(p.disease === "heart" ? "any" : String(exp?.explained_class ?? 1));
  const [busy, setBusy] = useState<"" | "pdf" | "delete">("");
  const [error, setError] = useState("");

  const ledger = useMemo(() => {
    if (!exp) return null;
    let base: number, shap: Record<string, number>, outcome: string;
    if (view === "any" && exp.any_disease) {
      base = exp.any_disease.base_value; shap = exp.any_disease.shap; outcome = "any heart disease (grades 1-4)";
    } else {
      base = exp.per_class[view].base_value; shap = exp.per_class[view].shap; outcome = task.class_labels[view];
    }
    const contributions: Contribution[] = Object.entries(shap)
      .map(([feature, s]) => ({ feature, shap: s, value: p.inputs[feature] ?? null }))
      .sort((a, b) => Math.abs(b.shap) - Math.abs(a.shap));
    const final = base + contributions.reduce((s, c) => s + c.shap, 0);
    return { base, final, contributions, outcome };
  }, [exp, view, p.inputs, task.class_labels]);

  async function pdf() {
    if (!p.id) return;
    setBusy("pdf"); setError("");
    try { await api.downloadReport(p.id); } catch (e) { setError(e instanceof ApiError ? e.message : "The report could not be created."); }
    setBusy("");
  }
  async function del() {
    if (!p.id || !window.confirm("Delete this assessment and its report? This can't be undone.")) return;
    setBusy("delete"); setError("");
    try { await api.deletePrediction(p.id); onDeleted?.(); } catch (e) { setError(e instanceof ApiError ? e.message : "Delete failed."); setBusy(""); }
  }

  const grouped = r.recommendations.items.reduce<Record<string, typeof r.recommendations.items>>((acc, it) => {
    (acc[it.category] ||= []).push(it); return acc;
  }, {});

  return (
    <article className="result" aria-labelledby="result-title">
      <header className={`result-head lvl-${p.risk_level}`}>
        <div>
          <p className="result-kicker">{p.disease === "heart" ? "Heart disease classification" : "Diabetes symptom screen"}, {new Date(p.created_at).toLocaleString()}</p>
          <h1 id="result-title"><RiskBadge level={p.risk_level} /> <span className="result-score">{(p.risk_score * 100).toFixed(1)}%</span></h1>
          <p className="result-def">{r.risk_score_definition}. Most likely class: <strong>{r.predicted_label}</strong>.</p>
        </div>
        <div className="result-actions">
          {p.id && <button className="btn" onClick={pdf} disabled={busy !== ""}>{busy === "pdf" ? "Creating PDF…" : "Download PDF report"}</button>}
          <Link className="btn ghost" to={`/assess/${p.disease}`}>New assessment</Link>
          {p.id && <button className="btn danger ghost" onClick={del} disabled={busy !== ""}>{busy === "delete" ? "Deleting…" : "Delete"}</button>}
        </div>
      </header>
      {error && <p className="banner error" role="alert">{error}</p>}
      {p.alert_status && <p className="banner info">{ALERT_TEXT[p.alert_status] ?? p.alert_status}</p>}
      {r.warnings.length > 0 && (
        <ul className="banner warn" aria-label="Reliability warnings">{r.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
      )}

      <div className="result-grid">
        <section className="panel span-2" aria-labelledby="why">
          <div className="panel-head">
            <h2 id="why">Why the model said this</h2>
            {exp && (
              <label className="inline-select">Explain
                <select value={view} onChange={(e) => setView(e.target.value)}>
                  {p.disease === "heart" && <option value="any">Any heart disease</option>}
                  {Object.entries(task.class_labels).map(([c, l]) => <option key={c} value={c}>{l}</option>)}
                </select>
              </label>
            )}
          </div>
          {ledger ? (
            <>
              <ShapLedger contributions={ledger.contributions} base={ledger.base} final={ledger.final} spec={task.spec} outcome={ledger.outcome} />
              {exp?.summary && view === String(exp.explained_class) && (
                <ul className="plain">{exp.summary.map((s) => <li key={s}>{s}</li>)}</ul>
              )}
              <p className="fine">SHAP values show how this model used your inputs, measured on the full RF + ANN ensemble.
                They are not proof that a factor causes disease.</p>
            </>
          ) : <p>No explanation is available for this record.</p>}
        </section>

        <section className="panel" aria-labelledby="probs">
          <h2 id="probs">Probabilities</h2>
          <ProbabilityTable probs={r.probabilities} rf={r.components.random_forest} ann={r.components.ann}
            labels={task.class_labels} predicted={r.predicted_class} />
          <p className="fine">{r.probability_note} Bands: low below {(r.risk_thresholds.low_below * 100).toFixed(0)}%,
            high from {(r.risk_thresholds.high_at_or_above * 100).toFixed(0)}%.</p>
        </section>

        <section className="panel" aria-labelledby="inputs">
          <h2 id="inputs">Your inputs</h2>
          <dl className="kv">
            {task.features.map((f) => (
              <div key={f}><dt>{task.spec[f].label}</dt><dd>{formatValue(task.spec[f], p.inputs[f])}</dd></div>
            ))}
          </dl>
        </section>

        <section className="panel span-2" aria-labelledby="recs">
          <h2 id="recs">What you can do next</h2>
          {(r.recommendations.bmi || r.recommendations.lifestyle_score) && (
            <div className="scorecards">
              {r.recommendations.bmi && (
                <div className="scorecard"><span className="sc-num">{r.recommendations.bmi.bmi}</span>
                  <span className="sc-label">BMI: {r.recommendations.bmi.category}</span></div>
              )}
              {r.recommendations.lifestyle_score && (
                <div className="scorecard"><span className="sc-num">{r.recommendations.lifestyle_score.score}<small>/100</small></span>
                  <span className="sc-label">Lifestyle score: {r.recommendations.lifestyle_score.band}</span></div>
              )}
            </div>
          )}
          <div className="rec-groups">
            {Object.entries(grouped).map(([cat, items]) => (
              <div key={cat} className="rec-group">
                <h3>{CATEGORY_NAMES[cat] ?? cat}</h3>
                <ul>
                  {items.map((it) => (
                    <li key={it.text} className={`prio-${it.priority}`}>
                      <p>{it.text}</p>
                      <p className="fine">Based on: {it.source}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <p className="disclaimer">{r.recommendations.disclaimer}</p>
        </section>
      </div>
      <p className="fine">Model {r.model.version}. Held-out test results: {Object.entries(r.model.test_metrics)
        .filter(([k]) => k !== "n_test").map(([k, v]) => `${k.replace(/_/g, " ")} ${Number(v).toFixed(3)}`).join(", ")}
        {" "}(n = {r.model.test_metrics.n_test}). <Link to="/models">How the models were evaluated</Link>.</p>
    </article>
  );
}
