import { useEffect, useMemo, useState } from "react";
import { Activity, FileUp, Send } from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, Badge, Button, Card, PageHead, Skeleton, Stat, usePageTitle } from "../components/ui";
import { api, type EcgInfo, type EcgResult } from "../lib/api";
import { pct } from "../lib/format";

function parseBeat(text: string): number[] | string {
  const nums = text.split(/[\s,;]+/).filter(Boolean).map(Number);
  if (nums.length === 0) return "Paste 187 comma-separated values first.";
  if (nums.some((n) => !Number.isFinite(n))) return "Some values are not numbers.";
  if (nums.length === 188) nums.pop(); // dataset rows end with the class label
  if (nums.length !== 187) return `A beat needs exactly 187 values (found ${nums.length}).`;
  return nums;
}

export default function ECGAssess() {
  usePageTitle("ECG heartbeat classifier");
  const [info, setInfo] = useState<EcgInfo | null>(null);
  const [beat, setBeat] = useState<number[] | null>(null);
  const [text, setText] = useState("");
  const [res, setRes] = useState<EcgResult | null>(null);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { api.ecgInfo().then(setInfo).catch((e) => setErr(e.message)); }, []);

  async function run(b: number[]) {
    setErr(""); setBusy(true); setBeat(b);
    try { setRes(await api.ecg(b)); } catch (e: any) { setErr(e.message); setRes(null); } finally { setBusy(false); }
  }
  function fromText() { const b = parseBeat(text); if (typeof b === "string") { setErr(b); return; } run(b); }
  async function fromFile(f: File | undefined) {
    if (!f) return;
    if (f.size > 200_000) { setErr("File too large. Upload one beat only."); return; }
    const t = await f.text(); setText(t.trim()); const b = parseBeat(t); if (typeof b === "string") { setErr(b); return; } run(b);
  }

  const maxImp = useMemo(() => Math.max(...(res?.saliency.map((s) => s.importance) ?? [0]), 0.001), [res]);
  const data = beat?.map((v, i) => ({ i, v })) ?? [];
  const probs = res ? Object.entries(res.probabilities).map(([name, v]) => ({ name, v, top: name === res.predicted_label.split(" ")[0] })) : [];
  const topName = res ? Object.entries(res.probabilities).sort((a, b) => b[1] - a[1])[0][0] : "";
  const rep = info?.report;

  return (
    <>
      <PageHead title="ECG heartbeat classifier" subtitle="Classify one heartbeat into five types. Hybrid Random Forest + neural network trained on the MIT-BIH Arrhythmia database." />
      {err && <Alert tone="error">{err}</Alert>}
      {rep && (
        <div className="grid cols-4" style={{ marginBottom: 20 }}>
          <Card><Stat icon={<Activity size={14} />} label="Test accuracy" value={pct(rep.test.hybrid.accuracy, 1)} sub={`${rep.n_test.toLocaleString()} unseen beats`} /></Card>
          <Card><Stat icon={<Activity size={14} />} label="Balanced accuracy" value={pct(rep.test.hybrid.balanced_accuracy, 1)} sub="mean recall over 5 classes" /></Card>
          <Card><Stat icon={<Activity size={14} />} label="Abnormal vs normal" value={pct(rep.abnormal_vs_normal.accuracy, 1)} sub={`sens ${pct(rep.abnormal_vs_normal.sensitivity)} · spec ${pct(rep.abnormal_vs_normal.specificity)}`} /></Card>
          <Card><Stat icon={<Activity size={14} />} label="When confident" value={<span style={{ color: "#34d399" }}>{(() => { const r = rep.gate.test_table.find((x) => info!.threshold != null && Math.abs(x.min_confidence - info!.threshold) < 1e-9); return r ? pct(r.accuracy, 1) : "—"; })()}</span>} sub={info?.threshold != null ? `confidence ≥ ${pct(info.threshold)}` : ""} /></Card>
        </div>
      )}
      <div className="grid" style={{ gridTemplateColumns: "minmax(0,1fr) minmax(0,1.2fr)", gap: 20 }}>
        <Card>
          <div className="card-title"><h3>1. Choose a beat</h3></div>
          <p style={{ fontSize: 14 }}>Try a real beat from the test set, or paste or upload your own (187 values scaled 0–1).</p>
          <div className="row" style={{ flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
            {!info ? <Skeleton h={36} /> : Object.entries(info.samples).map(([k, s]) => (
              <Button key={k} size="sm" onClick={() => { setText(s.beat.join(", ")); run(s.beat); }}>{s.label}</Button>))}
          </div>
          <label htmlFor="ecg-text" className="faint" style={{ fontSize: 13 }}>Beat values (comma or space separated)</label>
          <textarea id="ecg-text" className="input" rows={5} value={text} onChange={(e) => setText(e.target.value)} placeholder="0.97, 0.92, 0.68, 0.24, …" style={{ width: "100%", fontFamily: "var(--mono, monospace)", fontSize: 12 }} />
          <div className="row" style={{ gap: 8, marginTop: 10, flexWrap: "wrap" }}>
            <Button variant="primary" icon={<Send size={16} />} loading={busy} onClick={fromText}>Classify beat</Button>
            <label className="btn" style={{ cursor: "pointer" }}><FileUp size={16} /> Upload CSV
              <input type="file" accept=".csv,.txt" hidden onChange={(e) => fromFile(e.target.files?.[0])} /></label>
          </div>
        </Card>
        <Card glow>
          <div className="card-title"><h3>2. Result</h3>{res && <Badge tone={res.confidence.tier === "confident" ? "low" : "moderate"}>{res.confidence.tier}</Badge>}</div>
          {!res ? <p className="faint">Pick a sample beat or paste one to see the prediction.</p> : (
            <div className="stack" style={{ gap: 12 }}>
              <div><div className="faint" style={{ fontSize: 13 }}>Predicted type</div>
                <h2 style={{ margin: "2px 0" }}>{res.predicted_label}</h2>
                <span className="mono">confidence {pct(res.confidence.value, 1)}</span>
                {res.confidence.tier === "confident" && res.confidence.expected_accuracy_if_confident != null &&
                  <span className="faint"> · confident calls were {pct(res.confidence.expected_accuracy_if_confident, 1)} correct on the test set</span>}
              </div>
              {res.warnings.map((w) => <Alert key={w} tone="warn">{w}</Alert>)}
            </div>
          )}
        </Card>
      </div>
      {res && beat && (
        <div className="grid" style={{ gridTemplateColumns: "minmax(0,1.4fr) minmax(0,1fr)", gap: 20, marginTop: 20 }}>
          <Card>
            <div className="card-title"><h3>Beat signal and what the model relied on</h3><Badge tone="violet">occlusion saliency</Badge></div>
            <div style={{ height: 260 }}>
              <ResponsiveContainer>
                <AreaChart data={data} margin={{ top: 10, right: 16, left: -14, bottom: 0 }}>
                  <CartesianGrid vertical={false} />
                  {res.saliency.filter((s) => s.importance > 0.08 * maxImp && s.importance > 0.01).map((s) => (
                    <ReferenceArea key={s.start} x1={s.start} x2={s.end - 1} fill="#fb7185" fillOpacity={Math.min(0.55, 0.12 + 0.5 * (s.importance / maxImp))} stroke="none" />))}
                  <XAxis dataKey="i" tickLine={false} axisLine={false} /><YAxis domain={[0, 1]} tickLine={false} axisLine={false} />
                  <Tooltip /><Area type="monotone" dataKey="v" stroke="#22d3ee" strokeWidth={2} fill="#22d3ee" fillOpacity={0.12} isAnimationActive={false} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <p className="faint" style={{ fontSize: 13 }}>Red bands: removing that part of the beat lowered the predicted probability the most. This shows how the model behaves, not a physiological cause.</p>
          </Card>
          <Card>
            <div className="card-title"><h3>Class probabilities</h3></div>
            <div style={{ height: 260 }}>
              <ResponsiveContainer>
                <BarChart data={probs} layout="vertical" margin={{ left: 20, right: 20 }}>
                  <XAxis type="number" domain={[0, 1]} tickFormatter={(v) => `${v * 100}%`} tickLine={false} axisLine={false} />
                  <YAxis type="category" dataKey="name" width={110} tickLine={false} axisLine={false} />
                  <Tooltip formatter={(v: number) => pct(v, 1)} />
                  <Bar dataKey="v" radius={6} isAnimationActive={false}>{probs.map((p) => <Cell key={p.name} fill={p.name === topName ? "#22d3ee" : "#6366f1"} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="mono" style={{ fontSize: 13 }}>P(any abnormal beat) = {pct(res.abnormal_probability, 1)}</p>
          </Card>
        </div>
      )}
      {rep && (
        <Card style={{ marginTop: 20 }}>
          <div className="card-title"><h3>Per-class performance (unseen test beats)</h3></div>
          <div className="table-scroll"><table className="table"><thead><tr><th>Class</th><th className="num">Beats</th><th className="num">Precision</th><th className="num">Recall</th><th className="num">F1</th></tr></thead>
            <tbody>{Object.values(rep.test.hybrid.per_class).map((c) => <tr key={c.label}><td>{c.label}</td><td className="num">{c.support.toLocaleString()}</td><td className="num">{pct(c.precision, 1)}</td><td className="num">{pct(c.recall, 1)}</td><td className="num">{pct(c.f1, 1)}</td></tr>)}</tbody></table></div>
          <Alert tone="warn" title="Honest limitations">Normal beats make up 83% of the test set, so overall accuracy flatters the model; check the per-class recall. The rare fusion and supraventricular classes are weaker. The data is single-lead recordings from 47 patients and the train/test files are not split by patient, so accuracy on new patients is likely lower. Educational prototype, not a medical device.</Alert>
        </Card>
      )}
    </>
  );
}
