import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { useFeatureMeta } from "../useMeta";
import { GlobalImportance } from "../components/Explain";

export default function Landing() {
  const { user } = useAuth();
  const { meta } = useFeatureMeta();
  const [global, setGlobal] = useState<Record<string, number> | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    api.modelInfo("heart")
      .then((m) => {
        const all = m.global_shap?.mean_abs_shap_overall as Record<string, number> | undefined;
        if (all) setGlobal(Object.fromEntries(Object.entries(all).slice(0, 6)));
      })
      .catch(() => setUnavailable(true));
  }, []);

  return (
    <div className="landing">
      <section className="hero">
        <div className="hero-copy">
          <h1>See the reasons behind every screening result.</h1>
          <p className="lede">
            Answer a short set of questions about symptoms or heart test results. A Random Forest and a neural
            network are combined into one model, and every result shows which of your answers moved the estimate,
            and by how much.
          </p>
          <div className="hero-cta">
            {user ? (
              <Link className="btn" to="/dashboard">Go to your dashboard</Link>
            ) : (
              <>
                <Link className="btn" to="/register">Create a free account</Link>
                <Link className="btn ghost" to="/login">Log in</Link>
              </>
            )}
          </div>
          <p className="fine">Educational prototype. It screens, it does not diagnose.</p>
        </div>
        <figure className="hero-figure">
          <figcaption>
            <strong>What the heart model weighs most</strong>
            <span>Average size of each input's effect on the model's probabilities, measured with SHAP on held-out test patients (live from the trained model).</span>
          </figcaption>
          {global && meta ? <GlobalImportance ranked={global} spec={meta.heart.spec} />
            : unavailable ? <p className="fine">Model statistics are not available until the models are trained.</p>
              : <p className="loading" role="status">Loading model statistics…</p>}
        </figure>
      </section>

      <section className="feature-strip" aria-label="What you get">
        <div>
          <h2>Two screens</h2>
          <p>A symptom-based diabetes screen and a heart disease classifier that estimates angiographic severity grades 0 to 4.</p>
        </div>
        <div>
          <h2>Honest numbers</h2>
          <p>Probabilities from both component models are shown side by side, with warnings when they disagree or when inputs fall outside the training data.</p>
        </div>
        <div>
          <h2>Next steps</h2>
          <p>Diet, activity, sleep and follow-up suggestions tied to your answers, a BMI and lifestyle score, and a PDF you can take to a doctor.</p>
        </div>
      </section>

      <section className="note-block">
        <h2>About the diabetes screen</h2>
        <p>
          The original goal was early detection of type 1 diabetes. The available labelled data (the UCI Early Stage
          Diabetes Risk dataset) records diabetes without stating the type, so this screen estimates whether a symptom
          profile is consistent with diabetes in general. It cannot tell type 1 from type 2. A blood test is the only
          way to confirm either.
        </p>
      </section>
    </div>
  );
}
