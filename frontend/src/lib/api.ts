// Typed client for the FastAPI backend. Requests go to same-origin /api
// (Vite proxies it in development; FastAPI serves the built app in production).

export type Option = { value: number; label: string };
export type FieldSpec = {
  label: string; type: "number" | "select"; required: boolean;
  unit?: string; min?: number; max?: number; step?: number; help?: string; options?: Option[];
};
export type TaskMeta = {
  title: string; features: string[]; spec: Record<string, FieldSpec>; class_labels: Record<string, string>;
};
export type FeatureMeta = { diabetes: TaskMeta; heart: TaskMeta; cad: TaskMeta; disclaimer: string };
export type Task = "diabetes" | "heart" | "cad";
export type RiskLevel = "low" | "moderate" | "high";

export type Contribution = { feature: string; value: number | null; shap: number };
export type Explanation = {
  method: string; explained_class: number; base_value: number; predicted_probability: number;
  contributions: Contribution[]; summary: string[];
  per_class: Record<string, { base_value: number; shap: Record<string, number> }>;
  any_disease?: { base_value: number; shap: Record<string, number> };
};
export type Recommendation = { category: string; priority: "high" | "medium" | "low"; text: string; rule: string; source: string };
export type LifestyleScore = {
  score: number; band: string; note: string;
  components: Record<string, { points: number; max: number; input: number | string }>;
};
export type BMIResult = { bmi: number; category: string; cutoffs: string; healthy_weight_range_kg: [number, number]; note: string };
export type Lifestyle = {
  height_cm: number; weight_kg: number; sleep_hours: number; activity_minutes_week: number;
  fruit_veg_servings_day: number; smoking: "never" | "former" | "current"; alcohol_units_week: number;
  asian_bmi_cutoffs: boolean;
};
export type Confidence = {
  tier: "confident" | "inconclusive" | "unrated"; value: number; threshold?: number; decision?: string;
  expected_accuracy_if_confident?: number | null; coverage_at_threshold?: number | null;
  overall_cv_accuracy?: number; note: string;
};
export type PredictionResult = {
  task: Task; predicted_class: number; predicted_label: string; probabilities: Record<string, number>;
  risk_score: number; risk_score_definition: string; risk_level: RiskLevel;
  risk_thresholds: { low_below: number; high_at_or_above: number };
  components: { random_forest: Record<string, number>; ann: Record<string, number>; max_disagreement: number };
  probability_note: string; warnings: string[]; confidence: Confidence;
  model: { version: string; production_model: string; test_metrics: Record<string, number>;
    cross_validated?: { cv_accuracy: number; cv_balanced_accuracy: number; cv_roc_auc?: number;
      gate_threshold?: number; confident_accuracy?: number; confident_coverage?: number } | null };
  explanation?: Explanation;
  recommendations: { items: Recommendation[]; lifestyle_score: LifestyleScore | null; bmi: BMIResult | null;
    top_risk_factors: string[]; disclaimer: string };
};
export type Prediction = {
  id: number | null; disease: Task; created_at: string; inputs: Record<string, number | null>;
  lifestyle: Lifestyle | null; predicted_class: number; risk_score: number; risk_level: RiskLevel;
  result: PredictionResult; model_version: string; alert_status: string | null;
};
export type PredictionSummary = Pick<Prediction, "id" | "disease" | "created_at" | "predicted_class" | "risk_score" | "risk_level">;
export type User = { id: number; email: string; full_name: string; email_alerts_enabled: boolean; created_at: string };

export type EcgResult = {
  predicted_class: number; predicted_label: string; probabilities: Record<string, number>; abnormal_probability: number;
  confidence: { tier: "confident" | "inconclusive" | "unrated"; value: number; threshold: number | null; expected_accuracy_if_confident: number | null; coverage_at_threshold: number | null };
  saliency: { start: number; end: number; importance: number }[]; warnings: string[];
  model_accuracy: { test_accuracy: number; balanced_accuracy: number; n_test: number }; disclaimer: string;
};
export type EcgInfo = {
  dataset: string; classes: Record<string, string>; threshold: number | null; samples: Record<string, { label: string; beat: number[] }>;
  report: { n_test: number; test: { hybrid: { accuracy: number; balanced_accuracy: number; f1_macro: number; per_class: Record<string, { label: string; precision: number; recall: number; f1: number; support: number }> } };
    abnormal_vs_normal: { accuracy: number; sensitivity: number; specificity: number }; gate: { test_table: { min_confidence: number; coverage: number; accuracy: number }[] } };
};
export type T1DInput = {
  age: number; polyuria: 0 | 1; polydipsia: 0 | 1; weight_loss: 0 | 1; fatigue: 0 | 1; blurred_vision: 0 | 1;
  bedwetting: 0 | 1; recurrent_infections: 0 | 1; abdominal_pain_vomiting: 0 | 1; fruity_breath_or_fast_breathing: 0 | 1;
  symptom_weeks: number | null; family_history_t1d: 0 | 1; other_autoimmune: 0 | 1;
  bmi_category: "underweight" | "normal" | "overweight" | "obese" | "unknown";
  fasting_glucose: number | null; random_glucose: number | null; hba1c: number | null;
};
export type T1DResult = {
  kind: "t1d_indicator"; method: string; score: number; band: "low" | "possible" | "strong"; summary: string;
  contributions: { label: string; points: number }[]; lab_flags: { label: string; level: "high" | "moderate" }[];
  meets_diagnostic_range: boolean; emergency_warning: boolean; emergency_signs: string[]; next_steps: string[];
  cohort_comparison: { symptom: string; share_of_cohort: number }[]; cohort_note: string | null; limitations: string[];
};
export type WhatIfResult = {
  task: Task; delta: number; note: string;
  baseline: { risk_score: number; risk_level: RiskLevel; predicted_label: string; confidence: Confidence };
  scenario: { risk_score: number; risk_level: RiskLevel; predicted_label: string; confidence: Confidence };
  per_change: { feature: string; label: string; from: number | null; to: number | null; risk_score: number; delta: number }[];
};
export type SeriesPoint = { id: number; at: string; risk_score: number; risk_level: RiskLevel };
export type Analytics = {
  total_assessments: number; risk_distribution: Record<RiskLevel, number>;
  latest: Record<string, SeriesPoint & { trend: "up" | "down" | "steady" | null; assessments: number; average_score: number; confidence_tier: string | null }>;
  series: Record<string, SeriesPoint[]>; recent: (SeriesPoint & { disease: Task })[];
  top_drivers: Record<string, { feature: string; label: string; shap: number }[]>;
};
export type GateRow = { min_confidence: number; coverage: number; accuracy: number; n: number };
export type OofReport = {
  task: Task; n_records: number; repeats: number; folds: number; target_accuracy: number;
  overall: { accuracy: number; balanced_accuracy: number; f1_macro: number; roc_auc?: number; confusion_matrix: number[][] };
  any_disease?: { accuracy: number; balanced_accuracy: number; roc_auc: number; sensitivity: number; specificity: number; confusion_matrix: number[][] };
  gate: { decision: string; table: GateRow[]; threshold: number | null };
  gate_grade?: { decision: string; table: GateRow[]; threshold: number | null };
};

const TOKEN_KEY = "cs_token";
let memoryToken: string | null = null;

export function getToken(): string | null {
  if (memoryToken) return memoryToken;
  try { memoryToken = sessionStorage.getItem(TOKEN_KEY); } catch { /* storage blocked */ }
  return memoryToken;
}
export function setToken(t: string | null) {
  memoryToken = t;
  try { t ? sessionStorage.setItem(TOKEN_KEY, t) : sessionStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
}

export class ApiError extends Error {
  status: number; fieldErrors: { field: string; message: string }[];
  constructor(status: number, message: string, fieldErrors: { field: string; message: string }[] = []) {
    super(message); this.status = status; this.fieldErrors = fieldErrors;
  }
}

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

async function request<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = getToken();
  if (auth && token) headers.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check that the backend is running and try again.");
  }
  if (res.status === 204) return undefined as T;
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : null;
  if (!res.ok) {
    if (res.status === 401 && auth && token) { setToken(null); onUnauthorized(); }
    const detail = typeof data?.detail === "string" ? data.detail : `Request failed (${res.status})`;
    throw new ApiError(res.status, detail, data?.errors ?? []);
  }
  return data as T;
}

export const api = {
  features: () => request<FeatureMeta>("/meta/features", {}, false),
  modelInfo: (task: Task) => request<any>(`/meta/models/${task}`, {}, false),
  health: () => request<any>("/health", {}, false),
  register: (body: { email: string; full_name: string; password: string }) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify(body) }, false),
  login: (email: string, password: string) =>
    request<{ access_token: string; expires_at: string }>("/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) }, false),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<User>("/auth/me"),
  updateMe: (body: Partial<Pick<User, "full_name" | "email_alerts_enabled">>) =>
    request<User>("/auth/me", { method: "PATCH", body: JSON.stringify(body) }),
  changePassword: (current_password: string, new_password: string) =>
    request<void>("/auth/change-password", { method: "POST", body: JSON.stringify({ current_password, new_password }) }),
  deleteAccount: (password: string) =>
    request<void>("/auth/me", { method: "DELETE", body: JSON.stringify({ password }) }),
  predict: (task: Task, features: Record<string, number | null>, lifestyle: Lifestyle | null) =>
    request<Prediction>(`/predict/${task}`, { method: "POST", body: JSON.stringify({ features, lifestyle, save: true }) }),
  history: (disease?: Task, limit = 50, offset = 0) =>
    request<{ total: number; items: PredictionSummary[] }>(
      `/predictions?limit=${limit}&offset=${offset}${disease ? `&disease=${disease}` : ""}`),
  prediction: (id: number) => request<Prediction>(`/predictions/${id}`),
  deletePrediction: (id: number) => request<void>(`/predictions/${id}`, { method: "DELETE" }),
  bmi: (height_cm: number, weight_kg: number, asian_bmi_cutoffs: boolean) =>
    request<BMIResult>("/tools/bmi", { method: "POST", body: JSON.stringify({ height_cm, weight_kg, asian_bmi_cutoffs }) }, false),
  lifestyleScore: (l: Lifestyle) =>
    request<{ lifestyle_score: LifestyleScore; bmi: BMIResult }>("/tools/lifestyle-score",
      { method: "POST", body: JSON.stringify(l) }, false),
  ecg: (beat: number[]) => request<EcgResult>("/assess/ecg", { method: "POST", body: JSON.stringify({ beat }) }),
  ecgInfo: () => request<EcgInfo>("/meta/ecg"),
  t1d: (body: T1DInput) => request<T1DResult>("/assess/t1d", { method: "POST", body: JSON.stringify(body) }),
  whatIf: (task: Task, features: Record<string, number | null>, changes: Record<string, number | null>) =>
    request<WhatIfResult>(`/whatif/${task}`, { method: "POST", body: JSON.stringify({ features, changes }) }),
  analytics: () => request<Analytics>("/analytics/summary"),
  async downloadReport(id: number) {
    const token = getToken();
    let res: Response;
    try {
      res = await fetch(`/api/predictions/${id}/report.pdf`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    } catch { throw new ApiError(0, "Can't reach the server to create the report."); }
    if (!res.ok) throw new ApiError(res.status, res.status === 404 ? "Report not found." : "The report could not be created.");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `health-report-${id}.pdf`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
