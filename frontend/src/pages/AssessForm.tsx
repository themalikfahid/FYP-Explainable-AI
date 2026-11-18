import { useMemo, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, CheckCircle2, Send } from "lucide-react";
import { Alert, Button, Card, Field, PageHead, Segmented, SpecField, Stepper, ToggleCard, usePageTitle, Skeleton, useToast } from "../components/ui";
import { api, ApiError, type FieldSpec, type Lifestyle, type Task } from "../lib/api";
import { useFeatureMeta } from "../lib/useMeta";

const GROUPS: Record<Task, { title: string; hint: string; fields: string[]; toggles?: boolean }[]> = {
  heart: [
    { title: "About you", hint: "Basic details and the type of chest pain, if any.", fields: ["age", "sex", "cp"] },
    { title: "Vitals and blood", hint: "From a recent check-up. Cholesterol can be left blank if you don't have it.", fields: ["trestbps", "chol", "fbs"] },
    { title: "Heart tests", hint: "ECG and exercise-test results. Leave unknown items blank; the model will tell you it is less certain.", fields: ["restecg", "thalach", "exang", "oldpeak", "slope", "ca", "thal"] },
  ],
  cad: [
    { title: "About you", hint: "Basic details and your known risk factors.", fields: ["age", "sex", "bmi", "diabetes_hx", "hypertension", "current_smoker", "family_history", "dyslipidemia"] },
    { title: "Symptoms", hint: "Chest pain type and breathlessness. Pick the option that best describes your symptoms.", fields: ["typical_chest_pain", "atypical_chest_pain", "nonanginal_pain", "dyspnea", "function_class"] },
    { title: "ECG and vitals", hint: "Resting ECG findings and vital signs from a recent check-up.", fields: ["bp_systolic", "pulse", "q_wave", "st_elevation", "st_depression", "t_inversion", "lvh"] },
    { title: "Blood tests and echo", hint: "All optional. Adding them makes the estimate more reliable.", fields: ["fbs_mgdl", "ldl", "hdl", "triglycerides", "esr", "hemoglobin", "ef_tte"] },
  ],
  diabetes: [
    { title: "About you", hint: "Age and sex.", fields: ["age", "gender_male"] },
    { title: "Symptoms", hint: "Switch on everything you currently experience or have noticed recently.", toggles: true,
      fields: ["polyuria", "polydipsia", "sudden_weight_loss", "weakness", "polyphagia", "genital_thrush", "visual_blurring", "itching", "irritability", "delayed_healing", "partial_paresis", "muscle_stiffness", "alopecia", "obesity"] },
  ],
};

const EMPTY_LIFESTYLE = { height_cm: "", weight_kg: "", sleep_hours: "", activity_minutes_week: "", fruit_veg_servings_day: "", smoking: "never" as Lifestyle["smoking"], alcohol_units_week: "0", asian_bmi_cutoffs: false };

export default function AssessForm() {
  const { task } = useParams<{ task: string }>();
  const t = (task === "heart" || task === "diabetes" || task === "cad" ? task : null) as Task | null;
  const { meta, error } = useFeatureMeta();
  usePageTitle(t === "heart" ? "Heart disease assessment" : t === "cad" ? "Coronary artery screen" : "Diabetes screen");
  const nav = useNavigate(); const toast = useToast();
  const [step, setStep] = useState(0);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [life, setLife] = useState({ ...EMPTY_LIFESTYLE });
  const [useLife, setUseLife] = useState(false);
  const [busy, setBusy] = useState(false); const [formErr, setFormErr] = useState("");

  const groups = t ? GROUPS[t] : [];
  const steps = [...groups.map((g) => g.title), "Lifestyle", "Review"];
  const spec = meta && t ? meta[t].spec : {};

  const stepErrors = useMemo(() => (idx: number) => {
    const e: Record<string, string> = {};
    if (idx < groups.length) {
      for (const f of groups[idx].fields) {
        const s: FieldSpec = spec[f]; if (!s) continue;
        const v = vals[f] ?? "";
        if (groups[idx].toggles) continue;
        if (v === "") { if (s.required) e[f] = "Required"; continue; }
        const n = Number(v);
        if (!Number.isFinite(n)) e[f] = "Enter a number";
        else if (s.type === "number" && s.min !== undefined && (n < s.min || n > (s.max ?? Infinity))) e[f] = `Must be between ${s.min} and ${s.max}`;
      }
    }
    return e;
  }, [groups, spec, vals]);

  if (!t) return <Navigate to="/app/assess" replace />;
  if (error) return <Alert tone="error">{error}</Alert>;
  if (!meta) return <Card><Skeleton h={300} /></Card>;

  const set = (k: string) => (v: string) => { setVals((s) => ({ ...s, [k]: v })); setErrs((s) => { const n = { ...s }; delete n[k]; return n; }); };
  const next = () => { const e = stepErrors(step); setErrs(e); if (Object.keys(e).length === 0) setStep((s) => s + 1); };

  async function submit() {
    setBusy(true); setFormErr("");
    const features: Record<string, number | null> = {};
    for (const f of meta![t!].features) {
      const v = vals[f];
      features[f] = v === undefined || v === "" ? (t === "diabetes" && groups[1].fields.includes(f) ? 0 : null) : Number(v);
    }
    let lifestyle: Lifestyle | null = null;
    if (useLife) {
      const n = (s: string) => Number(s);
      lifestyle = { height_cm: n(life.height_cm), weight_kg: n(life.weight_kg), sleep_hours: n(life.sleep_hours), activity_minutes_week: n(life.activity_minutes_week),
        fruit_veg_servings_day: n(life.fruit_veg_servings_day), smoking: life.smoking, alcohol_units_week: n(life.alcohol_units_week), asian_bmi_cutoffs: life.asian_bmi_cutoffs };
    }
    try {
      const res = await api.predict(t!, features, lifestyle);
      toast("Assessment complete", "ok");
      nav(`/app/result/${res.id}`);
    } catch (x) {
      if (x instanceof ApiError) {
        setFormErr(x.fieldErrors.length ? x.fieldErrors.map((f) => `${f.field}: ${f.message}`).join(" · ") : x.message);
      } else setFormErr("Something went wrong.");
    } finally { setBusy(false); }
  }

  const lifeFilled = life.height_cm && life.weight_kg && life.sleep_hours && life.activity_minutes_week && life.fruit_veg_servings_day;
  const lastStep = steps.length - 1;
  const lifeStep = groups.length;
  const L = (k: keyof typeof life) => (e: React.ChangeEvent<HTMLInputElement>) => setLife({ ...life, [k]: e.target.value });

  return (
    <>
      <PageHead title={t === "heart" ? "Heart disease assessment" : t === "cad" ? "Coronary artery disease screen" : "Diabetes symptom screen"} subtitle={meta[t].title} />
      <Stepper steps={steps} current={step} />
      <Card large>
        <AnimatePresence mode="wait">
          <motion.div key={step} initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} transition={{ duration: .22 }}>
            {step < groups.length && (
              <div className="stack" style={{ gap: 22 }}>
                <div><h2 style={{ fontSize: "1.5rem", marginBottom: 4 }}>{groups[step].title}</h2><p style={{ margin: 0 }}>{groups[step].hint}</p></div>
                {groups[step].toggles ? (
                  <div className="form-grid">
                    {groups[step].fields.map((f) => <ToggleCard key={f} title={spec[f].label} help={spec[f].help} on={vals[f] === "1"} onClick={() => set(f)(vals[f] === "1" ? "0" : "1")} />)}
                  </div>
                ) : (
                  <div className="form-grid">{groups[step].fields.map((f) => <SpecField key={f} name={f} spec={spec[f]} value={vals[f] ?? ""} onChange={set(f)} error={errs[f]} />)}</div>
                )}
              </div>
            )}

            {step === lifeStep && (
              <div className="stack" style={{ gap: 22 }}>
                <div><h2 style={{ fontSize: "1.5rem", marginBottom: 4 }}>Lifestyle <span className="faint" style={{ fontSize: "1rem" }}>(optional)</span></h2>
                  <p style={{ margin: 0 }}>Used only for BMI, a lifestyle score and personalised advice. It does <strong>not</strong> change the AI risk score.</p></div>
                <ToggleCard title="Add lifestyle details" help="Adds BMI, lifestyle score and tailored recommendations" on={useLife} onClick={() => setUseLife((v) => !v)} />
                {useLife && (
                  <div className="form-grid">
                    <Field label="Height" unit="cm" htmlFor="h"><input id="h" className="input mono" type="number" value={life.height_cm} onChange={L("height_cm")} min={100} max={250} /></Field>
                    <Field label="Weight" unit="kg" htmlFor="w"><input id="w" className="input mono" type="number" value={life.weight_kg} onChange={L("weight_kg")} min={25} max={350} /></Field>
                    <Field label="Sleep per night" unit="hours" htmlFor="s"><input id="s" className="input mono" type="number" value={life.sleep_hours} onChange={L("sleep_hours")} min={0} max={24} step="0.5" /></Field>
                    <Field label="Moderate activity per week" unit="min" htmlFor="a"><input id="a" className="input mono" type="number" value={life.activity_minutes_week} onChange={L("activity_minutes_week")} min={0} /></Field>
                    <Field label="Fruit and vegetables per day" unit="servings" htmlFor="fv"><input id="fv" className="input mono" type="number" value={life.fruit_veg_servings_day} onChange={L("fruit_veg_servings_day")} min={0} max={20} /></Field>
                    <Field label="Alcohol per week" unit="units" htmlFor="al"><input id="al" className="input mono" type="number" value={life.alcohol_units_week} onChange={L("alcohol_units_week")} min={0} /></Field>
                    <Field label="Smoking"><Segmented label="Smoking" value={life.smoking} onChange={(v) => setLife({ ...life, smoking: v })} options={[{ value: "never", label: "Never" }, { value: "former", label: "Former" }, { value: "current", label: "Current" }]} /></Field>
                    <ToggleCard title="Use Asian BMI cut-offs" help="WHO cut-offs for Asian populations (23 / 27.5)" on={life.asian_bmi_cutoffs} onClick={() => setLife({ ...life, asian_bmi_cutoffs: !life.asian_bmi_cutoffs })} />
                  </div>
                )}
                {useLife && !lifeFilled && <Alert tone="warn">Fill every lifestyle field or switch lifestyle details off.</Alert>}
              </div>
            )}

            {step === lastStep && (
              <div className="stack" style={{ gap: 20 }}>
                <div><h2 style={{ fontSize: "1.5rem", marginBottom: 4 }}>Review and run</h2><p style={{ margin: 0 }}>Check your answers. The model runs on our server and the result is saved to your history.</p></div>
                <div className="grid cols-3">
                  {groups.flatMap((g) => g.fields).filter((f) => (vals[f] ?? "") !== "" || spec[f].required).map((f) => {
                    const s = spec[f]; const v = vals[f] ?? (t === "diabetes" && s.type === "select" ? "0" : "");
                    const shown = s.type === "select" ? s.options?.find((o) => String(o.value) === v)?.label ?? "—" : v ? `${v}${s.unit ? " " + s.unit : ""}` : "—";
                    return <div key={f} className="card" style={{ padding: 14 }}><div className="faint" style={{ fontSize: 12 }}>{s.label}</div><div className="mono" style={{ fontWeight: 600 }}>{shown}</div></div>;
                  })}
                </div>
                {useLife && <Alert tone="info">Lifestyle details will be used for BMI, lifestyle score and recommendations.</Alert>}
                {formErr && <Alert tone="error">{formErr}</Alert>}
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        <hr className="sep" />
        <div className="spread">
          <Button variant="ghost" icon={<ArrowLeft size={16} />} disabled={step === 0} onClick={() => setStep((s) => s - 1)}>Back</Button>
          {step < lastStep ? (
            <Button variant="primary" icon={<ArrowRight size={16} />} onClick={step === lifeStep && useLife && !lifeFilled ? undefined : next} disabled={step === lifeStep && useLife && !lifeFilled}>Continue</Button>
          ) : (
            <Button variant="primary" size="lg" loading={busy} icon={<Send size={16} />} onClick={submit}>Run assessment</Button>
          )}
        </div>
      </Card>
      <p className="faint" style={{ fontSize: 12.5, marginTop: 14 }}><CheckCircle2 size={13} style={{ verticalAlign: -2 }} /> {meta.disclaimer}</p>
    </>
  );
}
