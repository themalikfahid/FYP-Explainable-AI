import type { Contribution, FieldSpec } from "../api";

export function formatValue(spec: FieldSpec | undefined, v: number | null | undefined): string {
  if (v === null || v === undefined) return "Not provided";
  if (!spec) return String(v);
  if (spec.options) return spec.options.find((o) => Number(o.value) === Number(v))?.label ?? String(v);
  return `${v}${spec.unit ? ` ${spec.unit}` : ""}`;
}

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
const pp = (x: number) => `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(1)}`;

/**
 * The contribution ledger: a SHAP readout that starts at the model's average
 * probability, lists each input's push up or down, and ends at this person's
 * probability. Bars diverge from a centre line; red raises, green lowers.
 */
export function ShapLedger({ contributions, base, final, spec, outcome, limit = 8 }: {
  contributions: Contribution[]; base: number; final: number;
  spec: Record<string, FieldSpec>; outcome: string; limit?: number;
}) {
  const shown = contributions.slice(0, limit);
  const rest = contributions.slice(limit).reduce((s, c) => s + c.shap, 0);
  const maxAbs = Math.max(1e-9, ...shown.map((c) => Math.abs(c.shap)), Math.abs(rest));
  return (
    <figure className="ledger" aria-label={`How each input changed the estimated probability of ${outcome}`}>
      <div className="ledger-ends">
        <div><span className="ledger-num">{pct(base)}</span><span className="ledger-cap">average across the reference sample</span></div>
        <div className="ledger-arrow" aria-hidden="true" />
        <div><span className="ledger-num strong">{pct(final)}</span><span className="ledger-cap">this assessment</span></div>
      </div>
      <p className="ledger-outcome">Probability of <strong>{outcome}</strong>, in percentage points</p>
      <ol className="ledger-rows">
        {shown.map((c) => {
          const w = (Math.abs(c.shap) / maxAbs) * 50;
          const up = c.shap >= 0;
          return (
            <li key={c.feature} className="ledger-row">
              <span className="ledger-label">
                <span>{spec[c.feature]?.label ?? c.feature}</span>
                <span className="ledger-val">{formatValue(spec[c.feature], c.value)}</span>
              </span>
              <span className="ledger-track" aria-hidden="true">
                <span className={up ? "bar up" : "bar down"}
                  style={up ? { left: "50%", width: `${w}%` } : { left: `${50 - w}%`, width: `${w}%` }} />
              </span>
              <span className={up ? "ledger-pp up" : "ledger-pp down"}>{pp(c.shap)}</span>
            </li>
          );
        })}
        {contributions.length > limit && (
          <li className="ledger-row muted">
            <span className="ledger-label"><span>{contributions.length - limit} other inputs combined</span></span>
            <span className="ledger-track" aria-hidden="true" />
            <span className="ledger-pp">{pp(rest)}</span>
          </li>
        )}
      </ol>
    </figure>
  );
}

export function GlobalImportance({ ranked, spec }: { ranked: Record<string, number>; spec: Record<string, FieldSpec> }) {
  const entries = Object.entries(ranked);
  const max = Math.max(1e-9, ...entries.map(([, v]) => v));
  return (
    <ol className="importance">
      {entries.map(([f, v]) => (
        <li key={f}>
          <span className="imp-label">{spec[f]?.label ?? f}</span>
          <span className="imp-track"><span style={{ width: `${(v / max) * 100}%` }} /></span>
          <span className="imp-val">{(v * 100).toFixed(1)} pp</span>
        </li>
      ))}
    </ol>
  );
}

export function RiskBadge({ level }: { level: "low" | "moderate" | "high" }) {
  const text = { low: "Low risk", moderate: "Moderate risk", high: "High risk" }[level];
  return <span className={`risk risk-${level}`}>{text}</span>;
}

export function ProbabilityTable({ probs, rf, ann, labels, predicted }: {
  probs: Record<string, number>; rf: Record<string, number>; ann: Record<string, number>;
  labels: Record<string, string>; predicted: number;
}) {
  return (
    <table className="prob-table">
      <caption className="sr-only">Estimated probability per class from the hybrid model and its two components</caption>
      <thead><tr><th scope="col">Class</th><th scope="col">Hybrid</th><th scope="col">Random Forest</th><th scope="col">ANN</th></tr></thead>
      <tbody>
        {Object.entries(probs).map(([c, p]) => (
          <tr key={c} className={Number(c) === predicted ? "is-pred" : undefined}>
            <th scope="row">{labels[c]}</th>
            <td><span className="pbar"><span style={{ width: `${p * 100}%` }} /></span>{pct(p)}</td>
            <td>{pct(rf[c])}</td>
            <td>{pct(ann[c])}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
