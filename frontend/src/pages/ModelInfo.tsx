import { useEffect, useState } from "react";
import { api, type Task } from "../api";
import { GlobalImportance } from "../components/Explain";
import { useFeatureMeta } from "../useMeta";

const MODEL_NAMES: Record<string, string> = { random_forest: "Random Forest", ann: "ANN (MLP)", hybrid: "Hybrid (RF + ANN)" };
const f3 = (v: number | undefined) => (v === undefined || v === null ? "n/a" : v.toFixed(3));

export default function ModelInfo() {
  const { meta } = useFeatureMeta();
  const [task, setTask] = useState<Task>("heart");
  const [info, setInfo] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setInfo(null); setError("");
    api.modelInfo(task).then(setInfo).catch((e) => setError(e.message));
  }, [task]);

  const auc = (m: any) => m.roc_auc ?? m.roc_auc_ovr_macro;
  return (
    <div className="page">
      <div className="page-head">
        <h1>How the models work</h1>
        <div className="tabs" role="tablist" aria-label="Choose model">
          {(["heart", "diabetes"] as Task[]).map((t) => (
            <button key={t} role="tab" aria-selected={task === t} className={task === t ? "tab on" : "tab"} onClick={() => setTask(t)}>
              {t === "heart" ? "Heart disease" : "Diabetes screen"}
            </button>
          ))}
        </div>
      </div>
      {error && <p className="banner error" role="alert">{error}</p>}
      {!info && !error && <p className="loading" role="status">Loading model information…</p>}
      {info && meta && (
        <div className="model-info" role="tabpanel">
          <p className="lede">{info.title}. Trained on {info.split.train} records and tested once on {info.split.test} records the
            models never saw during training or tuning (stratified split, duplicates removed first).</p>
          <section className="panel">
            <h2>Held-out test results</h2>
            <div className="table-scroll">
              <table className="metrics">
                <thead><tr><th scope="col">Model</th><th scope="col">Accuracy</th><th scope="col">Macro F1</th><th scope="col">Weighted F1</th>
                  <th scope="col">ROC-AUC{task === "heart" ? " (macro OvR)" : ""}</th>
                  {task === "heart" && <th scope="col">Any-disease AUC</th>}<th scope="col">Brier</th><th scope="col">ECE</th></tr></thead>
                <tbody>
                  {Object.entries(info.test_metrics).map(([k, m]: [string, any]) => (
                    <tr key={k} className={k === "hybrid" ? "is-pred" : undefined}>
                      <th scope="row">{MODEL_NAMES[k]}</th><td>{f3(m.accuracy)}</td><td>{f3(m.f1_macro)}</td><td>{f3(m.f1_weighted)}</td>
                      <td>{f3(auc(m))}</td>{task === "heart" && <td>{f3(m.any_disease_roc_auc)}</td>}<td>{f3(m.brier)}</td><td>{f3(m.ece_top_label)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="fine">Hybrid 95% bootstrap intervals: accuracy {info.test_metrics.hybrid.bootstrap_95ci.accuracy.map(f3).join(" to ")},
              macro F1 {info.test_metrics.hybrid.bootstrap_95ci.f1_macro.map(f3).join(" to ")}. The test set is small, so differences between models
              within these intervals are not meaningful. The deployed model is the hybrid, as the project proposal specifies.</p>
            <h3>Cross-validation on the training set (5 folds, repeated)</h3>
            <ul className="plain">
              {Object.entries(info.cv_train_repeated).map(([k, v]: [string, any]) => (
                <li key={k}>{MODEL_NAMES[k]}: macro F1 {f3(v.f1_macro.mean)} ± {f3(v.f1_macro.std)}, accuracy {f3(v.accuracy.mean)} ± {f3(v.accuracy.std)}</li>
              ))}
            </ul>
          </section>
          <section className="panel">
            <h2>Per-class results of the hybrid</h2>
            <div className="table-scroll">
              <table className="metrics">
                <thead><tr><th scope="col">Class</th><th scope="col">Precision</th><th scope="col">Recall</th><th scope="col">F1</th><th scope="col">Test cases</th></tr></thead>
                <tbody>
                  {Object.entries(info.test_metrics.hybrid.per_class).map(([c, m]: [string, any]) => (
                    <tr key={c}><th scope="row">{meta[task].class_labels[c]}</th><td>{f3(m.precision)}</td><td>{f3(m.recall)}</td><td>{f3(m.f1)}</td><td>{m.support}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {info.global_shap && (
            <section className="panel">
              <h2>What the hybrid model relies on overall</h2>
              <p>Mean absolute SHAP value per input on {info.global_shap.n_rows_explained} test records, in percentage points of probability.</p>
              <GlobalImportance ranked={info.global_shap.mean_abs_shap_overall} spec={meta[task].spec} />
            </section>
          )}
          <section className="panel">
            <h2>How the hybrid is built</h2>
            <p>Deployed: <strong>{info.hybrid_description}</strong>.</p>
            <p>The Random Forest and the neural network each produce class probabilities. Two ways of combining them were compared
              using cross-validation on the training data only: stacking, where a logistic-regression meta-model learns the combination
              from out-of-fold predictions (5-fold, so it never sees over-fitted in-sample outputs), and weighted soft voting, which
              averages the two probability sets with a tuned weight. The better one by macro F1 was kept. Explanations are computed
              on this final combined output, not on either component alone.</p>
            {info.hybrid_candidates && (
              <ul className="plain">{Object.entries(info.hybrid_candidates).map(([k, v]: [string, any]) => (
                <li key={k}>{k === "stacking" ? "Stacking" : "Soft voting"}: cross-validated macro F1 {f3(v.cv_f1_macro)}</li>))}</ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
