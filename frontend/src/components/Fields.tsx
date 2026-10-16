import type { FieldSpec, Lifestyle } from "../api";

export type Values = Record<string, string>;

/** Validate one field against the backend-provided spec. Returns an error message or "". */
export function validateField(spec: FieldSpec, raw: string): string {
  if (raw === "" || raw === undefined) return spec.required ? "This field is required." : "";
  if (spec.type === "number") {
    const n = Number(raw);
    if (!Number.isFinite(n)) return "Enter a number.";
    if (spec.min !== undefined && n < spec.min) return `Must be at least ${spec.min}${spec.unit ? ` ${spec.unit}` : ""}.`;
    if (spec.max !== undefined && n > spec.max) return `Must be at most ${spec.max}${spec.unit ? ` ${spec.unit}` : ""}.`;
  }
  return "";
}

export function Field({ name, spec, value, error, onChange }: {
  name: string; spec: FieldSpec; value: string; error?: string; onChange: (v: string) => void;
}) {
  const id = `f-${name}`;
  const describedBy = [spec.help ? `${id}-help` : "", error ? `${id}-err` : ""].filter(Boolean).join(" ") || undefined;
  return (
    <div className={error ? "field has-error" : "field"}>
      <label htmlFor={id}>
        {spec.label}{spec.unit ? <span className="unit"> ({spec.unit})</span> : null}
        {!spec.required && <span className="optional"> optional</span>}
      </label>
      {spec.help && <p className="help" id={`${id}-help`}>{spec.help}</p>}
      {spec.type === "select" && spec.options && spec.options.length === 2 && spec.options.every((o) => o.label === "Yes" || o.label === "No") ? (
        <div className="seg" role="radiogroup" aria-labelledby={id} aria-describedby={describedBy}>
          <span id={id} className="sr-only">{spec.label}</span>
          {spec.options.map((o) => (
            <label key={o.value} className={value === String(o.value) ? "seg-opt on" : "seg-opt"}>
              <input type="radio" name={name} value={o.value} checked={value === String(o.value)}
                onChange={() => onChange(String(o.value))} />
              {o.label}
            </label>
          ))}
        </div>
      ) : spec.type === "select" ? (
        <select id={id} value={value} onChange={(e) => onChange(e.target.value)} aria-invalid={!!error}
          aria-describedby={describedBy}>
          <option value="">{spec.required ? "Choose…" : "Not known"}</option>
          {spec.options!.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      ) : (
        <input id={id} type="number" inputMode="decimal" value={value} min={spec.min} max={spec.max}
          step={spec.step ?? "any"} onChange={(e) => onChange(e.target.value)} aria-invalid={!!error}
          aria-describedby={describedBy} />
      )}
      {error && <p className="err" id={`${id}-err`} role="alert">{error}</p>}
    </div>
  );
}

export const LIFESTYLE_SPEC: Record<keyof Omit<Lifestyle, "asian_bmi_cutoffs" | "smoking">, FieldSpec> = {
  height_cm: { label: "Height", unit: "cm", type: "number", min: 100, max: 250, required: true },
  weight_kg: { label: "Weight", unit: "kg", type: "number", min: 25, max: 350, required: true },
  sleep_hours: { label: "Sleep per night", unit: "hours", type: "number", min: 0, max: 24, step: 0.5, required: true },
  activity_minutes_week: { label: "Moderate activity per week", unit: "minutes", type: "number", min: 0, max: 3000, required: true,
    help: "Brisk walking, cycling, housework that makes you breathe faster. Count vigorous minutes twice." },
  fruit_veg_servings_day: { label: "Fruit and vegetable servings per day", type: "number", min: 0, max: 20, step: 0.5, required: true,
    help: "One serving is about 80 g: a medium fruit or a handful of vegetables." },
  alcohol_units_week: { label: "Alcohol per week", unit: "units", type: "number", min: 0, max: 200, required: true,
    help: "Enter 0 if you don't drink." },
};

export const SMOKING_SPEC: FieldSpec = {
  label: "Smoking", type: "select", required: true,
  options: [{ value: 0, label: "Never smoked" }, { value: 1, label: "Former smoker" }, { value: 2, label: "Current smoker" }],
};
export const SMOKING_VALUES = ["never", "former", "current"] as const;

export function lifestyleFrom(values: Values): Lifestyle {
  return {
    height_cm: Number(values.height_cm), weight_kg: Number(values.weight_kg), sleep_hours: Number(values.sleep_hours),
    activity_minutes_week: Number(values.activity_minutes_week), fruit_veg_servings_day: Number(values.fruit_veg_servings_day),
    alcohol_units_week: Number(values.alcohol_units_week), smoking: SMOKING_VALUES[Number(values.smoking)],
    asian_bmi_cutoffs: values.asian_bmi_cutoffs === "1",
  };
}

export function validateAll(specs: Record<string, FieldSpec>, values: Values): Record<string, string> {
  const errs: Record<string, string> = {};
  for (const [k, s] of Object.entries(specs)) {
    const e = validateField(s, values[k] ?? "");
    if (e) errs[k] = e;
  }
  return errs;
}

export function LifestyleFields({ values, errors, set }: {
  values: Values; errors: Record<string, string>; set: (k: string, v: string) => void;
}) {
  return (
    <div className="grid-fields">
      {Object.entries(LIFESTYLE_SPEC).map(([k, s]) => (
        <Field key={k} name={k} spec={s} value={values[k] ?? ""} error={errors[k]} onChange={(v) => set(k, v)} />
      ))}
      <Field name="smoking" spec={SMOKING_SPEC} value={values.smoking ?? ""} error={errors.smoking}
        onChange={(v) => set("smoking", v)} />
      <div className="field check">
        <label>
          <input type="checkbox" checked={values.asian_bmi_cutoffs === "1"}
            onChange={(e) => set("asian_bmi_cutoffs", e.target.checked ? "1" : "0")} />
          Use WHO cut-offs for Asian populations (BMI 23 / 27.5)
        </label>
      </div>
    </div>
  );
}
