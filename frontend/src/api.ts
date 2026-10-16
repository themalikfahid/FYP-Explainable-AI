// Thin typed client for the FastAPI backend. All requests go to same-origin /api
// (Vite proxies it in development; FastAPI serves the built app in production).

export type Option = { value: number; label: string };
export type FieldSpec = {
  label: string; type: "number" | "select"; required: boolean;
  unit?: string; min?: number; max?: number; step?: number; help?: string; options?: Option[];
};
export type TaskMeta = {
  title: string; features: string[]; spec: Record<string, FieldSpec>; class_labels: Record<string, string>;
};
export type FeatureMeta = { diabetes: TaskMeta; heart: TaskMeta; disclaimer: string };
export type Task = "diabetes" | "heart";

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
export type PredictionResult = {
  task: Task; predicted_class: number; predicted_label: string; probabilities: Record<string, number>;
  risk_score: number; risk_score_definition: string; risk_level: "low" | "moderate" | "high";
  risk_thresholds: { low_below: number; high_at_or_above: number };
  components: { random_forest: Record<string, number>; ann: Record<string, number>; max_disagreement: number };
  probability_note: string; warnings: string[];
  model: { version: string; production_model: string; test_metrics: Record<string, number> };
  explanation?: Explanation;
  recommendations: { items: Recommendation[]; lifestyle_score: LifestyleScore | null; bmi: BMIResult | null;
    top_risk_factors: string[]; disclaimer: string };
};
export type Prediction = {
  id: number | null; disease: Task; created_at: string; inputs: Record<string, number | null>;
  lifestyle: Lifestyle | null; predicted_class: number; risk_score: number; risk_level: "low" | "moderate" | "high";
  result: PredictionResult; model_version: string; alert_status: string | null;
};
export type PredictionSummary = Pick<Prediction, "id" | "disease" | "created_at" | "predicted_class" | "risk_score" | "risk_level">;
export type User = { id: number; email: string; full_name: string; email_alerts_enabled: boolean; created_at: string };

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
