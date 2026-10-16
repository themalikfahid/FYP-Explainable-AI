"""PDF health report generation (ReportLab). The report is rebuilt from the
stored prediction record, so its contents always match what the user saw."""
from __future__ import annotations

import io
from datetime import datetime, timezone

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from ml.data import TASKS
from backend.app.services.recommend import DISCLAIMER

INK = colors.HexColor("#1d2b36")
ACCENT = colors.HexColor("#1f6f78")
UP = colors.HexColor("#c0392b")
DOWN = colors.HexColor("#2471a3")
RISK_COLORS = {"low": colors.HexColor("#2e7d32"), "moderate": colors.HexColor("#b26a00"),
               "high": colors.HexColor("#c62828")}


def _fmt_value(task: str, feature: str, value) -> str:
    spec = TASKS[task]["spec"][feature]
    if value is None:
        return "Not provided"
    if spec.get("options"):
        return next((o["label"] for o in spec["options"] if float(o["value"]) == float(value)), str(value))
    return f"{value:g} {spec.get('unit', '')}".strip()


def _shap_chart(task: str, contributions: list[dict], width=170 * mm) -> Drawing:
    items = contributions[:8]
    row_h, label_w = 16, 70 * mm
    h = row_h * len(items) + 24
    d = Drawing(width, h)
    max_abs = max((abs(c["shap"]) for c in items), default=1e-9) or 1e-9
    half = (width - label_w - 10) / 2
    zero_x = label_w + half
    d.add(Line(zero_x, 8, zero_x, h - 4, strokeColor=colors.grey, strokeWidth=0.5))
    for i, c in enumerate(items):
        y = h - 20 - i * row_h
        label = TASKS[task]["spec"][c["feature"]]["label"]
        d.add(String(0, y + 3, label[:42], fontSize=7.5, fillColor=INK))
        w = abs(c["shap"]) / max_abs * (half - 30)
        x = zero_x if c["shap"] >= 0 else zero_x - w
        d.add(Rect(x, y, w, 10, fillColor=UP if c["shap"] >= 0 else DOWN, strokeColor=None))
        txt = f"{c['shap'] * 100:+.1f} pp"
        tx = zero_x + w + 3 if c["shap"] >= 0 else zero_x - w - 30
        d.add(String(tx, y + 2, txt, fontSize=7, fillColor=INK))
    d.add(String(zero_x + 4, 0, "raises probability ->", fontSize=6.5, fillColor=UP))
    d.add(String(zero_x - 72, 0, "<- lowers probability", fontSize=6.5, fillColor=DOWN))
    return d


def build_report(pred, user) -> bytes:
    task = pred.disease
    res = pred.result
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=f"Health screening report #{pred.id}",
                            author="XAI Health Screening (FYP prototype)")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=INK, fontSize=16, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=ACCENT, fontSize=12, spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12, textColor=INK)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=10, textColor=colors.HexColor("#4a5a66"))
    tbl_style = TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8.5),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f1f2")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b8c7cc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ])

    story = [
        Paragraph("Explainable AI Health Screening Report", h1),
        Paragraph(f"Report #{pred.id} &nbsp;|&nbsp; Prepared for {user.full_name} &nbsp;|&nbsp; "
                  f"Assessment time (UTC): {pred.created_at:%Y-%m-%d %H:%M} &nbsp;|&nbsp; "
                  f"Generated: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC", small),
        Spacer(1, 4),
        Paragraph(f"<b>Assessment:</b> {TASKS[task]['title']}", body),
    ]

    risk_color = RISK_COLORS[pred.risk_level].hexval()[2:]
    story += [
        Paragraph("Result", h2),
        Paragraph(f"<b>Risk level:</b> <font color='#{risk_color}'><b>{pred.risk_level.upper()}</b></font> "
                  f"&nbsp; ({res['risk_score_definition']}: <b>{pred.risk_score:.1%}</b>)", body),
        Paragraph(f"<b>Most likely class:</b> {res['predicted_label']}", body),
        Paragraph(f"Risk bands: low &lt; {res['risk_thresholds']['low_below']:.0%}, high &ge; "
                  f"{res['risk_thresholds']['high_at_or_above']:.0%}. {res['probability_note']}", small),
    ]
    rows = [["Class", "Hybrid (RF+ANN)", "Random Forest", "ANN"]]
    for c, p in res["probabilities"].items():
        rows.append([TASKS[task]["class_labels"][int(c)], f"{p:.1%}",
                     f"{res['components']['random_forest'][c]:.1%}", f"{res['components']['ann'][c]:.1%}"])
    story += [Spacer(1, 3), Table(rows, colWidths=[78 * mm, 32 * mm, 30 * mm, 30 * mm], style=tbl_style)]
    if res.get("warnings"):
        story.append(Spacer(1, 3))
        for w in res["warnings"]:
            story.append(Paragraph(f"&#9888; {w}", small))

    exp = res.get("explanation")
    if exp:
        label = TASKS[task]["class_labels"][int(exp["explained_class"])]
        story += [Paragraph("Why the model gave this result (SHAP)", h2),
                  Paragraph(f"Contributions of each input to the estimated probability of <b>{label}</b>, in "
                            f"percentage points (pp). Baseline (average) probability {exp['base_value']:.1%} "
                            f"&rarr; this assessment {exp['predicted_probability']:.1%}.", body),
                  _shap_chart(task, exp["contributions"])]
        for s in exp.get("summary", []):
            story.append(Paragraph("&bull; " + s, body))
        story.append(Paragraph("SHAP values describe how the model used each input. They do not prove that a "
                               "factor causes disease.", small))

    rows = [["Input", "Value"]] + [[TASKS[task]["spec"][f]["label"], _fmt_value(task, f, v)]
                                   for f, v in pred.inputs.items()]
    story += [Paragraph("Inputs provided", h2),
              Table(rows, colWidths=[100 * mm, 70 * mm], style=tbl_style, repeatRows=1)]

    recs = res.get("recommendations", {})
    if recs.get("bmi") or recs.get("lifestyle_score"):
        story.append(Paragraph("BMI and lifestyle score", h2))
        if recs.get("bmi"):
            b = recs["bmi"]
            story.append(Paragraph(f"<b>BMI:</b> {b['bmi']} kg/m&sup2; ({b['category']}; {b['cutoffs']}). "
                                   f"Healthy weight range for your height: {b['healthy_weight_range_kg'][0]}-"
                                   f"{b['healthy_weight_range_kg'][1]} kg. {b['note']}", body))
        if recs.get("lifestyle_score"):
            ls = recs["lifestyle_score"]
            comp = ", ".join(f"{k.replace('_', ' ')} {v['points']}/{v['max']}" for k, v in ls["components"].items())
            story.append(Paragraph(f"<b>Lifestyle score:</b> {ls['score']}/100 ({ls['band']}) &mdash; {comp}. "
                                   f"{ls['note']}", body))

    if recs.get("items"):
        rows = [["Priority", "Area", "Recommendation"]]
        for r in recs["items"]:
            rows.append([r["priority"].capitalize(), r["category"].replace("_", " ").capitalize(),
                         Paragraph(f"{r['text']}<br/><font size=6.5 color='#4a5a66'>Source: {r['source']}</font>",
                                   body)])
        story += [Paragraph("Personalised recommendations", h2),
                  Table(rows, colWidths=[18 * mm, 28 * mm, 124 * mm], style=tbl_style, repeatRows=1)]

    m = res["model"]
    story += [KeepTogether([
        Paragraph("About the model", h2),
        Paragraph(f"Model version: {m['version']}. Production model: {m['production_model']}. Held-out test "
                  f"metrics (n={m['test_metrics'].get('n_test')}): " +
                  ", ".join(f"{k.replace('_', ' ')} {v:.3f}" for k, v in m["test_metrics"].items() if k != "n_test") +
                  ". These are retrospective results on a public dataset, not clinical validation.", small),
        Spacer(1, 6),
        Paragraph(f"<b>Important:</b> {DISCLAIMER}", body),
    ])]
    doc.build(story)
    return buf.getvalue()
