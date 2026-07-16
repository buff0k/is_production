from __future__ import annotations

from io import BytesIO
from math import ceil
from typing import BinaryIO

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


SLIDE_WIDTH = 13.333
SLIDE_HEIGHT = 7.5
FONT_NAME = "Aptos"

NAVY = "0F1F53"
DARK_NAVY = "102A43"
GREEN = "18A957"
RED = "E03124"
ORANGE = "D97706"
BLUE = "2563EB"
WHITE = "FFFFFF"
LIGHT_BG = "F4F6F8"
LIGHT_BORDER = "D7DDE5"
MUTED = "62708A"
TEXT = "304055"
PALE_GREEN = "DFEEE5"
PALE_RED = "F5EAEA"
PALE_ORANGE = "FFF4E5"
PALE_BLUE = "EAF2FF"
PALE_YELLOW = "FEF3C7"
YELLOW = "CA8A04"
GRAY = "6B7280"
DARK_GRAY = "374151"
AVAIL_BAR = "F59E0B"
UTIL_BAR = "737373"
AVAIL_TARGET_LINE = "FF0000"
UTIL_TARGET_LINE = "7AC943"
SPARE_PURPLE = "D291FF"
SPARE_PURPLE_DARK = "6B21A8"


def build_hod_presentation(
    payload: dict,
    output: BinaryIO | BytesIO,
) -> None:
    """Build one presentation containing all selected sites."""

    prs = Presentation()
    prs.slide_width = Inches(SLIDE_WIDTH)
    prs.slide_height = Inches(SLIDE_HEIGHT)

    site_payloads = (
        payload.get("site_payloads")
        or [payload]
    )

    combined_site_name = (
        payload.get("site")
        or " / ".join(
            str(item.get("site") or "")
            for item in site_payloads
        )
    )

    title_payload = dict(site_payloads[0])
    title_payload["site"] = combined_site_name

    title_payload["period_label"] = (
        payload.get("period_label")
        or site_payloads[0].get(
            "period_label",
            "",
        )
    )

    title_payload["generated_by"] = (
        payload.get("generated_by")
        or site_payloads[0].get(
            "generated_by",
            "",
        )
    )

    title_payload["generated_at"] = (
        payload.get("generated_at")
        or site_payloads[0].get(
            "generated_at",
            "",
        )
    )

    prs.core_properties.title = (
        f"HOD Presentation - {combined_site_name}"
    )

    prs.core_properties.subject = (
        "Production, excavator, availability and utilisation performance"
    )

    prs.core_properties.author = (
        title_payload.get("generated_by")
        or "Isambane"
    )

    prs.core_properties.keywords = (
        "production, excavator, BCM, availability, utilisation, HOD"
    )

    _add_title_slide(
        prs,
        title_payload,
    )

    for site_payload in site_payloads:
        _add_executive_summary_slide(
            prs,
            site_payload,
        )

        _add_production_performance_slide(
            prs,
            site_payload,
        )

        _add_excavator_slides(
            prs,
            site_payload,
        )

        _add_au_overview_slide(
            prs,
            site_payload,
        )

        _add_selected_au_slides(
            prs,
            site_payload,
        )

    _apply_footer_numbers(prs)
    prs.save(output)


def _add_title_slide(prs: Presentation, payload: dict) -> None:
    slide = _blank_slide(prs, NAVY)
    availability = payload.get("availability", {})

    _add_rect(slide, 0.0, 0.0, 0.18, SLIDE_HEIGHT, GREEN, GREEN, radius=False)
    _add_rect(slide, 0.65, 1.02, 1.15, 0.10, GREEN, GREEN, radius=False)

    _add_text(
        slide,
        "HOD PRODUCTION PRESENTATION",
        0.65,
        1.30,
        11.9,
        0.70,
        30,
        WHITE,
        bold=True,
        align=PP_ALIGN.LEFT,
    )
    _add_text(
        slide,
        payload.get("site", ""),
        0.65,
        2.16,
        11.9,
        0.68,
        27,
        WHITE,
        bold=True,
        align=PP_ALIGN.LEFT,
    )
    _add_text(
        slide,
        "Production, Excavator, Availability and Utilisation Performance",
        0.65,
        2.94,
        11.9,
        0.42,
        16,
        "D9E2EC",
        align=PP_ALIGN.LEFT,
    )

    _add_rect(slide, 0.65, 3.78, 5.65, 1.06, DARK_NAVY, "2D4268", radius=True)
    _add_text(
        slide,
        "REPORTING PERIOD",
        0.95,
        3.98,
        2.15,
        0.24,
        10,
        "B9C6D5",
        bold=True,
        align=PP_ALIGN.LEFT,
    )
    _add_text(
        slide,
        payload.get("period_label", ""),
        0.95,
        4.25,
        5.00,
        0.34,
        17,
        WHITE,
        bold=True,
        align=PP_ALIGN.LEFT,
    )

    _add_rect(slide, 6.55, 3.78, 5.85, 1.72, DARK_NAVY, "2D4268", radius=True)
    _add_filter_line(
        slide,
        "A&U VIEW",
        availability.get("summary_type", ""),
        6.86,
        3.96,
        5.20,
    )
    _add_filter_line(
        slide,
        "MACHINES",
        availability.get("machine_scope", ""),
        6.86,
        4.42,
        5.20,
    )
    _add_filter_line(
        slide,
        "TARGET MODE",
        availability.get("au_target_filter", ""),
        6.86,
        4.88,
        5.20,
    )

    generated_line = "Generated {0} by {1}".format(
        payload.get("generated_at", ""), payload.get("generated_by", "")
    )
    _add_text(
        slide,
        generated_line,
        0.65,
        6.75,
        11.9,
        0.25,
        9,
        "B9C6D5",
        align=PP_ALIGN.LEFT,
    )


def _add_filter_line(slide, label: str, value: str, x: float, y: float, w: float) -> None:
    _add_text(
        slide,
        label,
        x,
        y,
        1.35,
        0.24,
        8,
        "B9C6D5",
        bold=True,
        align=PP_ALIGN.LEFT,
    )
    _add_text(
        slide,
        value,
        x + 1.45,
        y - 0.01,
        w - 1.45,
        0.27,
        11,
        WHITE,
        bold=True,
        align=PP_ALIGN.LEFT,
    )


def _add_executive_summary_slide(prs: Presentation, payload: dict) -> None:
    slide = _blank_slide(prs, WHITE)
    _add_slide_header(slide, "Executive Summary", payload)

    production = payload.get("production", {})
    excavators = payload.get("excavators", {})
    availability = payload.get("availability", {})

    cards = [
        (
            "ACTUAL BCM",
            _fmt_number(production.get("actual_bcm"), 0),
            BLUE,
            PALE_BLUE,
            "Month-to-date production",
        ),
        (
            "FORECAST VARIANCE",
            _fmt_signed(production.get("forecast_variance_bcm"), 0, " BCM"),
            _variance_colour(production.get("forecast_variance_bcm")),
            _variance_fill(production.get("forecast_variance_bcm")),
            "Forecast less target",
        ),
        (
            "EXCAVATOR HOURS",
            _fmt_number(excavators.get("total_hours"), 1),
            BLUE,
            PALE_BLUE,
            "Valid hours: >0 and <=24",
        ),
        (
            "AVERAGE BCM/H",
            _fmt_number(payload.get("average_bcm_h"), 1),
            GREEN if _num(payload.get("average_bcm_h")) > 0 else RED,
            PALE_GREEN if _num(payload.get("average_bcm_h")) > 0 else PALE_RED,
            "Actual BCM / excavator hours",
        ),
        (
            "AVG AVAILABILITY",
            _fmt_percent_or_nd(availability.get("overall_availability")),
            _status_colour(
                availability.get("overall_availability"),
                availability.get("availability_target", 85),
            ),
            _status_fill(
                availability.get("overall_availability"),
                availability.get("availability_target", 85),
            ),
            "Target line: 85%",
        ),
        (
            "AVG UTILISATION",
            _fmt_percent_or_nd(availability.get("overall_utilisation")),
            _status_colour(
                availability.get("overall_utilisation"),
                availability.get("utilisation_target", 80),
            ),
            _status_fill(
                availability.get("overall_utilisation"),
                availability.get("utilisation_target", 80),
            ),
            "Target line: 80%",
        ),
        (
            "A&U MACHINES",
            _fmt_number(availability.get("machine_count"), 0),
            NAVY,
            LIGHT_BG,
            availability.get("machine_scope", ""),
        ),
        (
            "FORECAST DELIVERY",
            _fmt_number(production.get("forecast_delivery_percent"), 1) + "%",
            GREEN
            if _num(production.get("forecast_delivery_percent")) >= 100
            else ORANGE,
            PALE_GREEN
            if _num(production.get("forecast_delivery_percent")) >= 100
            else PALE_ORANGE,
            "Forecast / monthly target",
        ),
    ]

    positions = []
    card_w = 2.96
    card_h = 2.02
    start_x = 0.45
    gap_x = 0.20
    for row_index, y in enumerate((1.20, 3.73)):
        for col_index in range(4):
            positions.append(
                (start_x + col_index * (card_w + gap_x), y)
            )

    for card, (x, y) in zip(cards, positions):
        _add_kpi_card(
            slide,
            x=x,
            y=y,
            w=card_w,
            h=card_h,
            label=card[0],
            value=card[1],
            accent=card[2],
            fill=card[3],
            note=card[4],
        )


def _add_production_performance_slide(prs: Presentation, payload: dict) -> None:
    slide = _blank_slide(prs, WHITE)
    _add_slide_header(slide, "Production Performance", payload)

    production = payload.get("production", {})
    forecast_variance = production.get("forecast_variance_bcm")

    _add_rect(
        slide,
        0.55,
        1.08,
        12.23,
        0.78,
        _variance_fill(forecast_variance),
        _variance_fill(forecast_variance),
        radius=True,
    )
    _add_text(
        slide,
        "FORECAST VARIANCE",
        0.85,
        1.23,
        3.0,
        0.25,
        11,
        MUTED,
        bold=True,
        align=PP_ALIGN.LEFT,
    )
    _add_text(
        slide,
        _fmt_signed(forecast_variance, 0, " BCM"),
        8.25,
        1.17,
        4.1,
        0.42,
        24,
        _variance_colour(forecast_variance),
        bold=True,
        align=PP_ALIGN.RIGHT,
    )

    metric_pairs = [
        (
            "Monthly target",
            _fmt_number(production.get("monthly_target_bcm"), 0) + " BCM",
            "Forecast",
            _fmt_number(production.get("forecast_bcm"), 0) + " BCM",
        ),
        (
            "Actual BCM",
            _fmt_number(production.get("actual_bcm"), 0) + " BCM",
            "Actual coal",
            _fmt_number(production.get("actual_coal_tons"), 0) + " TONS",
        ),
        (
            "Waste variance",
            _fmt_signed(production.get("waste_variance_bcm"), 0, " BCM"),
            "Coal variance",
            _fmt_signed(production.get("coal_variance_tons"), 0, " TONS"),
        ),
        (
            "Daily required",
            _fmt_number(production.get("daily_required_bcm"), 1) + " BCM",
            "Daily achieved",
            _fmt_number(production.get("daily_achieved_bcm"), 1) + " BCM",
        ),
        (
            "Days worked / left",
            "{0} / {1}".format(
                _fmt_number(production.get("days_worked"), 0),
                _fmt_number(production.get("days_left"), 0),
            ),
            "Strip ratio",
            _fmt_number(production.get("strip_ratio"), 1),
        ),
        (
            "Forecast delivery",
            _fmt_number(production.get("forecast_delivery_percent"), 1) + "%",
            "Monthly plan",
            payload.get("plan_name", ""),
        ),
    ]

    table_shape = slide.shapes.add_table(
        len(metric_pairs),
        4,
        Inches(0.55),
        Inches(2.08),
        Inches(12.23),
        Inches(4.63),
    )
    table = table_shape.table
    table.columns[0].width = Inches(2.25)
    table.columns[1].width = Inches(3.85)
    table.columns[2].width = Inches(2.25)
    table.columns[3].width = Inches(3.88)

    for row_index, pair in enumerate(metric_pairs):
        table.rows[row_index].height = Inches(0.765)
        _style_table_cell(
            table.cell(row_index, 0), pair[0], LIGHT_BG, MUTED, 11, True, PP_ALIGN.LEFT
        )
        _style_table_cell(
            table.cell(row_index, 1),
            pair[1],
            WHITE,
            _metric_value_colour(pair[0], pair[1]),
            15,
            True,
            PP_ALIGN.RIGHT,
        )
        _style_table_cell(
            table.cell(row_index, 2), pair[2], LIGHT_BG, MUTED, 11, True, PP_ALIGN.LEFT
        )
        _style_table_cell(
            table.cell(row_index, 3),
            pair[3],
            WHITE,
            _metric_value_colour(pair[2], pair[3]),
            15,
            True,
            PP_ALIGN.RIGHT,
        )


def _add_excavator_slides(prs: Presentation, payload: dict) -> None:
    excavators = payload.get("excavators", {})
    breakdown = excavators.get("breakdown", []) or []
    rows_per_slide = 8
    chunks = [
        breakdown[index : index + rows_per_slide]
        for index in range(0, len(breakdown), rows_per_slide)
    ]
    if not chunks:
        chunks = [[]]

    total_parts = len(chunks)

    for part_index, chunk in enumerate(chunks, start=1):
        slide = _blank_slide(prs, WHITE)
        title = "Excavator Performance"
        if total_parts > 1:
            title += f" ({part_index}/{total_parts})"
        _add_slide_header(slide, title, payload)

        _add_small_kpi(
            slide,
            0.55,
            1.02,
            2.80,
            "TOTAL VALID HOURS",
            _fmt_number(excavators.get("total_hours"), 1),
            BLUE,
        )
        _add_small_kpi(
            slide,
            3.52,
            1.02,
            2.80,
            "AVERAGE BCM/H",
            _fmt_number(payload.get("average_bcm_h"), 1),
            GREEN if _num(payload.get("average_bcm_h")) > 0 else RED,
        )
        _add_small_kpi(
            slide,
            6.49,
            1.02,
            2.80,
            "EXCAVATORS",
            _fmt_number(excavators.get("excavator_count"), 0),
            NAVY,
        )
        _add_small_kpi(
            slide,
            9.46,
            1.02,
            2.80,
            "EXCLUDED ENTRIES",
            _fmt_number(excavators.get("excluded_entry_count"), 0),
            ORANGE if _num(excavators.get("excluded_entry_count")) > 0 else NAVY,
        )

        if not chunk:
            _add_rect(slide, 0.55, 2.45, 12.23, 2.30, LIGHT_BG, LIGHT_BORDER, radius=True)
            _add_text(
                slide,
                "No valid excavator working hours were found for the selected period.",
                1.10,
                3.15,
                11.10,
                0.70,
                20,
                MUTED,
                bold=True,
                align=PP_ALIGN.CENTER,
            )
        else:
            _add_excavator_table(slide, chunk)

        excluded = int(_num(excavators.get("excluded_entry_count")))
        note_colour = ORANGE if excluded else MUTED
        note = (
            f"{excluded} entries excluded because hours were missing, <=0, or >24."
            if excluded
            else "All collapsed excavator-hour entries passed the validation rules."
        )
        _add_text(
            slide,
            note,
            0.65,
            6.72,
            11.60,
            0.25,
            9,
            note_colour,
            align=PP_ALIGN.LEFT,
        )


def _add_excavator_table(slide, rows: list[dict]) -> None:
    headers = [
        "Excavator",
        "Make / Model",
        "Working Days",
        "Valid Entries",
        "Total Hours",
        "Avg H/Day",
    ]

    table_shape = slide.shapes.add_table(
        len(rows) + 1,
        len(headers),
        Inches(0.55),
        Inches(2.28),
        Inches(12.23),
        Inches(4.15),
    )
    table = table_shape.table
    widths = [2.15, 3.15, 1.45, 1.45, 1.85, 2.18]
    for index, width in enumerate(widths):
        table.columns[index].width = Inches(width)

    table.rows[0].height = Inches(0.48)
    for col_index, header in enumerate(headers):
        _style_table_cell(
            table.cell(0, col_index),
            header,
            NAVY,
            WHITE,
            10,
            True,
            PP_ALIGN.CENTER,
        )

    row_height = max(0.43, min(0.53, 3.55 / max(len(rows), 1)))

    for row_index, item in enumerate(rows, start=1):
        table.rows[row_index].height = Inches(row_height)
        fill = WHITE if row_index % 2 else LIGHT_BG
        values = [
            item.get("asset_name", ""),
            item.get("item_name", ""),
            _fmt_number(item.get("working_days"), 0),
            _fmt_number(item.get("valid_entries"), 0),
            _fmt_number(item.get("total_hours"), 1),
            _fmt_number(item.get("average_hours_per_day"), 1),
        ]

        for col_index, value in enumerate(values):
            alignment = PP_ALIGN.LEFT if col_index < 2 else PP_ALIGN.RIGHT
            _style_table_cell(
                table.cell(row_index, col_index),
                value,
                fill,
                TEXT,
                10,
                col_index in {0, 4},
                alignment,
            )


def _add_au_overview_slide(prs: Presentation, payload: dict) -> None:
    slide = _blank_slide(prs, WHITE)
    _add_slide_header(slide, "Availability & Utilisation Overview", payload)

    availability = payload.get("availability", {})
    categories = availability.get("categories", []) or []
    _add_au_filter_ribbon(slide, availability)

    card_w = 2.34
    card_h = 2.18
    start_x = 0.48
    gap_x = 0.18
    row_ys = (1.53, 4.02)

    for index, category in enumerate(categories[:10]):
        row_index = index // 5
        col_index = index % 5
        x = start_x + col_index * (card_w + gap_x)
        y = row_ys[row_index]
        _add_au_category_card(
            slide,
            x=x,
            y=y,
            w=card_w,
            h=card_h,
            category=category,
            availability_target=availability.get("availability_target", 85),
            utilisation_target=availability.get("utilisation_target", 80),
        )


def _add_au_filter_ribbon(slide, availability: dict) -> None:
    _add_rect(slide, 0.50, 0.84, 12.28, 0.50, LIGHT_BG, LIGHT_BORDER, radius=True)
    ribbon_text = "Summary: {0}   |   Machines: {1}   |   Target Mode: {2}".format(
        availability.get("summary_type", ""),
        availability.get("machine_scope", ""),
        availability.get("au_target_filter", ""),
    )
    _add_text(
        slide,
        ribbon_text,
        0.75,
        0.94,
        11.78,
        0.24,
        10,
        DARK_NAVY,
        bold=True,
        align=PP_ALIGN.LEFT,
    )


def _add_au_category_card(
    slide,
    *,
    x: float,
    y: float,
    w: float,
    h: float,
    category: dict,
    availability_target: float,
    utilisation_target: float,
) -> None:
    _add_rect(slide, x, y, w, h, WHITE, LIGHT_BORDER, radius=True)
    _add_rect(slide, x, y, w, 0.43, NAVY, NAVY, radius=True)
    _add_text(
        slide,
        category.get("title", ""),
        x + 0.12,
        y + 0.07,
        w - 0.24,
        0.25,
        10,
        WHITE,
        bold=True,
        align=PP_ALIGN.CENTER,
    )

    bubble_size = 0.86
    first_x = x + 0.25
    second_x = x + w - bubble_size - 0.25
    bubble_y = y + 0.69

    _add_metric_bubble(
        slide,
        x=first_x,
        y=bubble_y,
        size=bubble_size,
        label="AVAIL.",
        value=category.get("availability"),
        target=availability_target,
    )
    _add_metric_bubble(
        slide,
        x=second_x,
        y=bubble_y,
        size=bubble_size,
        label="UTIL.",
        value=category.get("utilisation"),
        target=utilisation_target,
    )

    _add_text(
        slide,
        "Machines: {0}".format(_fmt_number(category.get("machine_count"), 0)),
        x + 0.18,
        y + 1.76,
        w - 0.36,
        0.23,
        8,
        MUTED,
        bold=True,
        align=PP_ALIGN.CENTER,
    )


def _add_metric_bubble(
    slide,
    *,
    x: float,
    y: float,
    size: float,
    label: str,
    value,
    target: float,
) -> None:
    fill = _status_fill(value, target)
    line = _status_colour(value, target)
    _add_oval(slide, x, y, size, size, fill, line)
    _add_text(
        slide,
        label,
        x + 0.06,
        y + 0.18,
        size - 0.12,
        0.17,
        6.5,
        DARK_GRAY,
        bold=True,
        align=PP_ALIGN.CENTER,
    )
    _add_text(
        slide,
        _fmt_percent_or_nd(value),
        x + 0.04,
        y + 0.42,
        size - 0.08,
        0.24,
        10,
        line,
        bold=True,
        align=PP_ALIGN.CENTER,
    )


def _add_selected_au_slides(prs: Presentation, payload: dict) -> None:
    availability = payload.get("availability", {})
    summary_type = availability.get("summary_type") or "Average Per Machine"

    if summary_type == "Average Per Machine":
        _add_average_per_machine_slides(prs, payload)
        return

    if summary_type == "Daily Summary":
        _add_daily_summary_slides(prs, payload)
        return

    _add_category_summary_chart_slide(prs, payload, summary_type)


def _add_average_per_machine_slides(prs: Presentation, payload: dict) -> None:
    availability = payload.get("availability", {})
    categories = availability.get("categories", []) or []
    machine_series = availability.get("machine_series", {}) or {}
    rows_per_slide = 16
    added = False

    for category in categories:
        category_name = category.get("category")
        machines = machine_series.get(category_name) or []
        if not machines:
            continue

        chunks = [
            machines[index : index + rows_per_slide]
            for index in range(0, len(machines), rows_per_slide)
        ]
        total_parts = len(chunks)

        for part_index, chunk in enumerate(chunks, start=1):
            rows = [
                {
                    "label": row.get("machine", ""),
                    "availability": row.get("availability"),
                    "utilisation": row.get("utilisation"),
                    "is_spare": bool(row.get("is_spare")),
                }
                for row in chunk
            ]
            title = f"{category.get('title', category_name)} Availability & Utilisation"
            if total_parts > 1:
                title += f" ({part_index}/{total_parts})"

            _add_grouped_column_chart_slide(
                prs,
                payload,
                title=title,
                rows=rows,
                subtitle="Average Per Machine",
                average_availability=category.get("availability"),
                average_utilisation=category.get("utilisation"),
                show_values=True,
                show_spare_legend=True,
            )
            added = True

    if not added:
        _add_no_au_data_slide(prs, payload, "Average Per Machine")


def _add_daily_summary_slides(prs: Presentation, payload: dict) -> None:
    availability = payload.get("availability", {})
    categories = availability.get("categories", []) or []
    daily_series = availability.get("daily_series", {}) or {}
    added = False

    for category in categories:
        category_name = category.get("category")
        values = daily_series.get(category_name) or []
        if not values:
            continue

        has_data = any(
            row.get("availability") is not None or row.get("utilisation") is not None
            for row in values
        )
        if not has_data:
            continue

        rows = [
            {
                "label": row.get("day") or str(row.get("date", ""))[-2:],
                "availability": row.get("availability"),
                "utilisation": row.get("utilisation"),
                "is_spare": False,
            }
            for row in values
        ]

        _add_grouped_column_chart_slide(
            prs,
            payload,
            title=f"{category.get('title', category_name)} Daily Availability & Utilisation",
            rows=rows,
            subtitle="Daily Summary - day of month",
            average_availability=category.get("availability"),
            average_utilisation=category.get("utilisation"),
            show_values=len(rows) <= 14,
            show_spare_legend=False,
        )
        added = True

    if not added:
        _add_no_au_data_slide(prs, payload, "Daily Summary")


def _add_category_summary_chart_slide(
    prs: Presentation, payload: dict, summary_type: str
) -> None:
    availability = payload.get("availability", {})
    rows = []

    for category in availability.get("categories", []) or []:
        if (
            category.get("availability") is None
            and category.get("utilisation") is None
        ):
            continue
        rows.append(
            {
                "label": _short_category_label(category.get("category", "")),
                "availability": category.get("availability"),
                "utilisation": category.get("utilisation"),
                "is_spare": False,
            }
        )

    if not rows:
        _add_no_au_data_slide(prs, payload, summary_type)
        return

    _add_grouped_column_chart_slide(
        prs,
        payload,
        title=f"{summary_type} - Availability & Utilisation",
        rows=rows,
        subtitle="Category Average",
        average_availability=availability.get("overall_availability"),
        average_utilisation=availability.get("overall_utilisation"),
        show_values=True,
        show_spare_legend=False,
    )


def _add_grouped_column_chart_slide(
    prs: Presentation,
    payload: dict,
    *,
    title: str,
    rows: list[dict],
    subtitle: str,
    average_availability,
    average_utilisation,
    show_values: bool,
    show_spare_legend: bool,
) -> None:
    slide = _blank_slide(prs, WHITE)
    _add_slide_header(slide, title, payload)
    availability = payload.get("availability", {})

    filter_text = "{0} | {1} | {2}".format(
        subtitle,
        availability.get("machine_scope", ""),
        availability.get("au_target_filter", ""),
    )
    _add_text(
        slide,
        filter_text,
        0.58,
        0.86,
        7.25,
        0.28,
        10,
        MUTED,
        bold=True,
        align=PP_ALIGN.LEFT,
    )

    _add_compact_metric(
        slide,
        x=8.17,
        y=0.82,
        w=2.03,
        label="AVG AVAIL.",
        value=average_availability,
        target=availability.get("availability_target", 85),
    )
    _add_compact_metric(
        slide,
        x=10.35,
        y=0.82,
        w=2.03,
        label="AVG UTIL.",
        value=average_utilisation,
        target=availability.get("utilisation_target", 80),
    )

    _add_chart_legend(slide, show_spare_legend=show_spare_legend)
    _draw_grouped_column_chart(
        slide,
        rows,
        availability_target=_num(availability.get("availability_target")) or 85,
        utilisation_target=_num(availability.get("utilisation_target")) or 80,
        show_values=show_values,
    )


def _add_compact_metric(
    slide,
    *,
    x: float,
    y: float,
    w: float,
    label: str,
    value,
    target: float,
) -> None:
    fill = _status_fill(value, target)
    colour = _status_colour(value, target)
    _add_rect(slide, x, y, w, 0.48, fill, colour, radius=True)
    _add_text(
        slide,
        label,
        x + 0.10,
        y + 0.08,
        0.90,
        0.22,
        7.5,
        MUTED,
        bold=True,
        align=PP_ALIGN.LEFT,
    )
    _add_text(
        slide,
        _fmt_percent_or_nd(value),
        x + 0.95,
        y + 0.06,
        w - 1.05,
        0.25,
        12,
        colour,
        bold=True,
        align=PP_ALIGN.RIGHT,
    )


def _add_chart_legend(slide, *, show_spare_legend: bool) -> None:
    y = 1.30
    _add_rect(slide, 0.76, y, 0.19, 0.13, AVAIL_BAR, AVAIL_BAR, radius=False)
    _add_text(slide, "Availability", 1.00, y - 0.03, 1.10, 0.20, 8, TEXT, bold=True)
    _add_rect(slide, 2.16, y, 0.19, 0.13, UTIL_BAR, UTIL_BAR, radius=False)
    _add_text(slide, "Utilisation", 2.40, y - 0.03, 1.05, 0.20, 8, TEXT, bold=True)
    _add_rect(slide, 3.55, y + 0.05, 0.28, 0.025, AVAIL_TARGET_LINE, AVAIL_TARGET_LINE, radius=False)
    _add_text(slide, "Availability target 85%", 3.89, y - 0.03, 1.75, 0.20, 8, TEXT)
    _add_rect(slide, 5.74, y + 0.05, 0.28, 0.025, UTIL_TARGET_LINE, UTIL_TARGET_LINE, radius=False)
    _add_text(slide, "Utilisation target 80%", 6.08, y - 0.03, 1.70, 0.20, 8, TEXT)

    if show_spare_legend:
        _add_text(
            slide,
            "Purple label = Swing/Spare",
            9.72,
            y - 0.03,
            2.60,
            0.20,
            8,
            SPARE_PURPLE_DARK,
            bold=True,
            align=PP_ALIGN.RIGHT,
        )


def _draw_grouped_column_chart(
    slide,
    rows: list[dict],
    *,
    availability_target: float,
    utilisation_target: float,
    show_values: bool,
) -> None:
    plot_x = 1.05
    plot_y = 1.72
    plot_w = 11.60
    plot_h = 4.75
    base_y = plot_y + plot_h

    # Grid and Y-axis labels.
    for tick in range(0, 101, 10):
        y = plot_y + plot_h - (tick / 100.0) * plot_h
        line_colour = "BBC5D0" if tick in {0, 100} else "E4E9EF"
        _add_rect(slide, plot_x, y, plot_w, 0.008, line_colour, line_colour, radius=False)
        _add_text(
            slide,
            f"{tick}%",
            0.45,
            y - 0.10,
            0.48,
            0.20,
            7,
            MUTED,
            bold=tick in {0, 100},
            align=PP_ALIGN.RIGHT,
        )

    avail_line_y = plot_y + plot_h - (availability_target / 100.0) * plot_h
    util_line_y = plot_y + plot_h - (utilisation_target / 100.0) * plot_h
    _add_rect(
        slide,
        plot_x,
        avail_line_y,
        plot_w,
        0.028,
        AVAIL_TARGET_LINE,
        AVAIL_TARGET_LINE,
        radius=False,
    )
    _add_rect(
        slide,
        plot_x,
        util_line_y,
        plot_w,
        0.028,
        UTIL_TARGET_LINE,
        UTIL_TARGET_LINE,
        radius=False,
    )

    if not rows:
        _add_text(
            slide,
            "No availability and utilisation data found.",
            plot_x,
            plot_y + 1.85,
            plot_w,
            0.55,
            18,
            MUTED,
            bold=True,
            align=PP_ALIGN.CENTER,
        )
        return

    count = len(rows)
    group_w = plot_w / max(count, 1)
    bar_w = min(0.23, max(0.055, group_w * 0.28))
    bar_gap = min(0.07, max(0.018, group_w * 0.08))
    label_size = 7.5 if count <= 16 else 5.8
    value_size = 7 if count <= 12 else 5.5

    for index, row in enumerate(rows):
        group_left = plot_x + index * group_w
        center_x = group_left + group_w / 2
        avail_x = center_x - bar_w - bar_gap / 2
        util_x = center_x + bar_gap / 2

        avail = _percent(row.get("availability"))
        util = _percent(row.get("utilisation"))
        avail_h = plot_h * (avail / 100.0) if avail is not None else 0.0
        util_h = plot_h * (util / 100.0) if util is not None else 0.0

        if avail is not None:
            _add_rect(
                slide,
                avail_x,
                base_y - max(avail_h, 0.02),
                bar_w,
                max(avail_h, 0.02),
                AVAIL_BAR,
                AVAIL_BAR,
                radius=False,
            )
        if util is not None:
            _add_rect(
                slide,
                util_x,
                base_y - max(util_h, 0.02),
                bar_w,
                max(util_h, 0.02),
                UTIL_BAR,
                UTIL_BAR,
                radius=False,
            )

        if show_values and avail is not None:
            _add_text(
                slide,
                f"{avail:.1f}",
                avail_x - 0.08,
                base_y - avail_h - 0.21,
                bar_w + 0.16,
                0.17,
                value_size,
                DARK_GRAY,
                bold=True,
                align=PP_ALIGN.CENTER,
            )
        if show_values and util is not None:
            _add_text(
                slide,
                f"{util:.1f}",
                util_x - 0.08,
                base_y - util_h - 0.21,
                bar_w + 0.16,
                0.17,
                value_size,
                DARK_GRAY,
                bold=True,
                align=PP_ALIGN.CENTER,
            )

        label = _truncate_label(row.get("label", ""), 13 if count <= 16 else 5)
        label_colour = SPARE_PURPLE_DARK if row.get("is_spare") else TEXT
        label_y = base_y + 0.06 + (0.15 if count > 18 and index % 2 else 0.0)
        _add_text(
            slide,
            label,
            group_left,
            label_y,
            group_w,
            0.38,
            label_size,
            label_colour,
            bold=True,
            align=PP_ALIGN.CENTER,
        )


def _add_no_au_data_slide(prs: Presentation, payload: dict, summary_type: str) -> None:
    slide = _blank_slide(prs, WHITE)
    _add_slide_header(slide, f"{summary_type} - Availability & Utilisation", payload)
    _add_rect(slide, 0.75, 1.55, 11.83, 3.90, LIGHT_BG, LIGHT_BORDER, radius=True)
    _add_text(
        slide,
        "No availability and utilisation data was returned for the selected filters.",
        1.20,
        2.78,
        10.95,
        0.82,
        20,
        MUTED,
        bold=True,
        align=PP_ALIGN.CENTER,
    )


def _blank_slide(prs: Presentation, colour: str):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(colour)
    return slide


def _add_slide_header(slide, title: str, payload: dict) -> None:
    _add_rect(slide, 0.0, 0.0, SLIDE_WIDTH, 0.67, NAVY, NAVY, radius=False)
    _add_rect(slide, 0.0, 0.0, 0.13, 0.67, GREEN, GREEN, radius=False)
    _add_text(
        slide,
        title,
        0.48,
        0.13,
        8.40,
        0.36,
        22,
        WHITE,
        bold=True,
        align=PP_ALIGN.LEFT,
    )
    _add_text(
        slide,
        payload.get("site", ""),
        9.10,
        0.13,
        3.70,
        0.34,
        13,
        WHITE,
        bold=True,
        align=PP_ALIGN.RIGHT,
    )


def _apply_footer_numbers(prs: Presentation) -> None:
    total = len(prs.slides)
    for index, slide in enumerate(prs.slides, start=1):
        if index == 1:
            continue
        _add_text(
            slide,
            f"HOD Presentation  |  {index} of {total}",
            10.15,
            7.10,
            2.62,
            0.18,
            8,
            MUTED,
            align=PP_ALIGN.RIGHT,
        )


def _add_kpi_card(
    slide,
    *,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    value: str,
    accent: str,
    fill: str,
    note: str,
) -> None:
    _add_rect(slide, x, y, w, h, fill, LIGHT_BORDER, radius=True)
    _add_rect(slide, x, y, 0.09, h, accent, accent, radius=False)
    _add_text(
        slide,
        label,
        x + 0.24,
        y + 0.22,
        w - 0.42,
        0.26,
        9,
        MUTED,
        bold=True,
        align=PP_ALIGN.LEFT,
    )
    _add_text(
        slide,
        value,
        x + 0.24,
        y + 0.62,
        w - 0.42,
        0.54,
        22,
        accent,
        bold=True,
        align=PP_ALIGN.LEFT,
    )
    _add_text(
        slide,
        note,
        x + 0.24,
        y + 1.57,
        w - 0.42,
        0.22,
        7.5,
        MUTED,
        align=PP_ALIGN.LEFT,
    )


def _add_small_kpi(
    slide,
    x: float,
    y: float,
    w: float,
    label: str,
    value: str,
    accent: str,
) -> None:
    _add_rect(slide, x, y, w, 0.96, WHITE, LIGHT_BORDER, radius=True)
    _add_rect(slide, x, y, 0.08, 0.96, accent, accent, radius=False)
    _add_text(
        slide,
        label,
        x + 0.24,
        y + 0.14,
        w - 0.42,
        0.20,
        8,
        MUTED,
        bold=True,
        align=PP_ALIGN.LEFT,
    )
    _add_text(
        slide,
        value,
        x + 0.24,
        y + 0.42,
        w - 0.42,
        0.34,
        19,
        accent,
        bold=True,
        align=PP_ALIGN.LEFT,
    )


def _add_rect(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    fill_colour: str,
    line_colour: str,
    *,
    radius: bool,
):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(
        shape_type, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill_colour)
    shape.line.color.rgb = _rgb(line_colour)
    shape.line.width = Pt(0.8)
    return shape


def _add_oval(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    fill_colour: str,
    line_colour: str,
):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill_colour)
    shape.line.color.rgb = _rgb(line_colour)
    shape.line.width = Pt(1.0)
    return shape


def _add_text(
    slide,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    font_size: float,
    colour: str,
    *,
    bold: bool = False,
    align=PP_ALIGN.LEFT,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame.margin_left = Inches(0.02)
    frame.margin_right = Inches(0.02)
    frame.margin_top = Inches(0.01)
    frame.margin_bottom = Inches(0.01)

    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.space_before = Pt(0)
    paragraph.space_after = Pt(0)

    run = paragraph.add_run()
    run.text = str(text or "")
    run.font.name = FONT_NAME
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(colour)
    return box


def _style_table_cell(
    cell,
    text: str,
    fill_colour: str,
    font_colour: str,
    font_size: float,
    bold: bool,
    align,
) -> None:
    cell.fill.solid()
    cell.fill.fore_color.rgb = _rgb(fill_colour)
    cell.margin_left = Inches(0.08)
    cell.margin_right = Inches(0.08)
    cell.margin_top = Inches(0.03)
    cell.margin_bottom = Inches(0.03)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE

    frame = cell.text_frame
    frame.clear()
    frame.word_wrap = True
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.space_before = Pt(0)
    paragraph.space_after = Pt(0)
    run = paragraph.add_run()
    run.text = str(text or "")
    run.font.name = FONT_NAME
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(font_colour)


def _metric_value_colour(label: str, value: str) -> str:
    normalised = label.lower()
    if "variance" in normalised:
        return GREEN if not str(value).strip().startswith("-") else RED
    return TEXT


def _variance_colour(value) -> str:
    return GREEN if _num(value) >= 0 else RED


def _variance_fill(value) -> str:
    return PALE_GREEN if _num(value) >= 0 else PALE_RED


def _status_colour(value, target: float) -> str:
    if value is None:
        return MUTED
    return GREEN if _num(value) >= _num(target) else RED


def _status_fill(value, target: float) -> str:
    if value is None:
        return LIGHT_BG
    return PALE_GREEN if _num(value) >= _num(target) else PALE_RED


def _fmt_number(value, decimals: int = 0) -> str:
    number = _num(value)
    return f"{number:,.{decimals}f}"


def _fmt_percent_or_nd(value) -> str:
    if value is None:
        return "N/D"
    return f"{_num(value):.1f}%"


def _fmt_signed(value, decimals: int = 0, suffix: str = "") -> str:
    number = _num(value)
    sign = "+" if number >= 0 else "-"
    return f"{sign}{abs(number):,.{decimals}f}{suffix}"


def _percent(value):
    if value is None:
        return None
    return max(0.0, min(100.0, _num(value)))


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _truncate_label(value, maximum: int) -> str:
    text = str(value or "")
    if len(text) <= maximum:
        return text
    return text[: max(1, maximum - 1)] + "..."


def _short_category_label(value: str) -> str:
    mapping = {
        "Service Truck": "SERV TRK",
        "Water Bowser": "WATER",
        "Diesel Bowsers": "DIESEL",
        "Excavator": "EXCAV",
    }
    return mapping.get(value, str(value or "").upper())


def _rgb(hex_colour: str) -> RGBColor:
    hex_colour = hex_colour.strip().lstrip("#")
    return RGBColor(
        int(hex_colour[0:2], 16),
        int(hex_colour[2:4], 16),
        int(hex_colour[4:6], 16),
    )
