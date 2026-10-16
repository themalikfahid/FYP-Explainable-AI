import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError, type Task } from "../api";
import { Field, LIFESTYLE_SPEC, LifestyleFields, SMOKING_SPEC, lifestyleFrom, validateAll, type Values } from "../components/Fields";
import { useFeatureMeta } from "../useMeta";

export default function Assess() {
  const { task } = useParams<{ task: Task }>();
  const nav = useNavigate();
  const { meta, error: metaError } = useFeatureMeta();
  const [values, setValues] = useState<Values>({});
  const [ls, setLs] = useState<Values>({ asian_bmi_cutoffs: "0" });
  const [withLifestyle, setWithLifestyle] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const errRef = useRef<HTMLParagraphElement>(null);
  const clearError = (k: string) => setErrors((e) => { if (!(k in e)) return e; const n = { ...e }; delete n[k]; return n; });
  const setField = (k: string, v: string) => { setValues((old) => ({ ...old, [k]: v })); clearError(k); };

  useEffect(() => { setValues({}); setErrors({}); setError(""); }, [task]);

  if (task !== "diabetes" && task !== "heart") return <div className="page"><h1>Unknown assessment</h1></div>;
  if (metaError) return <div className="page"><p className="banner error" role="alert">{metaError}</p></div>;
  if (!meta) return <div className="page"><p className="loading" role="status">Loading form…</p></div>;
  const t = meta[task];

  async function submit(e: FormEvent) {
    e.preventDefault();
    const errs = validateAll(t.spec, values);
    if (withLifestyle) Object.assign(errs, validateAll({ ...LIFESTYLE_SPEC, smoking: SMOKING_SPEC }, ls));
    setErrors(errs);
    if (Object.keys(errs).length) {
      setError(`Please fix ${Object.keys(errs).length} highlighted field${Object.keys(errs).length > 1 ? "s" : ""}.`);
      setTimeout(() => errRef.current?.focus(), 0);
      return;
    }
    const features: Record<string, number | null> = {};
    for (const f of t.features) features[f] = values[f] === undefined || values[f] === "" ? null : Number(values[f]);
    setBusy(true); setError("");
    try {
      const p = await api.predict(task!, features, withLifestyle ? lifestyleFrom(ls) : null);
      nav(`/history/${p.id}`, { state: { fresh: true } });
    } catch (err) {
      if (err instanceof ApiError && err.fieldErrors.length) {
        setErrors(Object.fromEntries(err.fieldErrors.map((f) => [f.field.split(".").pop()!, f.message])));
      }
      setError(err instanceof ApiError ? err.message : "The assessment could not be completed.");
      setBusy(false);
      setTimeout(() => errRef.current?.focus(), 0);
    }
  }

  function fillSymptomFree() {
    // convenience for the diabetes screen: set every symptom to "No" (user then changes what applies)
    const v: Values = { ...values };
    const cleared: string[] = [];
    for (const f of t.features) if (f !== "age" && f !== "gender_male") { v[f] = "0"; cleared.push(f); }
    setValues(v);
    cleared.forEach(clearError);
  }

  const symptomFields = t.features.filter((f) => !["age", "gender_male", "sex"].includes(f));
  return (
    <div className="page narrow">
      <h1>{task === "heart" ? "Heart disease classification" : "Diabetes symptom screen"}</h1>
      <p className="lede">{task === "heart"
        ? "Enter results from a clinical examination and exercise stress test. Optional fields can be left as \"Not known\"; the model then fills in a typical value and tells you the result is less certain."
        : "Answer for symptoms you have had recently. This screen does not tell type 1 from type 2 diabetes and cannot replace a blood test."}</p>
      <form onSubmit={submit} noValidate>
        {error && <p className="banner error" role="alert" tabIndex={-1} ref={errRef}>{error}</p>}
        <fieldset>
          <legend>About you</legend>
          <div className="grid-fields">
            {t.features.filter((f) => ["age", "gender_male", "sex"].includes(f)).map((f) => (
              <Field key={f} name={f} spec={t.spec[f]} value={values[f] ?? ""} error={errors[f]}
                onChange={(v) => setField(f, v)} />
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>{task === "heart" ? "Examination and test results" : "Symptoms"}</legend>
          {task === "diabetes" && <button type="button" className="link-btn" onClick={fillSymptomFree}>Set all symptoms to "No"</button>}
          <div className={task === "diabetes" ? "grid-fields symptoms" : "grid-fields"}>
            {symptomFields.map((f) => (
              <Field key={f} name={f} spec={t.spec[f]} value={values[f] ?? ""} error={errors[f]}
                onChange={(v) => setField(f, v)} />
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>Lifestyle</legend>
          <label className="check-line">
            <input type="checkbox" checked={withLifestyle} onChange={(e) => setWithLifestyle(e.target.checked)} />
            Include lifestyle details for BMI, a lifestyle score and personalised suggestions (not used by the prediction model)
          </label>
          {withLifestyle && <LifestyleFields values={ls} errors={errors} set={(k, v) => { setLs((old) => ({ ...old, [k]: v })); clearError(k); }} />}
        </fieldset>
        <div className="form-foot">
          <button className="btn" disabled={busy}>{busy ? "Running model and explanation…" : "Get my result"}</button>
          <p className="fine">{meta.disclaimer}</p>
        </div>
      </form>
    </div>
  );
}
