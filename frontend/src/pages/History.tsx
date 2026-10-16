import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, ApiError, type PredictionSummary, type Task } from "../api";
import { RiskBadge } from "../components/Explain";

const PAGE = 15;

export default function History() {
  const loc = useLocation() as { state?: { message?: string } };
  const [filter, setFilter] = useState<Task | "">("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{ total: number; items: PredictionSummary[] } | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  function load() {
    setError("");
    api.history(filter || undefined, PAGE, offset).then(setData).catch((e) => setError(e.message));
  }
  useEffect(load, [filter, offset]);

  async function pdf(id: number) {
    setBusyId(id);
    try { await api.downloadReport(id); } catch (e) { setError(e instanceof ApiError ? e.message : "Report failed."); }
    setBusyId(null);
  }
  async function del(id: number) {
    if (!window.confirm("Delete this assessment? This can't be undone.")) return;
    setBusyId(id);
    try { await api.deletePrediction(id); load(); } catch (e) { setError(e instanceof ApiError ? e.message : "Delete failed."); }
    setBusyId(null);
  }

  return (
    <div className="page">
      <div className="page-head">
        <h1>Assessment history</h1>
        <label className="inline-select">Show
          <select value={filter} onChange={(e) => { setFilter(e.target.value as Task | ""); setOffset(0); }}>
            <option value="">All assessments</option>
            <option value="diabetes">Diabetes screens</option>
            <option value="heart">Heart assessments</option>
          </select>
        </label>
      </div>
      {loc.state?.message && <p className="banner info" role="status">{loc.state.message}</p>}
      {error && <p className="banner error" role="alert">{error}</p>}
      {!data && !error && <p className="loading" role="status">Loading…</p>}
      {data && data.items.length === 0 && (
        <div className="empty">
          <p>No assessments to show.</p>
          <p><Link className="btn" to="/assess/diabetes">Start a diabetes screen</Link> <Link className="btn ghost" to="/assess/heart">Start a heart assessment</Link></p>
        </div>
      )}
      {data && data.items.length > 0 && (
        <>
          <table className="history">
            <thead><tr><th scope="col">Date</th><th scope="col">Assessment</th><th scope="col">Risk</th><th scope="col">Score</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {data.items.map((i) => (
                <tr key={i.id}>
                  <td data-label="Date">{new Date(i.created_at).toLocaleString()}</td>
                  <td data-label="Assessment"><Link to={`/history/${i.id}`}>{i.disease === "heart" ? "Heart disease" : "Diabetes symptoms"}</Link></td>
                  <td data-label="Risk"><RiskBadge level={i.risk_level} /></td>
                  <td data-label="Score">{(i.risk_score * 100).toFixed(1)}%</td>
                  <td className="row-actions">
                    <Link to={`/history/${i.id}`}>View</Link>
                    <button className="link-btn" onClick={() => pdf(i.id!)} disabled={busyId === i.id}>PDF</button>
                    <button className="link-btn danger" onClick={() => del(i.id!)} disabled={busyId === i.id}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pager">
            <button className="btn ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Newer</button>
            <span>{offset + 1}-{Math.min(offset + PAGE, data.total)} of {data.total}</span>
            <button className="btn ghost" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>Older</button>
          </div>
        </>
      )}
    </div>
  );
}
