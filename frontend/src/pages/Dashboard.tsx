import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Activity, ArrowDownRight, ArrowRight, ArrowUpRight, ClipboardPlus, HeartPulse, Droplets, Minus, ShieldCheck, TrendingUp, Zap } from "lucide-react";
import { Alert, Button, Card, Empty, PageHead, RiskBadge, Skeleton, Stat, usePageTitle } from "../components/ui";
import { api, type Analytics } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateTime, pct, riskColor, shortDate, taskName } from "../lib/format";

const TREND = { up: <ArrowUpRight size={16} color="#fb7185" />, down: <ArrowDownRight size={16} color="#34d399" />, steady: <Minus size={16} color="#9fb0d4" /> };

function Tip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return <div className="chart-tip"><div className="mono">{pct(p.score)}</div><div className="faint">{p.label}</div></div>;
}

export default function Dashboard() {
  usePageTitle("Dashboard");
  const { user } = useAuth();
  const [data, setData] = useState<Analytics | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.analytics().then(setData).catch((e) => setErr(e.message)); }, []);

  const trend = data ? Object.entries(data.series).flatMap(([d, pts]) => pts.map((p) => ({ ...p, disease: d }))).sort((a, b) => +new Date(a.at) - +new Date(b.at))
    .map((p) => ({ score: p.risk_score, [p.disease]: p.risk_score, label: `${taskName(p.disease)} · ${shortDate(p.at)}`, date: shortDate(p.at) })) : [];
  const dist = data ? (["low", "moderate", "high"] as const).map((k) => ({ name: k, value: data.risk_distribution[k], color: riskColor[k] })) : [];
  const first = user?.full_name.split(" ")[0];

  return (
    <>
      <PageHead title={<>Hello, <span className="grad-text">{first}</span></>} subtitle="Your screening overview. Scores are model estimates, not diagnoses."
        actions={<Button variant="primary" to="/app/assess" icon={<ClipboardPlus size={16} />}>New assessment</Button>} />
      {err && <Alert tone="error">{err}</Alert>}

      <div className="grid" style={{ marginBottom: 20, gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))" }}>
        {!data ? [0, 1, 2, 3].map((i) => <Card key={i}><Skeleton h={90} /></Card>) : <>
          <Card><Stat icon={<Activity size={14} />} label="Assessments" value={data.total_assessments} sub="saved to your account" /></Card>
          {(["diabetes", "heart", "cad"] as const).map((t) => {
            const l = data.latest[t];
            return (
              <Card key={t}>
                <Stat icon={t === "diabetes" ? <Droplets size={14} /> : <HeartPulse size={14} />} label={t === "heart" ? "Heart disease" : t === "cad" ? "Coronary artery" : "Diabetes screen"}
                  value={l ? <span style={{ color: riskColor[l.risk_level] }}>{pct(l.risk_score)}</span> : <span className="faint">—</span>}
                  sub={l ? <span className="row" style={{ gap: 6 }}><RiskBadge level={l.risk_level} />{l.trend && TREND[l.trend]}</span> : "no assessment yet"} />
              </Card>
            );
          })}
          <Card><Stat icon={<ShieldCheck size={14} />} label="High-risk results" value={<span style={{ color: data.risk_distribution.high ? "#fb7185" : undefined }}>{data.risk_distribution.high}</span>} sub="worth a clinician check" /></Card>
        </>}
      </div>

      {data && data.total_assessments === 0 ? (
        <Card large glow><Empty icon={<Zap size={26} />} title="Run your first assessment"
          action={<Button variant="primary" to="/app/assess" icon={<ArrowRight size={16} />}>Start now</Button>}>
          Choose heart disease, diabetes or the Type 1 pattern check. It takes about two minutes.</Empty></Card>
      ) : data && (
        <div className="grid dash">
          <Card>
            <div className="card-title"><h3><TrendingUp size={18} color="#22d3ee" /> Risk trend</h3><span className="faint" style={{ fontSize: 13 }}>all assessments</span></div>
            <div style={{ height: 280 }}>
              <ResponsiveContainer>
                <AreaChart data={trend.map((t, i) => ({ ...t, date: `${t.date} #${i + 1}` }))} margin={{ top: 10, right: 24, left: -14, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gd" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#22d3ee" stopOpacity={.5} /><stop offset="1" stopColor="#22d3ee" stopOpacity={0} /></linearGradient>
                    <linearGradient id="gh" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fb7185" stopOpacity={.5} /><stop offset="1" stopColor="#fb7185" stopOpacity={0} /></linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="date" tickLine={false} axisLine={false} />
                  <YAxis domain={[0, 1]} tickFormatter={(v) => `${v * 100}%`} tickLine={false} axisLine={false} />
                  <Tooltip content={<Tip />} />
                  <Area type="monotone" dataKey="diabetes" stroke="#22d3ee" strokeWidth={2.5} fill="url(#gd)" connectNulls isAnimationActive={false} dot={{ r: 4, fill: "#22d3ee" }} activeDot={{ r: 6 }} />
                  <Area type="monotone" dataKey="cad" stroke="#f59e0b" strokeWidth={2.5} fill="none" connectNulls isAnimationActive={false} dot={{ r: 4, fill: "#f59e0b" }} activeDot={{ r: 6 }} />
                  <Area type="monotone" dataKey="heart" stroke="#fb7185" strokeWidth={2.5} fill="url(#gh)" connectNulls isAnimationActive={false} dot={{ r: 4, fill: "#fb7185" }} activeDot={{ r: 6 }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="legend"><span><i style={{ background: "#22d3ee" }} />Diabetes screen</span><span><i style={{ background: "#fb7185" }} />Heart disease</span><span><i style={{ background: "#f59e0b" }} />Coronary artery</span></div>
          </Card>
          <Card>
            <div className="card-title"><h3>Risk mix</h3></div>
            <div style={{ height: 190 }}>
              <ResponsiveContainer>
                <PieChart><Pie data={dist} dataKey="value" innerRadius={55} outerRadius={80} paddingAngle={4} stroke="none">{dist.map((d) => <Cell key={d.name} fill={d.color} />)}</Pie><Tooltip /></PieChart>
              </ResponsiveContainer>
            </div>
            <div className="legend" style={{ justifyContent: "center" }}>{dist.map((d) => <span key={d.name}><i style={{ background: d.color }} />{d.name} · {d.value}</span>)}</div>
          </Card>

          <Card>
            <div className="card-title"><h3>Recent assessments</h3><Link to="/app/history" className="row" style={{ gap: 6, fontSize: 13.5 }}>View all <ArrowRight size={14} /></Link></div>
            <div className="table-scroll"><table className="table">
              <thead><tr><th>Assessment</th><th>Date</th><th className="num">Score</th><th>Level</th></tr></thead>
              <tbody>{data.recent.map((r) => (
                <tr key={r.id}><td><Link to={`/app/result/${r.id}`}>{taskName(r.disease)}</Link></td><td className="muted">{dateTime(r.at)}</td><td className="num">{pct(r.risk_score)}</td><td><RiskBadge level={r.risk_level} /></td></tr>
              ))}</tbody>
            </table></div>
          </Card>
          <Card>
            <div className="card-title"><h3>What drove your latest results</h3></div>
            {Object.keys(data.top_drivers).length === 0 ? <p>No explanation data yet.</p> : Object.entries(data.top_drivers).map(([d, items]) => (
              <div key={d} style={{ marginBottom: 14 }}>
                <div className="label" style={{ marginBottom: 8 }}>{taskName(d)}</div>
                <div className="chip-list">{items.length ? items.map((i) => <span key={i.feature} className="badge cyan">{i.label} +{(i.shap * 100).toFixed(0)}</span>) : <span className="faint">No factor raised the score.</span>}</div>
              </div>
            ))}
          </Card>
        </div>
      )}
    </>
  );
}
