import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ClipboardList, Download, Trash2 } from "lucide-react";
import { Alert, Button, Card, Empty, PageHead, RiskBadge, Segmented, Skeleton, usePageTitle, useToast } from "../components/ui";
import { api, type PredictionSummary, type Task } from "../lib/api";
import { dateTime, pct, taskName } from "../lib/format";

export default function History() {
  usePageTitle("History");
  const toast = useToast();
  const [filter, setFilter] = useState<"all" | Task>("all");
  const [items, setItems] = useState<PredictionSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState("");

  const load = () => { setItems(null); api.history(filter === "all" ? undefined : filter, 100).then((r) => { setItems(r.items); setTotal(r.total); }).catch((e) => setErr(e.message)); };
  useEffect(load, [filter]); // eslint-disable-line react-hooks/exhaustive-deps

  async function remove(id: number) {
    if (!window.confirm("Delete this assessment permanently?")) return;
    try { await api.deletePrediction(id); toast("Deleted", "ok"); load(); } catch (e: any) { toast(e.message, "error"); }
  }
  async function pdf(id: number) { try { await api.downloadReport(id); } catch (e: any) { toast(e.message, "error"); } }

  return (
    <>
      <PageHead title="History" subtitle={`${total} saved assessment${total === 1 ? "" : "s"}`}
        actions={<Segmented label="Filter" value={filter} onChange={setFilter} options={[{ value: "all", label: "All" }, { value: "heart", label: "Heart" }, { value: "diabetes", label: "Diabetes" }, { value: "cad", label: "Coronary" }]} />} />
      {err && <Alert tone="error">{err}</Alert>}
      <Card>
        {!items ? <Skeleton h={200} /> : items.length === 0 ? (
          <Empty icon={<ClipboardList size={26} />} title="Nothing here yet" action={<Button variant="primary" to="/app/assess">New assessment</Button>}>Your saved assessments will appear here.</Empty>
        ) : (
          <div className="table-scroll"><table className="table">
            <thead><tr><th>Assessment</th><th>Date</th><th className="num">Score</th><th>Level</th><th aria-label="Actions" /></tr></thead>
            <tbody>{items.map((r) => (
              <tr key={r.id!}>
                <td><Link to={`/app/result/${r.id}`}>{taskName(r.disease)}</Link></td>
                <td className="muted">{dateTime(r.created_at)}</td>
                <td className="num">{pct(r.risk_score, 1)}</td>
                <td><RiskBadge level={r.risk_level} /></td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  <Button size="sm" variant="ghost" aria-label="Download PDF" onClick={() => pdf(r.id!)} icon={<Download size={15} />} />
                  <Button size="sm" variant="ghost" aria-label="Delete assessment" onClick={() => remove(r.id!)} icon={<Trash2 size={15} />} />
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </>
  );
}
