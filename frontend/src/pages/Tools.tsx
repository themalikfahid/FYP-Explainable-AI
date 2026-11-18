import { useState } from "react";
import { Calculator, Scale } from "lucide-react";
import { Alert, Button, Card, Field, PageHead, Segmented, ToggleCard, usePageTitle, Gauge } from "../components/ui";
import { api, ApiError, type BMIResult, type Lifestyle, type LifestyleScore } from "../lib/api";
import { riskFromScore } from "../lib/format";

export default function Tools() {
  usePageTitle("Health tools");
  const [h, setH] = useState(""); const [w, setW] = useState(""); const [asian, setAsian] = useState(false);
  const [bmi, setBmi] = useState<BMIResult | null>(null); const [e1, setE1] = useState("");
  const [l, setL] = useState({ sleep: "", act: "", fv: "", alc: "0", smoke: "never" as Lifestyle["smoking"] });
  const [ls, setLs] = useState<LifestyleScore | null>(null); const [e2, setE2] = useState("");

  const msg = (x: unknown) => x instanceof ApiError ? (x.fieldErrors.map((f) => `${f.field}: ${f.message}`).join(" · ") || x.message) : "Request failed.";
  async function calcBmi() { setE1(""); try { setBmi(await api.bmi(Number(h), Number(w), asian)); } catch (x) { setE1(msg(x)); setBmi(null); } }
  async function calcLs() {
    setE2("");
    try {
      const r = await api.lifestyleScore({ height_cm: Number(h) || 170, weight_kg: Number(w) || 70, sleep_hours: Number(l.sleep), activity_minutes_week: Number(l.act),
        fruit_veg_servings_day: Number(l.fv), smoking: l.smoke, alcohol_units_week: Number(l.alc), asian_bmi_cutoffs: asian });
      setLs(r.lifestyle_score);
    } catch (x) { setE2(msg(x)); setLs(null); }
  }
  // lifestyle score: higher is better, so invert for the risk-coloured gauge
  const lvl = ls ? riskFromScore(1 - ls.score / 100) : "low";

  return (
    <>
      <PageHead title="Health tools" subtitle="Quick calculators. Nothing is saved." />
      <div className="grid cols-2" style={{ alignItems: "start" }}>
        <Card large>
          <h3><Scale size={18} color="#22d3ee" /> BMI calculator</h3>
          <div className="stack">
            <Field label="Height" unit="cm" htmlFor="tb-h"><input id="tb-h" className="input mono" type="number" value={h} onChange={(e) => setH(e.target.value)} /></Field>
            <Field label="Weight" unit="kg" htmlFor="tb-w"><input id="tb-w" className="input mono" type="number" value={w} onChange={(e) => setW(e.target.value)} /></Field>
            <ToggleCard title="Asian BMI cut-offs" help="23 / 27.5 instead of 25 / 30" on={asian} onClick={() => setAsian(!asian)} />
            {e1 && <Alert tone="error">{e1}</Alert>}
            <Button variant="primary" icon={<Calculator size={16} />} onClick={calcBmi}>Calculate BMI</Button>
            {bmi && <Alert tone="info" title={`BMI ${bmi.bmi.toFixed(1)} · ${bmi.category}`}>Healthy weight for your height: {bmi.healthy_weight_range_kg[0]}–{bmi.healthy_weight_range_kg[1]} kg. {bmi.note}</Alert>}
          </div>
        </Card>
        <Card large>
          <h3>Lifestyle score</h3>
          <div className="stack">
            <Field label="Sleep per night" unit="hours" htmlFor="tl-s"><input id="tl-s" className="input mono" type="number" value={l.sleep} onChange={(e) => setL({ ...l, sleep: e.target.value })} /></Field>
            <Field label="Moderate activity per week" unit="min" htmlFor="tl-a"><input id="tl-a" className="input mono" type="number" value={l.act} onChange={(e) => setL({ ...l, act: e.target.value })} /></Field>
            <Field label="Fruit and vegetables per day" unit="servings" htmlFor="tl-f"><input id="tl-f" className="input mono" type="number" value={l.fv} onChange={(e) => setL({ ...l, fv: e.target.value })} /></Field>
            <Field label="Alcohol per week" unit="units" htmlFor="tl-al"><input id="tl-al" className="input mono" type="number" value={l.alc} onChange={(e) => setL({ ...l, alc: e.target.value })} /></Field>
            <Field label="Smoking"><Segmented label="Smoking" value={l.smoke} onChange={(v) => setL({ ...l, smoke: v })} options={[{ value: "never", label: "Never" }, { value: "former", label: "Former" }, { value: "current", label: "Current" }]} /></Field>
            {e2 && <Alert tone="error">{e2}</Alert>}
            <Button variant="primary" onClick={calcLs}>Calculate score</Button>
            {ls && <div style={{ display: "grid", placeItems: "center" }}><Gauge value={ls.score / 100} level={lvl} label={`${ls.band} · lifestyle`} /><p style={{ textAlign: "center", fontSize: 14 }}>{ls.note}</p></div>}
          </div>
        </Card>
      </div>
    </>
  );
}
