import { motion } from "framer-motion";
import { ArrowRight, Droplets, HeartPulse, Microscope, Clock, FlaskConical, Stethoscope, Activity } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Card, PageHead, usePageTitle } from "../components/ui";

const OPTIONS = [
  { to: "/app/assess/heart", icon: HeartPulse, title: "Heart disease", tag: "Multiclass · ML hybrid", color: "#fb7185", time: "~3 min",
    text: "Eleven routine measurements (age, blood pressure, ECG, exercise test) give an overall disease probability and a grade 0–4 estimate.", needs: "Needs: blood pressure, ECG and exercise-test results" },
  { to: "/app/assess/cad", icon: Stethoscope, title: "Coronary artery screen", tag: "Binary · angiography-confirmed data", color: "#f59e0b", time: "~4 min",
    text: "Risk factors, symptoms, ECG and optional blood tests estimate whether significant coronary artery disease is likely. About 89% accurate in cross-validation, and over 95% on confident results.", needs: "Needs: ECG findings; blood tests are optional" },
  { to: "/app/assess/ecg", icon: Activity, title: "ECG heartbeat classifier", tag: "Multiclass · 5 beat types · MIT-BIH", color: "#34d399", time: "~1 min",
    text: "Upload or paste one heartbeat (187 samples) and the hybrid model names its type: normal, supraventricular, ventricular, fusion or paced/unknown. About 98% accurate on the official test set.", needs: "Needs: a single-beat ECG signal, or use a sample beat" },
  { to: "/app/assess/diabetes", icon: Droplets, title: "Diabetes symptom screen", tag: "Binary · ML hybrid", color: "#22d3ee", time: "~2 min",
    text: "Fourteen yes/no symptoms plus age and sex estimate whether your profile resembles diagnosed diabetes.", needs: "Needs: only things you can observe yourself" },
  { to: "/app/assess/t1d", icon: Microscope, title: "Type 1 pattern check", tag: "Rule-based · clinical criteria", color: "#a78bfa", time: "~2 min",
    text: "Scores how closely your symptoms, age, onset speed and lab values match Type 1 diabetes, and flags emergency warning signs.", needs: "Optional: glucose or HbA1c if you have them" },
];

export default function Assess() {
  usePageTitle("New assessment");
  return (
    <>
      <PageHead title="New assessment" subtitle="Pick the screening that fits your situation. Results are saved to your history." />
      <div className="grid cols-3">
        {OPTIONS.map((o, i) => (
          <motion.div key={o.to} initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * .08, duration: .5 }} whileHover={{ y: -6 }}>
            <Link to={o.to} style={{ textDecoration: "none", color: "inherit" }}>
              <Card glow style={{ height: "100%" }}>
                <div className="stack" style={{ height: "100%" }}>
                  <div className="spread"><div className="icon-chip" style={{ color: o.color }}><o.icon size={22} /></div><Badge tone="default"><Clock size={12} />{o.time}</Badge></div>
                  <div><h3 style={{ fontSize: "1.35rem", margin: "0 0 4px" }}>{o.title}</h3><span className="faint" style={{ fontSize: 12.5 }}>{o.tag}</span></div>
                  <p style={{ margin: 0 }}>{o.text}</p>
                  <div className="row faint" style={{ fontSize: 13, gap: 8, marginTop: "auto" }}><FlaskConical size={14} />{o.needs}</div>
                  <div className="row" style={{ color: o.color, fontWeight: 600 }}>Start <ArrowRight size={16} /></div>
                </div>
              </Card>
            </Link>
          </motion.div>
        ))}
      </div>
    </>
  );
}
