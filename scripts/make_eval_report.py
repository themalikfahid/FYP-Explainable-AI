"""Generate docs/MODEL_EVALUATION.md from the saved training metadata so the
document always matches the shipped models.

    python scripts/make_eval_report.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "artifacts" / "models"
NAMES = {"random_forest": "Random Forest", "ann": "ANN (MLP)", "hybrid": "Hybrid (RF + ANN)"}


def f(v, d=3):
    return "n/a" if v is None else f"{v:.{d}f}"


def ci(pair):
    return f"{pair[0]:.3f} to {pair[1]:.3f}"


def task_section(task: str) -> str:
    m = json.loads((MODELS / task / "metadata.json").read_text())
    g = json.loads((MODELS / task / "global_shap.json").read_text())
    tm = m["test_metrics"]
    binary = len(m["classes"]) == 2
    out = [f"## {m['title']}\n",
           f"* Rows after removing exact duplicates: **{m['split']['rows_after_dedup']}** "
           f"(train {m['split']['train']}, test {m['split']['test']}, stratified, seed {m['split']['seed']}).",
           f"* Class distribution, train: `{m['class_distribution_train']}`; test: `{m['class_distribution_test']}`.",
           f"* Trained at {m['trained_at_utc']} with scikit-learn {m['versions']['sklearn']} "
           f"in {m['train_seconds']} s.",
           f"* Tuned hyperparameters: RF `{m['best_params']['random_forest']}`; ANN `{m['best_params']['ann']}`.",
           f"* Hybrid strategy selected by training-set CV: **{m['hybrid_strategy']}** with "
           f"`{m['best_params']['hybrid']}`. Candidates (5-fold CV macro-F1 on train): " +
           ", ".join(f"{k} {v['cv_f1_macro']:.3f}" for k, v in m["hybrid_candidates"].items()) + ".\n",
           "### Repeated cross-validation on the training set (5 folds x 3 repeats)\n",
           "| Model | Accuracy | Macro F1 | Weighted F1 | ROC-AUC |", "|---|---|---|---|---|"]
    for k, v in m["cv_train_repeated"].items():
        out.append(f"| {NAMES[k]} | {f(v['accuracy']['mean'])} ± {f(v['accuracy']['std'])} | "
                   f"{f(v['f1_macro']['mean'])} ± {f(v['f1_macro']['std'])} | "
                   f"{f(v['f1_weighted']['mean'])} ± {f(v['f1_weighted']['std'])} | "
                   f"{f(v['roc_auc']['mean'])} ± {f(v['roc_auc']['std'])} |")
    out += ["", f"### Held-out test set (n = {tm['hybrid']['n']}, evaluated once)\n"]
    if binary:
        out += ["| Model | Accuracy | Balanced acc. | Macro precision | Macro recall | Macro F1 | Weighted F1 | "
                "Sensitivity | Specificity | ROC-AUC | Avg. precision | Brier | ECE |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, v in tm.items():
            out.append(f"| {NAMES[k]} | {f(v['accuracy'])} | {f(v['balanced_accuracy'])} | {f(v['precision_macro'])} | "
                       f"{f(v['recall_macro'])} | {f(v['f1_macro'])} | {f(v['f1_weighted'])} | {f(v['sensitivity'])} | "
                       f"{f(v['specificity'])} | {f(v['roc_auc'])} | {f(v['average_precision'])} | {f(v['brier'])} | "
                       f"{f(v['ece_top_label'])} |")
    else:
        out += ["| Model | Accuracy | Balanced acc. | Macro precision | Macro recall | Macro F1 | Weighted F1 | "
                "ROC-AUC (OvR macro) | Avg. precision (macro) | Brier | ECE |",
                "|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, v in tm.items():
            out.append(f"| {NAMES[k]} | {f(v['accuracy'])} | {f(v['balanced_accuracy'])} | {f(v['precision_macro'])} | "
                       f"{f(v['recall_macro'])} | {f(v['f1_macro'])} | {f(v['f1_weighted'])} | "
                       f"{f(v['roc_auc_ovr_macro'])} | {f(v['average_precision_macro'])} | {f(v['brier'])} | "
                       f"{f(v['ece_top_label'])} |")
        out += ["", "**Any disease (grades 1-4) vs none (grade 0)**, derived from the same probabilities "
                "(P(any) = 1 - P(grade 0), threshold 0.5):\n",
                "| Model | ROC-AUC | Accuracy | Sensitivity | Specificity |", "|---|---|---|---|---|"]
        for k, v in tm.items():
            out.append(f"| {NAMES[k]} | {f(v['any_disease_roc_auc'])} | {f(v['any_disease_accuracy'])} | "
                       f"{f(v['any_disease_sensitivity'])} | {f(v['any_disease_specificity'])} |")
    out += ["", "Bootstrap 95% confidence intervals on the test set (1000 resamples):\n",
            "| Model | Accuracy | Macro F1 | ROC-AUC |", "|---|---|---|---|"]
    for k, v in tm.items():
        b = v["bootstrap_95ci"]
        out.append(f"| {NAMES[k]} | {ci(b['accuracy'])} | {ci(b['f1_macro'])} | {ci(b['auc']) if 'auc' in b else 'n/a'} |")
    out += ["", "### Per-class results and confusion matrices (test set)\n"]
    for k, v in tm.items():
        out += [f"**{NAMES[k]}**\n", "| Class | Precision | Recall | F1 | Support | ROC-AUC (OvR) | Avg. precision (OvR) |",
                "|---|---|---|---|---|---|---|"]
        for c, d in v["per_class"].items():
            out.append(f"| {c}: {m['class_labels'][c]} | {f(d['precision'])} | {f(d['recall'])} | {f(d['f1'])} | "
                       f"{d['support']} | {f(d.get('roc_auc_ovr'))} | {f(d.get('average_precision_ovr'))} |")
        labels = " | ".join(f"pred {c}" for c in m["classes"])
        out += ["", f"| actual \\ predicted | {labels} |", "|---" * (len(m["classes"]) + 1) + "|"]
        for c, row in zip(m["classes"], v["confusion_matrix"]):
            out.append(f"| {c} | " + " | ".join(str(x) for x in row) + " |")
        out.append("")
    out += ["### Calibration (top-class reliability, hybrid, test set)\n",
            "| Confidence bin | Count | Mean confidence | Observed accuracy |", "|---|---|---|---|"]
    for r in tm["hybrid"]["calibration_table"]:
        out.append(f"| {r['bin']} | {r['count']} | {f(r['mean_confidence'])} | {f(r['accuracy'])} |")
    if m.get("leave_one_site_out_hybrid"):
        out += ["", "### Supplementary: leave-one-site-out (hybrid trained on the other three sites)\n",
                "| Held-out site | n | Accuracy (5-class) | Macro F1 (classes present) | Any-disease accuracy |",
                "|---|---|---|---|---|"]
        for s, v in m["leave_one_site_out_hybrid"].items():
            out.append(f"| {s} | {v['n']} | {f(v['accuracy'])} | {f(v['f1_macro_over_present_classes'])} | "
                       f"{f(v['any_disease_accuracy'])} |")
    out += ["", f"### Global SHAP importance of the hybrid ({g['n_rows_explained']} test rows, "
            f"{g['background_rows']} background rows, max additivity error {g['max_additivity_error']:.1e})\n",
            "| Rank | Feature | Mean abs. SHAP (probability points, averaged over classes) |", "|---|---|---|"]
    for i, (feat, v) in enumerate(g["mean_abs_shap_overall"].items(), 1):
        out.append(f"| {i} | {feat} | {v:.4f} |")
    out += ["", f"Figures: `artifacts/eval/{task}_roc.png`, `{task}_calibration.png`, `{task}_global_shap.png`, "
            f"`{task}_<model>_confusion.png`.\n"]
    return "\n".join(out)


def t1d_section() -> str:
    p = ROOT / "artifacts" / "eval" / "t1d_external_check.json"
    if not p.exists():
        return "## Exploratory check on the local T1D cohort\n\nNot run (python -m ml.external_t1d_check).\n"
    d = json.loads(p.read_text())
    out = ["## Exploratory check of the diabetes screen on the local type 1 cohort\n",
           f"Run with `python -m ml.external_t1d_check` on {d['n']} de-identified, diagnosed T1D children and "
           "adolescents. Because every person in this cohort has T1D, the only quantity that can be estimated is "
           "the share the screen flags as positive (a rough sensitivity). It is **not** a validation.\n",
           f"{d['share_with_no_mapped_symptom']:.1%} of the cohort had none of the five symptoms that exist in both datasets.\n",
           "| Scenario | Hybrid: share positive | RF: share positive | ANN: share positive | Hybrid: share high risk |",
           "|---|---|---|---|---|"]
    for k, r in d["results"].items():
        out.append(f"| {k} | {r['hybrid']['share_predicted_positive']:.1%} | {r['random_forest']['share_predicted_positive']:.1%} | "
                   f"{r['ann']['share_predicted_positive']:.1%} | {r['hybrid']['share_high_risk']:.1%} |")
    out += ["", "Caveats (from the script):\n", "```", d["caveats"], "```", ""]
    return "\n".join(out)


def main():
    head = """# Model evaluation

This file is generated by `python scripts/make_eval_report.py` from `artifacts/models/*/metadata.json`,
`global_shap.json` and `artifacts/eval/t1d_external_check.json`. Do not edit the numbers by hand; retrain
(`python -m ml.train`) and regenerate instead. Interpretation is in docs/MODEL_METHODOLOGY.md.

All numbers are retrospective results on public datasets. They describe software and model behaviour on
those datasets, not clinical accuracy.

**Metric notes.** Macro scores weight every class equally (important for the rare heart grades); weighted
scores weight by class frequency. Brier score is the mean squared error of the probability vector (lower is
better; for 5 classes it ranges 0 to 2). ECE is the top-label expected calibration error over 10 equal-width
bins (lower is better). Confidence intervals come from 1000 bootstrap resamples of the small test sets and
are wide; differences between models that fall inside each other's intervals are not evidence that one model
is better.
"""
    body = "\n".join([head, task_section("diabetes"), task_section("heart"), t1d_section()])
    (ROOT / "docs" / "MODEL_EVALUATION.md").write_text(body, encoding="utf-8")
    print("wrote docs/MODEL_EVALUATION.md")


if __name__ == "__main__":
    main()
