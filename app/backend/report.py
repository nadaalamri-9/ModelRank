# ModelRank - PDF Report

import re
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.platypus.flowables import HRFlowable


# ModelRank design system (matches the website)

PAGE_BG = colors.HexColor("#0A0909")
SURFACE = colors.HexColor("#141210")
SURFACE_RAISED = colors.HexColor("#1B1815")
BORDER = colors.HexColor("#2A2521")
TEXT_PRIMARY = colors.HexColor("#F3EFE9")
TEXT_SECONDARY = colors.HexColor("#A09A93")
TEXT_MUTED = colors.HexColor("#6F6963")
ACCENT = colors.HexColor("#D9A07F")

# Copper at roughly 12% over the card surface, for the winner row
ACCENT_TINT = colors.HexColor("#2C231D")

# Verdicts: the website's status colors, each over a faint tint of itself
VERDICT_STYLES = {
    "pass": (colors.HexColor("#C9DFC3"), colors.HexColor("#1B1E17")),
    "partial": (colors.HexColor("#E4D2A6"), colors.HexColor("#241E16")),
    "fail": (colors.HexColor("#DEB2AA"), colors.HexColor("#221815")),
}

CONTENT_WIDTH = 174 * mm


def text(value, fallback="-") -> str:
    """Judge text is free-form; escape it so ReportLab markup never breaks."""

    if value is None or value == "":
        return fallback

    return escape(str(value))


def format_test_id(test_id) -> str:
    """Display only: tc_01 -> TC-01."""

    return re.sub(r"^tc[_-]?", "TC-", str(test_id), flags=re.IGNORECASE)


def draw_page(canvas, document):
    """Dark page background and a small footer on every page."""

    width, height = A4

    canvas.saveState()

    canvas.setFillColor(PAGE_BG)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(document.leftMargin, 10 * mm, "ModelRank")
    canvas.drawRightString(
        width - document.rightMargin,
        10 * mm,
        f"Page {document.page}"
    )

    canvas.restoreState()


def generate_pdf_report(
    user_request: str,
    final_decision: dict
) -> BytesIO:
    """Generate a PDF report for the latest ModelRank evaluation."""

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="ModelRank Evaluation Report",
        author="ModelRank"
    )

    styles = getSampleStyleSheet()

    def style(name, **overrides):
        base = {
            "parent": styles["BodyText"],
            "fontName": "Helvetica",
            "fontSize": 10,
            "leading": 15,
            "textColor": TEXT_PRIMARY,
        }
        base.update(overrides)

        return ParagraphStyle(name, **base)

    brand_style = style(
        "ModelRankBrand",
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=32,
    )

    subtitle_style = style(
        "ModelRankSubtitle",
        fontSize=10.5,
        leading=14,
        textColor=TEXT_SECONDARY,
    )

    # Small copper uppercase label, like the website's eyebrows
    eyebrow_style = style(
        "ModelRankEyebrow",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=ACCENT,
        spaceBefore=18,
        spaceAfter=8,
    )

    body_style = style("ModelRankBody")

    secondary_style = style(
        "ModelRankSecondary",
        textColor=TEXT_SECONDARY,
    )

    small_style = style(
        "ModelRankSmall",
        fontSize=8,
        leading=11.5,
        textColor=TEXT_SECONDARY,
    )

    small_primary_style = style(
        "ModelRankSmallPrimary",
        fontSize=8,
        leading=11.5,
    )

    header_cell_style = style(
        "ModelRankHeaderCell",
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=TEXT_SECONDARY,
    )

    best_name_style = style(
        "ModelRankBestName",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
    )

    meta_style = style(
        "ModelRankMeta",
        fontSize=9.5,
        leading=13,
        textColor=TEXT_SECONDARY,
    )

    model_heading_style = style(
        "ModelRankModelHeading",
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
    )

    model_id_style = style(
        "ModelRankModelId",
        fontSize=8,
        leading=11,
        textColor=TEXT_MUTED,
    )

    card_label_style = style(
        "ModelRankCardLabel",
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=TEXT_MUTED,
    )

    def eyebrow(label):
        return Paragraph(label.upper(), eyebrow_style)

    # Shared look for dark cards and tables
    card_padding = [
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]

    story = []

    selected_model = final_decision.get("selected_model")
    model_rankings = final_decision.get("model_rankings", [])
    decision_reason = final_decision.get("decision_reason", "")
    retry_required = final_decision.get("retry_required", False)
    retry_reason = final_decision.get("retry_reason", "")

    report_date = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Header

    story.append(
        Paragraph(
            "ModelRank",
            brand_style
        )
    )

    story.append(Spacer(1, 4))

    story.append(
        Paragraph(
            "LLM Evaluation Report",
            subtitle_style
        )
    )

    story.append(Spacer(1, 10))

    story.append(
        HRFlowable(
            width=22 * mm,
            thickness=1.5,
            color=ACCENT,
            hAlign="LEFT",
            spaceBefore=0,
            spaceAfter=6
        )
    )

    # Report Information

    story.append(eyebrow("Evaluation Overview"))

    overview_data = [
        [
            Paragraph("Report date", small_style),
            Paragraph(report_date, small_primary_style)
        ],
        [
            Paragraph("Evaluation status", small_style),
            Paragraph(
                "Retry required" if retry_required else "Completed",
                small_primary_style
            )
        ],
        [
            Paragraph("Selected model", small_style),
            Paragraph(
                text(selected_model.get("name"), "No model selected")
                if selected_model
                else "No model selected",
                small_primary_style
            )
        ]
    ]

    overview_table = Table(
        overview_data,
        colWidths=[
            45 * mm,
            CONTENT_WIDTH - 45 * mm
        ]
    )

    overview_table.setStyle(
        TableStyle(
            card_padding + [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    story.append(overview_table)

    # Project Description

    story.append(eyebrow("Project Description"))

    story.append(
        Paragraph(
            text(user_request),
            secondary_style
        )
    )

    # Best Model

    story.append(eyebrow("Best Match"))

    best_rows = [
        [
            Paragraph(
                text(selected_model.get("name"))
                if selected_model
                else "No model selected",
                best_name_style
            )
        ]
    ]

    if selected_model:
        best_rows.append(
            [
                Paragraph(
                    text(selected_model.get("provider")),
                    meta_style
                )
            ]
        )

    best_rows.append(
        [
            Paragraph(
                text(decision_reason, "No decision reason available."),
                secondary_style
            )
        ]
    )

    best_table = Table(
        best_rows,
        colWidths=[CONTENT_WIDTH]
    )

    best_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.6, ACCENT),
                ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, 0), 16),
                ("TOPPADDING", (0, -1), (-1, -1), 10),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 16),
            ]
        )
    )

    story.append(best_table)

    # Rankings

    story.append(eyebrow("Model Comparison"))

    ranking_data = [
        [
            "Rank",
            "Model",
            "Provider",
            "Pass",
            "Partial",
            "Fail",
            "Latency",
            "Cost"
        ]
    ]

    for ranking in model_rankings:
        latency = ranking.get("average_latency_seconds")
        cost = ranking.get("total_cost_usd")

        ranking_data.append(
            [
                f"#{ranking.get('rank', '-')}",
                Paragraph(text(ranking.get("name")), small_primary_style),
                Paragraph(text(ranking.get("provider")), small_style),
                str(ranking.get("passed_tests", 0)),
                str(ranking.get("partial_tests", 0)),
                str(ranking.get("failed_tests", 0)),
                (
                    f"{latency:.1f}s"
                    if isinstance(latency, (int, float))
                    else "-"
                ),
                (
                    f"${cost:.6f}"
                    if isinstance(cost, (int, float))
                    else "-"
                )
            ]
        )

    # Winner is the selected model; fall back to rank 1 (+1 skips the header)
    selected_id = selected_model.get("model_id") if selected_model else None

    winner_row = next(
        (
            index + 1
            for index, ranking in enumerate(model_rankings)
            if selected_id and ranking.get("model_id") == selected_id
        ),
        next(
            (
                index + 1
                for index, ranking in enumerate(model_rankings)
                if ranking.get("rank") == 1
            ),
            None
        )
    )

    # Rank, Model, Provider, Pass, Partial, Fail, Latency; Cost takes the rest
    ranking_widths = [w * mm for w in (13, 42, 25, 13, 15, 13, 22)]

    ranking_table = Table(
        ranking_data,
        repeatRows=1,
        colWidths=ranking_widths + [CONTENT_WIDTH - sum(ranking_widths)]
    )

    ranking_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SURFACE_RAISED),
                ("TEXTCOLOR", (0, 0), (-1, 0), TEXT_SECONDARY),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 7),
                ("BACKGROUND", (0, 1), (-1, -1), SURFACE),
                ("TEXTCOLOR", (0, 1), (-1, -1), TEXT_PRIMARY),
                ("TEXTCOLOR", (0, 1), (0, -1), TEXT_MUTED),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    if winner_row is not None:
        ranking_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, winner_row), (-1, winner_row), ACCENT_TINT),
                    ("LINEBEFORE", (0, winner_row), (0, winner_row), 2, ACCENT),
                    ("TEXTCOLOR", (0, winner_row), (0, winner_row), ACCENT),
                    ("FONTNAME", (0, winner_row), (-1, winner_row), "Helvetica-Bold"),
                ]
            )
        )

    story.append(ranking_table)

    # Detailed Model Assessments

    for ranking in model_rankings:
        story.append(PageBreak())

        story.append(eyebrow(f"Model #{ranking.get('rank', '-')}"))

        # Heading card: name, then provider and model ID, then the two
        # Judge notes, each under its own small label
        detail_rows = [
            [Paragraph(text(ranking.get("name"), "Model"), model_heading_style)],
            [Paragraph(text(ranking.get("provider")), meta_style)],
            [Paragraph(text(ranking.get("model_id")), model_id_style)],
            [Paragraph("QUALITY ASSESSMENT", card_label_style)],
            [
                Paragraph(
                    text(
                        ranking.get("quality_assessment"),
                        "No quality assessment available."
                    ),
                    secondary_style
                )
            ],
            [Paragraph("RANKING REASON", card_label_style)],
            [Paragraph(text(ranking.get("reason")), secondary_style)],
        ]

        detail_table = Table(
            detail_rows,
            colWidths=[CONTENT_WIDTH]
        )

        detail_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                    ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 16),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, 0), 16),
                    # Rule under the model ID, and between the two notes
                    ("BOTTOMPADDING", (0, 2), (-1, 2), 12),
                    ("LINEBELOW", (0, 2), (-1, 2), 0.4, BORDER),
                    ("TOPPADDING", (0, 3), (-1, 3), 12),
                    ("BOTTOMPADDING", (0, 4), (-1, 4), 12),
                    ("LINEBELOW", (0, 4), (-1, 4), 0.4, BORDER),
                    ("TOPPADDING", (0, 5), (-1, 5), 12),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 16),
                ]
            )
        )

        story.append(detail_table)

        assessments = ranking.get(
            "test_case_assessments",
            []
        )

        if assessments:
            story.append(eyebrow("Test Cases"))

            assessment_data = [
                [
                    Paragraph("TEST", header_cell_style),
                    Paragraph("CRITERION", header_cell_style),
                    Paragraph("VERDICT", header_cell_style),
                    Paragraph("REASON", header_cell_style),
                ]
            ]

            verdict_commands = []

            for row, assessment in enumerate(assessments, start=1):
                verdict = str(assessment.get("verdict", "-")).lower()
                verdict_color, verdict_tint = VERDICT_STYLES.get(
                    verdict,
                    (TEXT_SECONDARY, SURFACE)
                )

                verdict_commands.append(
                    ("BACKGROUND", (2, row), (2, row), verdict_tint)
                )

                assessment_data.append(
                    [
                        Paragraph(
                            text(format_test_id(
                                assessment.get("test_case_id", "-")
                            )),
                            small_style
                        ),
                        Paragraph(
                            text(assessment.get("criterion")),
                            small_primary_style
                        ),
                        Paragraph(
                            text(verdict).upper(),
                            style(
                                f"ModelRankVerdict{row}",
                                fontName="Helvetica-Bold",
                                fontSize=7,
                                leading=11.5,
                                textColor=verdict_color,
                            )
                        ),
                        Paragraph(
                            text(assessment.get("reason")),
                            small_style
                        ),
                    ]
                )

            assessment_table = Table(
                assessment_data,
                repeatRows=1,
                colWidths=[
                    18 * mm,
                    40 * mm,
                    20 * mm,
                    CONTENT_WIDTH - 78 * mm
                ]
            )

            assessment_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), SURFACE_RAISED),
                        ("BACKGROUND", (0, 1), (-1, -1), SURFACE),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                        ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORDER),
                        ("LEFTPADDING", (0, 0), (-1, -1), 7),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                        ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ]
                    + verdict_commands
                )
            )

            story.append(assessment_table)

    # Retry Information

    if retry_required:
        story.append(PageBreak())

        story.append(eyebrow("Retry Required"))

        story.append(
            Paragraph(
                text(
                    retry_reason,
                    "The current candidates require another evaluation."
                ),
                secondary_style
            )
        )

    document.build(
        story,
        onFirstPage=draw_page,
        onLaterPages=draw_page
    )

    buffer.seek(0)

    return buffer
