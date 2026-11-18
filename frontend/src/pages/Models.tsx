import { useEffect, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BrainCircuit, Database, Target } from "lucide-react";
import { Alert, Badge, Card, PageHead, Segmented, Skeleton, Stat, usePageTitle } from "../components/ui";
import { api, type OofReport, type Task } from "../lib/api";
import { pct, taskName } from "../lib/format";

const tipStyle = { background: "#0e1830", border: "1px solid rgba(120,150,220,.3)", borderRadius: 12 };

function Confusion({ m, labels }: { m: number[][]; labels: string[] }) {
  const max = Math.max(...m.flat(), 1);
  return (
    <div className="table-scroll"><table className="table" style={{ textAlign: "center" }}>
      <thead><tr><th>Actual ↓ / Predicted →</th>{labels.map((l) => <th key={l} className="num">{l}</th>)}</tr></thead>
      <tbody>{m.map((row, i) => <tr key={i}><td style={{ textAlign: "left" }}>{labels[i]}</td>{row.map((v, j) => <td key={j} className="num" style={{ background: `rgba(34,211,238,${(v / max) * (i === j ? .5 : .28)})`, fontWeight: i === j ? 700 : 400 }}>{v}</td>)}</tr>)}</tbody>
    </table></div>
  );
}

export default function Models() {
  usePageTitle("Model transparency");
  const [task, setTask] = useState<Task>("diabetes");
  const [info, setInfo] = useState<any>(null); const [err, setErr] = useState("");
  useEffect(() => { setInfo(null); api.modelInfo(task).then(setInfo).catch((e) => setErr(e.message)); }, [task]);
  const cv: OofReport | undefined = info?.cross_validated;
  const heart = task === "heart";
  const labels = heart ? ["0", "1", "2", "3", "4"] : ["Negative", "Positive"];

  const gateRows = cv?.gate.table.map((r) => ({ conf: `${(r.min_confidence * 100).toFixed(0)}%`, Accuracy: +(r.accuracy * 100).toFixed(1), Coverage: +(r.coverage * 100).toFixed(1) })) ?? [];
  const gradeRows = cv?.gate_grade?.table.map((r) => ({ conf: `${(r.min_confidence * 100).toFixed(0)}%`, Accuracy: +(r.accuracy * 100).toFixed(1), Coverage: +(r.coverage * 100).toFixed(1) })) ?? [];
  const shap = info ? Object.entries(info.global_shap.mean_abs_shap_overall as Record<string, number>).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([k, v]) => ({ name: k, v: +v.toFixed(4) })) : [];
  const calib = info ? (info.calibration?.hybrid ?? []).filter((b: any) => b.count > 0).map((b: any) => ({ bin: b.bin, Predicted: +(b.mean_confidence * 100).toFixed(1), Observed: +(b.accuracy * 100).toFixed(1) })) : [];
  const test = info?.test_metrics?.hybrid;
  const gate = cv?.gate.table.find((r) => r.min_confidence === cv.gate.threshold);

  return (
    <>
      <PageHead title="Model transparency" subtitle="Every number below was measured, not assumed. Out-of-fold cross-validation on all unique records."
        actions={<Segmented label="Model" value={task} onChange={setTask} options={[{ value: "diabetes", label: "Diabetes" }, { value: "heart", label: "Heart" }, { value: "cad", label: "Coronary" }]} />} />
      {err && <Alert tone="error">{err}</Alert>}
      {!info || !cv ? <div className="stack"><Skeleton h={120} /><Skeleton h={320} /></div> : (
        <div className="stack" style={{ gap: 20 }}>
          <div className="grid cols-4">
            <Card><Stat icon={<Target size={14} />} label={heart ? "5-grade accuracy (CV)" : "Accuracy (CV)"} value={pct(cv.overall.accuracy, 1)} sub={`${cv.repeats}× ${cv.folds}-fold, n=${cv.n_records}`} /></Card>
            {heart && cv.any_disease ? <Card><Stat icon={<Target size={14} />} label="Disease vs none (CV)" value={pct(cv.any_disease.accuracy, 1)} sub={`AUC ${cv.any_disease.roc_auc.toFixed(2)} · sens ${pct(cv.any_disease.sensitivity)} · spec ${pct(cv.any_disease.specificity)}`} /></Card>
              : <Card><Stat icon={<Target size={14} />} label="ROC-AUC (CV)" value={cv.overall.roc_auc?.toFixed(3) ?? "—"} sub={`balanced acc ${pct(cv.overall.balanced_accuracy, 1)}`} /></Card>}
            <Card><Stat icon={<BrainCircuit size={14} />} label="When confident" value={<span style={{ color: "#34d399" }}>{gate ? pct(gate.accuracy, 1) : "—"}</span>} sub={gate ? `${pct(gate.coverage)} of cases · gate ≥ ${pct(cv.gate.threshold ?? 0)}` : ""} /></Card>
            <Card><Stat icon={<Database size={14} />} label="Production model" value={<span style={{ fontSize: "1.2rem" }}>{info.hybrid_strategy.replace(/_/g, " ")}</span>} sub={info.version} /></Card>
          </div>

          <Card>
            <div className="card-title"><h3>Accuracy vs coverage (confidence gate)</h3><Badge tone="cyan">{taskName(task)}{heart ? " · disease vs none" : ""}</Badge></div>
            <p style={{ fontSize: 14 }}>Raising the confidence threshold makes the model answer fewer cases but get them right more often. Cases below the gate are reported as <em>inconclusive</em> rather than guessed. Target accuracy {pct(cv.target_accuracy)}.</p>
            <div style={{ height: 300 }}><ResponsiveContainer>
              <LineChart data={gateRows} margin={{ left: -6, right: 16, top: 10 }}>
                <CartesianGrid vertical={false} /><XAxis dataKey="conf" tickLine={false} axisLine={false} /><YAxis domain={[0, 100]} unit="%" tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tipStyle} /><Legend />
                <ReferenceLine y={cv.target_accuracy * 100} stroke="#fbbf24" strokeDasharray="4 4" />
                <Line dataKey="Accuracy" stroke="#22d3ee" strokeWidth={3} dot={{ r: 3 }} /><Line dataKey="Coverage" stroke="#a78bfa" strokeWidth={3} dot={{ r: 3 }} />
              </LineChart></ResponsiveContainer></div>
          </Card>

          {heart && gradeRows.length > 0 && (
            <Card>
              <div className="card-title"><h3>Exact grade (0–4) accuracy vs coverage</h3></div>
              <p style={{ fontSize: 14 }}>The exact grade is much harder than disease vs none. Overall 5-grade accuracy is only <strong>{pct(cv.overall.accuracy, 1)}</strong>; high accuracy appears only on the small share of cases the model is very sure about.</p>
              <div style={{ height: 260 }}><ResponsiveContainer>
                <AreaChart data={gradeRows} margin={{ left: -6, right: 16 }}>
                  <CartesianGrid vertical={false} /><XAxis dataKey="conf" tickLine={false} axisLine={false} /><YAxis domain={[0, 100]} unit="%" tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={tipStyle} /><Legend />
                  <Area dataKey="Accuracy" stroke="#22d3ee" fill="#22d3ee33" strokeWidth={2} /><Area dataKey="Coverage" stroke="#a78bfa" fill="#a78bfa22" strokeWidth={2} />
                </AreaChart></ResponsiveContainer></div>
            </Card>
          )}

          <div className="grid cols-2" style={{ alignItems: "start" }}>
            <Card><div className="card-title"><h3>Global feature importance</h3><Badge tone="violet">mean |SHAP|</Badge></div>
              <div style={{ height: 320 }}><ResponsiveContainer><BarChart data={shap} layout="vertical" margin={{ left: 20, right: 16 }}>
                <CartesianGrid horizontal={false} /><XAxis type="number" tickLine={false} axisLine={false} /><YAxis type="category" dataKey="name" width={110} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tipStyle} /><Bar dataKey="v" fill="#7c83ff" radius={6} /></BarChart></ResponsiveContainer></div></Card>
            <Card><div className="card-title"><h3>Calibration</h3></div>
              <p style={{ fontSize: 14 }}>Does “80% confident” mean right about 80% of the time? Closer lines mean better-calibrated probabilities (held-out test set).</p>
              <div style={{ height: 270 }}><ResponsiveContainer><LineChart data={calib} margin={{ left: -8, right: 12 }}>
                <CartesianGrid vertical={false} /><XAxis dataKey="bin" tickLine={false} axisLine={false} /><YAxis unit="%" domain={[0, 100]} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tipStyle} /><Legend /><Line dataKey="Predicted" stroke="#22d3ee" strokeWidth={2.5} /><Line dataKey="Observed" stroke="#fb7185" strokeWidth={2.5} /></LineChart></ResponsiveContainer></div></Card>
          </div>

          <div className="grid cols-2" style={{ alignItems: "start" }}>
            <Card><h3>Confusion matrix (out-of-fold)</h3><Confusion m={cv.overall.confusion_matrix} labels={labels} /></Card>
            <Card><h3>Held-out test split</h3>
              {test && <table className="table"><tbody>
                <tr><td>Test records</td><td className="num">{test.n}</td></tr>
                <tr><td>Accuracy</td><td className="num">{pct(test.accuracy, 1)}</td></tr>
                <tr><td>Balanced accuracy</td><td className="num">{pct(test.balanced_accuracy, 1)}</td></tr>
                <tr><td>Macro F1</td><td className="num">{pct(test.f1_macro, 1)}</td></tr>
                {test.roc_auc != null && <tr><td>ROC-AUC</td><td className="num">{test.roc_auc.toFixed(3)}</td></tr>}
                {test.any_disease_accuracy != null && <tr><td>Disease vs none accuracy</td><td className="num">{pct(test.any_disease_accuracy, 1)}</td></tr>}
              </tbody></table>}
              <p className="faint" style={{ fontSize: 12.5, marginBottom: 0 }}>The test split is small, so cross-validated figures are more reliable.</p>
            </Card>
          </div>

          {info.leave_one_site_out_hybrid && (
            <Card><div className="card-title"><h3>Leave-one-hospital-out check</h3></div>
              <p style={{ fontSize: 14 }}>Train on three hospitals, test on the fourth. Performance drops on unseen sites, a realistic view of generalisation.</p>
              <div className="table-scroll"><table className="table"><thead><tr><th>Held-out site</th><th className="num">n</th><th className="num">Grade accuracy</th><th className="num">Disease vs none</th></tr></thead>
                <tbody>{Object.entries(info.leave_one_site_out_hybrid as Record<string, any>).map(([s, v]) => <tr key={s}><td >{s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()).replace("Va Long Beach", "VA Long Beach")}</td><td className="num">{v.n}</td><td className="num">{pct(v.accuracy, 1)}</td><td className="num">{v.any_disease_accuracy != null ? pct(v.any_disease_accuracy, 1) : "—"}</td></tr>)}</tbody></table></div></Card>
          )}

          <Alert tone="warn" title="Honest limitations">{task === "cad" ? "The dataset has 303 patients from one Iranian hospital (Shaheed Rajaei), referred for angiography, so many had symptoms already. Results may not carry over to a general, symptom-free population. Accuracy is cross-validated, not externally validated." : heart ? "Predicting the exact grade 1–4 from these 11 inputs is limited by the data: overall grade accuracy is near 52%, not 90%. Disease-vs-none is more reliable (about 81%), and confident predictions are much more accurate but cover fewer patients."
              : "The dataset is small (251 unique records after removing duplicates) and from one Bangladeshi clinic. Results may not carry over to other populations."} Hybrid hyper-parameters were chosen on training folds only.</Alert>
        </div>
      )}
    </>
  );
}
