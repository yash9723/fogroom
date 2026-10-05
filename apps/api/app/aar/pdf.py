"""Server-side PDF export of an AAR report (reportlab - pure Python, no system deps)."""

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6B7280")
ACCENT = colors.HexColor("#0E7490")
RULE = colors.HexColor("#D1D5DB")


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text if text is not None else "-")), style)


def _table(rows: list[list[Any]], widths: list[float], body: ParagraphStyle) -> Table:
    data = [[_p(c, body) if not isinstance(c, Paragraph) else c for c in row] for row in rows]
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, INK),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _fmt(seconds: Any) -> str:
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return "-"
    return f"T+{total // 60:02d}:{total % 60:02d}"


def render_pdf(report: dict[str, Any], narrative: str | None = None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"FOGROOM AAR - {report['exercise']['title']}",
        author="FOGROOM",
    )
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=INK, fontSize=18, spaceAfter=4)
    h2 = ParagraphStyle(
        "h2", parent=ss["Heading2"], textColor=ACCENT, fontSize=12.5, spaceBefore=10, spaceAfter=4
    )
    body = ParagraphStyle("body", parent=ss["BodyText"], textColor=INK, fontSize=8.8, leading=11.5)
    small = ParagraphStyle("small", parent=body, textColor=MUTED, fontSize=7.8, leading=10)

    ex = report["exercise"]
    team = report["team"]
    story: list[Any] = [
        _p("FOGROOM - After Action Review", small),
        _p(ex["title"], h1),
        _p(
            f"Scenario: {ex['scenario']}  |  Room {ex['room_code']}  |  Duration {ex['duration_label']}  |  "
            f"{ex['participant_count']} participants",
            small,
        ),
        Spacer(1, 6),
        _p(report["summary"], body),
    ]
    if narrative:
        story += [_p("Narrative summary", h2), _p(narrative, body)]

    story += [_p("Training objectives", h2)]
    for obj in report.get("objectives", []):
        story.append(
            _p(f"{obj['title']}", ParagraphStyle("o", parent=body, fontName="Helvetica-Bold"))
        )
        for line in obj.get("observations", [])[:6]:
            story.append(_p(f"- {line}", body))

    story += [
        _p("Team metrics", h2),
        _table(
            [
                [
                    "Team score",
                    "Decision agreement",
                    "Avg confidence",
                    "Avg response",
                    "Avg uncertainty at decision",
                    "Avg coordination",
                ],
                [
                    f"{team['team_score']:.0f}",
                    f"{team['decision_agreement']:.0f}%",
                    f"{team['average_confidence']:.0f}%",
                    f"{team['average_response_time_s']:.0f}s",
                    f"{team['average_uncertainty_at_decision']:.0f}",
                    f"{team['average_coordination']:.0f}",
                ],
            ],
            [29 * mm] * 6,
            body,
        ),
        _p("Participant metrics", h2),
        _table(
            [
                [
                    "Callsign",
                    "Response",
                    "Awareness",
                    "Quality",
                    "Coordination",
                    "Uncertainty mgmt",
                    "Avg conf.",
                    "High-uncert. decisions",
                ]
            ]
            + [
                [
                    p["callsign"],
                    f"{p['decision_response_score']:.0f}",
                    f"{p['information_awareness']:.0f}",
                    f"{p['decision_quality']:.0f}",
                    f"{p['coordination_score']:.0f}",
                    f"{p['uncertainty_management']:.0f}",
                    f"{p['average_confidence']:.0f}%",
                    str(p["decisions_under_high_uncertainty"]),
                ]
                for p in report["participants"]
            ],
            [22 * mm, 20 * mm, 21 * mm, 19 * mm, 23 * mm, 25 * mm, 19 * mm, 27 * mm],
            body,
        ),
        _p("Important decisions", h2),
        _table(
            [["Time", "Who", "Decision point", "Choice", "Conf.", "Uncert.", "Rationale"]]
            + [
                [
                    d["submitted_label"],
                    d["callsign"],
                    d["decision_point_title"],
                    d["selected_label"] or d["decision_text"],
                    f"{d['confidence']}%",
                    f"{(d['uncertainty_index'] or 0):.0f}",
                    d["rationale"] or "-",
                ]
                for d in report["decisions"]
            ],
            [16 * mm, 17 * mm, 32 * mm, 38 * mm, 12 * mm, 13 * mm, 50 * mm],
            body,
        ),
        PageBreak(),
        _p("Communication disruptions", h2),
        _table(
            [["Start", "End", "Type", "Targets", "Channels", "Source"]]
            + [
                [
                    _fmt(d["start_sim_time"]),
                    _fmt(d["end_sim_time"]),
                    d["disruption_type"],
                    ", ".join(d["targets"]),
                    ", ".join(d["channels"]) or "-",
                    d["source"],
                ]
                for d in report["disruptions"]
            ],
            [16 * mm, 16 * mm, 34 * mm, 40 * mm, 40 * mm, 32 * mm],
            body,
        ),
        _p("Information outcomes (timeline summary)", h2),
    ]
    lines = [
        f"{_fmt(o['created_sim_time'])}  {o['label']} - {o['title']}: " + "; ".join(o["narrative"])
        for o in report["information_outcomes"]
        if o["narrative"]
    ]
    for line in lines or ["All information was delivered on time to every recipient."]:
        story.append(_p(line, body))

    story.append(_p("Instructor notes", h2))
    for n in report["notes"] or [{"label": "", "content": "No notes recorded."}]:
        story.append(_p(f"{n['label']}  {n['content']}", body))

    story.append(_p("Recommendations", h2))
    for rec in report["recommendations"]:
        story.append(_p(f"- {rec}", body))

    story += [Spacer(1, 8), _p(report["metric_disclaimer"], small)]
    for name, formula in report["formulas"].items():
        story.append(_p(f"{name.replace('_', ' ').title()}: {formula}", small))

    def _footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            16 * mm, 9 * mm, "FOGROOM - fictional training exercise - experimental training metrics"
        )
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
