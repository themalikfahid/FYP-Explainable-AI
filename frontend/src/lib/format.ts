import type { RiskLevel } from "./api";

export const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`;
export const riskLabel: Record<RiskLevel, string> = { low: "Low risk", moderate: "Moderate risk", high: "High risk" };
export const riskColor: Record<RiskLevel, string> = { low: "#34d399", moderate: "#fbbf24", high: "#fb7185" };
export const taskName = (t: string) => (t === "heart" ? "Heart disease" : t === "cad" ? "Coronary artery screen" : t === "diabetes" ? "Diabetes screen" : "Type 1 pattern");

export function dateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}
export function clamp(v: number, lo: number, hi: number) { return Math.min(hi, Math.max(lo, v)); }
export function riskFromScore(score: number, th = { low_below: 0.3, high_at_or_above: 0.7 }): RiskLevel {
  return score >= th.high_at_or_above ? "high" : score < th.low_below ? "low" : "moderate";
}
