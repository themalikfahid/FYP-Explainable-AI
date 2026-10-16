import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type PredictionSummary } from "../api";
import { useAuth } from "../auth";
import { RiskBadge } from "../components/Explain";

function Trend({ items }: { items: PredictionSummary[] }) {
  // risk score over time (oldest -> newest), one line per disease
  const W = 320, H = 90, pad = 8;
  const series = (["diabetes", "heart"] as const).map((d) => ({
    d, pts: items.filter((i) => i.disease === d).slice().reverse(),
  })).filter((s) => s.pts.length > 0);
  if (!series.length) return null;
  return (
    <svg className="trend" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label="Risk score of your recent assessments over time, from 0% to 100%">
      <line x1={pad} x2={W - pad} y1={H - pad - (H - 2 * pad) * 0.7} y2={H - pad - (H - 2 * pad) * 0.7} className="trend-th" />
      <line x1={pad} x2={W - pad} y1={H - pad - (H - 2 * pad) * 0.3} y2={H - pad - (H - 2 * pad) * 0.3} className="trend-th" />
      {series.map(({ d, pts }) => {
        const xy = pts.map((p, i) => [pad + (pts.length === 1 ? (W - 2 * pad) / 2 : (i * (W - 2 * pad)) / (pts.length - 1)),
          H - pad - p.risk_score * (H - 2 * pad)]);
        return (
          <g key={d} className={`trend-${d}`}>
            <polyline points={xy.map((p) => p.join(",")).join(" ")} fill="none" />
            {xy.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={3} />)}
          </g>
        );
      })}
    </svg>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [items, setItems] = useState<PredictionSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    api.history(undefined, 10).then((r) => { setItems(r.items); setTotal(r.total); })
      .catch((e) => setError(e.message));
  }, []);

  const latest = (d: string) => items?.find((i) => i.disease === d);

  return (
    <div className="page">
      <h1>Hello, {user?.full_name.split(" ")[0]}</h1>
      <div className="dash-grid">
        <Link to="/assess/diabetes" className="start-card">
          <h2>Diabetes symptom screen</h2>
          <p>Age, sex and 14 yes/no symptom questions. About 2 minutes.</p>
          {latest("diabetes") && <p className="fine">Last result: <RiskBadge level={latest("diabetes")!.risk_level} /></p>}
          <span className="start-go">Start screen</span>
        </Link>
        <Link to="/assess/heart" className="start-card">
          <h2>Heart disease classification</h2>
          <p>Uses results from a clinical exam and exercise stress test (blood pressure, cholesterol, ECG, heart rate).</p>
          {latest("heart") && <p className="fine">Last result: <RiskBadge level={latest("heart")!.risk_level} /></p>}
          <span className="start-go">Start assessment</span>
        </Link>
        <section className="panel">
          <h2>Recent results</h2>
          {error && <p className="banner error" role="alert">{error}</p>}
          {items === null && !error && <p className="loading" role="status">Loading…</p>}
          {items && items.length === 0 && <p>You have no saved assessments yet. Start with one of the screens above.</p>}
          {items && items.length > 0 && (
            <>
              <Trend items={items} />
              <p className="fine trend-key"><span className="key-diabetes">Diabetes</span> <span className="key-heart">Heart</span> risk score; dashed lines mark the 30% and 70% bands.</p>
              <ul className="mini-list">
                {items.slice(0, 5).map((i) => (
                  <li key={i.id}><Link to={`/history/${i.id}`}>{i.disease === "heart" ? "Heart" : "Diabetes"}, {new Date(i.created_at).toLocaleDateString()}</Link>
                    <RiskBadge level={i.risk_level} /></li>
                ))}
              </ul>
              <Link to="/history">See all {total} assessments</Link>
            </>
          )}
        </section>
        <Link to="/tools" className="start-card quiet">
          <h2>BMI and lifestyle score</h2>
          <p>Check BMI and a 0 to 100 lifestyle score without running a screen.</p>
          <span className="start-go">Open calculator</span>
        </Link>
      </div>
    </div>
  );
}
