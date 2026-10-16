import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError, type Prediction } from "../api";
import PredictionView from "../components/PredictionView";
import { useFeatureMeta } from "../useMeta";

export default function ResultPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const { meta, error: metaError } = useFeatureMeta();
  const [p, setP] = useState<Prediction | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const n = Number(id);
    if (!Number.isInteger(n) || n <= 0) { setError("This assessment doesn't exist."); return; }
    setP(null); setError("");
    api.prediction(n).then(setP).catch((e) =>
      setError(e instanceof ApiError && e.status === 404 ? "This assessment doesn't exist or belongs to another account." : e.message));
  }, [id]);

  if (error || metaError) return <div className="page"><p className="banner error" role="alert">{error || metaError}</p></div>;
  if (!p || !meta) return <div className="page"><p className="loading" role="status">Loading result…</p></div>;
  return <div className="page wide"><PredictionView p={p} meta={meta} onDeleted={() => nav("/history", { state: { message: "Assessment deleted." } })} /></div>;
}
