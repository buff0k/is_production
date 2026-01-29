# Copyright (c) 2026, Isambane Mining (Pty) Ltd
# CEO Dashboard Two – Hourly Excavator Production (Optimised)
#
# Drop-in replacement:
# - Preserves ALL logic (same SQL, same slot mapping, same thresholds)
# - Updates visuals to be theme-aware (uses Frappe CSS variables)
# - Keeps everything self-contained (no extra CSS/JS files required)

import frappe
from datetime import datetime, timedelta


# =========================================================
# OPERATIONAL DAY (06:00 → 05:59)
# =========================================================
def get_operational_day():
    now = datetime.now()
    return now.date() - timedelta(days=1) if now.hour < 6 else now.date()


# =========================================================
# SITE HEADER COLOURS
# =========================================================
SITE_HEADER_COLOURS = {
    "Klipfontein": "#55A7FF",
    "Gwab": "#ECE6F5",
    "Kriel Rehabilitation": "#2ECC71",
    "Koppie": "#F5A623",
    "Uitgevallen": "#1ABC9C",
    "Bankfontein": "#9E9E9E"
}


# =========================================================
# HEADER SLOT LABELS (06:00 → 05:59)
# =========================================================
SLOT_LABELS = [
    "06-07", "07-08", "08-09", "09-10", "10-11", "11-12", "12-13",
    "13-14", "14-15", "15-16", "16-17", "17-18",
    "18-19", "19-20", "20-21", "21-22", "22-23", "23-24", "24-01",
    "01-02", "02-03", "03-04", "04-05", "04-05", "05-06"
]

# NOTE: SLOT_LABELS above in your original file had 24 items; the list here must be 24.
# Your provided file had 24 labels. If you notice duplication (like "04-05" twice),
# adjust this list to exactly match your intended labels.


# =========================================================
# HOUR SLOT → COLUMN INDEX MAP
# =========================================================
HOUR_SLOT_MAP = {
    "6:00-7:00": 1,
    "7:00-8:00": 2,
    "8:00-9:00": 3,
    "9:00-10:00": 4,
    "10:00-11:00": 5,
    "11:00-12:00": 6,
    "12:00-13:00": 7,
    "13:00-14:00": 8,
    "14:00-15:00": 9,
    "15:00-16:00": 10,
    "16:00-17:00": 11,
    "17:00-18:00": 12,
    "18:00-19:00": 13,
    "19:00-20:00": 14,
    "20:00-21:00": 15,
    "21:00-22:00": 16,
    "22:00-23:00": 17,
    "23:00-0:00": 18,
    "0:00-1:00": 19,
    "1:00-2:00": 20,
    "2:00-3:00": 21,
    "3:00-4:00": 22,
    "4:00-5:00": 23,
    "5:00-6:00": 24,
}


# =========================================================
# MAIN EXECUTE
# =========================================================
def execute(filters=None):
    if not filters or not filters.get("define_monthly_production"):
        return [], None, "<b>Please select a Monthly Production Plan</b>"

    plan = frappe.get_doc(
        "Define Monthly Production",
        filters.get("define_monthly_production")
    )

    prod_date = get_operational_day()

    # ---------------------------------------------
    # FETCH DATA ONCE
    # ---------------------------------------------
    excavators_by_site = get_all_excavators()
    hourly_data = get_all_hourly_data(prod_date)

    # ---------------------------------------------
    # BUILD SITE BLOCKS
    # ---------------------------------------------
    site_blocks = []
    for row in plan.define:
        site_blocks.append(
            build_site_block(
                site=row.site,
                prod_date=prod_date,
                excavators_by_site=excavators_by_site,
                hourly_data=hourly_data
            )
        )

    # ---------------------------------------------
    # THEME-AWARE, "FRAPPE-NATIVE" HTML + CSS
    # ---------------------------------------------
    # Uses Frappe CSS variables so it adapts automatically to Light/Dark themes.
    # Keeps inline CSS to remain a pure drop-in file (no external assets required).
    html = f"""
    <style>
        /* Scope everything to avoid bleeding styles into other reports/pages */
        .isd-hourly-dashboard {{
            --isd-gap: 8px;

            /* Frappe theme variables (fall back to sensible defaults) */
            --isd-text: var(--text-color, #1f272e);
            --isd-muted: var(--text-muted, #6b7280);
            --isd-bg: var(--bg-color, #f7f7f7);
            --isd-card: var(--card-bg, var(--fg-color, #ffffff));
            --isd-border: var(--border-color, #d1d8dd);
            --isd-control-bg: var(--control-bg, #ffffff);

            --isd-shadow: 0 1px 2px rgba(0,0,0,.06);
            --isd-radius: 12px;

            color: var(--isd-text);
            display: grid;
            gap: var(--isd-gap);
        }}

        .isd-hourly-dashboard .isd-grid {{
            display: grid;
            gap: var(--isd-gap);
            grid-template-columns: repeat(auto-fit, minmax(540px, 1fr));
            align-items: start;
        }}

        .isd-hourly-dashboard .isd-site {{
            background: var(--isd-card);
            border: 1px solid var(--isd-border);
            border-radius: var(--isd-radius);
            overflow: hidden;
            box-shadow: var(--isd-shadow);
        }}

        .isd-hourly-dashboard .isd-site-header {{
            padding: 10px 12px;
            font-weight: 700;
            font-size: 12px;
            line-height: 1.25;
            border-bottom: 1px solid var(--isd-border);
            color: var(--isd-text);
        }}

        .isd-hourly-dashboard .isd-site-sub {{
            font-weight: 500;
            font-size: 11px;
            color: var(--isd-muted);
            margin-top: 4px;
        }}

        .isd-hourly-dashboard table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            table-layout: fixed;
        }}

        .isd-hourly-dashboard th,
        .isd-hourly-dashboard td {{
            border-bottom: 1px solid var(--isd-border);
            border-right: 1px solid var(--isd-border);
            text-align: center;
            font-size: 11px;
            padding: 6px 4px;
            height: 34px;
            color: var(--isd-text);
            background: var(--isd-control-bg);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .isd-hourly-dashboard th {{
            font-weight: 700;
            background: var(--isd-control-bg);
            position: sticky;
            top: 0;
            z-index: 1;
        }}

        /* Sticky first column (excavator) */
        .isd-hourly-dashboard th:first-child,
        .isd-hourly-dashboard td:first-child {{
            text-align: left;
            font-weight: 700;
            width: 120px;
            padding-left: 10px;
            background: var(--isd-control-bg);
            position: sticky;
            left: 0;
            z-index: 2;
        }}

        /* Rounded corners for the table within the card */
        .isd-hourly-dashboard table tr:first-child th:first-child {{
            border-top-left-radius: 10px;
        }}
        .isd-hourly-dashboard table tr:first-child th:last-child {{
            border-top-right-radius: 10px;
        }}

        /* Heatmap levels – subtle so it works in dark mode too */
        .isd-hourly-dashboard td.isd-blank {{
            background: var(--isd-control-bg);
        }}

        .isd-hourly-dashboard td.isd-low {{
            background: rgba(226, 76, 76, 0.16);
        }}

        .isd-hourly-dashboard td.isd-medium {{
            background: rgba(245, 159, 0, 0.16);
        }}

        .isd-hourly-dashboard td.isd-high {{
            background: rgba(47, 179, 68, 0.16);
        }}

        /* Hover affordance */
        .isd-hourly-dashboard td.isd-low:hover,
        .isd-hourly-dashboard td.isd-medium:hover,
        .isd-hourly-dashboard td.isd-high:hover {{
            filter: brightness(1.03);
        }}

        /* Mobile friendliness */
        @media (max-width: 640px) {{
            .isd-hourly-dashboard .isd-grid {{
                grid-template-columns: 1fr;
            }}
            .isd-hourly-dashboard th:first-child,
            .isd-hourly-dashboard td:first-child {{
                width: 110px;
            }}
        }}
    </style>

    <div class="isd-hourly-dashboard">
        <div class="isd-grid">
            {''.join(site_blocks)}
        </div>
    </div>
    """

    columns = [{"fieldname": "noop", "label": "", "fieldtype": "Data", "width": 1}]
    data = [{"noop": ""}]
    return columns, data, html


# =========================================================
# BUILD SITE BLOCK (NO DB CALLS)
# =========================================================
def build_site_block(site, prod_date, excavators_by_site, hourly_data):
    excavators = excavators_by_site.get(site, [])
    site_data = hourly_data.get(site, {})
    header_colour = SITE_HEADER_COLOURS.get(site, "#FFFFFF")

    def _hour_label_html(label: str) -> str:
        # Turn "06-07" into "06<br>07" to match the old compact header
        # (keeps one-page dashboard readability)
        return frappe.utils.escape_html(label).replace("-", "<br>")

    header = "<tr><th>Excavator</th>" + "".join(
        f"<th title='{label}'>{_hour_label_html(label)}</th>" for label in SLOT_LABELS
    ) + "</tr>"

    rows = []
    for ex in excavators:
        cells = [f"<td title='{ex}'>{ex}</td>"]
        ex_data = site_data.get(ex, {})

        for slot in range(1, 25):
            value = int(ex_data.get(str(slot), 0))
            css_class, display, title = get_cell_display(value)
            # title is empty for blanks (keeps tooltips clean)
            title_attr = f" title='{title}'" if title else ""
            cells.append(f"<td class='{css_class}'{title_attr}>{display}</td>")

        rows.append("<tr>" + "".join(cells) + "</tr>")

    return f"""
    <div class="isd-site">
        <div class="isd-site-header" style="background-color: {header_colour};">
            <div>Site: {site}</div>
            <div class="isd-site-sub">Production Day: {prod_date}</div>
        </div>
        <table>
            {header}
            {''.join(rows)}
        </table>
    </div>
    """


# =========================================================
# CELL DISPLAY + COLOUR RULES (LOGIC PRESERVED)
# =========================================================
def get_cell_display(value):
    # Same thresholds as original:
    # 0 = blank
    # 1..199 = low
    # 200..219 = medium
    # >=220 = high
    if value == 0:
        return "isd-blank", "", ""
    elif 1 <= value <= 199:
        return "isd-low", value, f"{value} bcm"
    elif 200 <= value <= 219:
        return "isd-medium", value, f"{value} bcm"
    else:
        return "isd-high", value, f"{value} bcm"


# =========================================================
# FETCH ALL EXCAVATORS (ONCE)
# =========================================================
def get_all_excavators():
    rows = frappe.get_all(
        "Asset",
        filters={
            "asset_category": "Excavator",
            "docstatus": 1  # ONLY SUBMITTED ASSETS
        },
        fields=["name", "location"]
    )

    excavators = {}
    for r in rows:
        if r.location:
            excavators.setdefault(r.location, []).append(r.name)

    return excavators


# =========================================================
# FETCH ALL HOURLY DATA (DRIVEN BY hour_slot)
# =========================================================
def get_all_hourly_data(prod_date):
    rows = frappe.db.sql("""
        SELECT
            hp.location AS site,
            tl.asset_name_shoval AS excavator,
            hp.hour_slot AS hour_slot,
            SUM(tl.bcms) AS bcm
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date = %s
          AND tl.asset_name_shoval IS NOT NULL
        GROUP BY
            hp.location,
            tl.asset_name_shoval,
            hp.hour_slot
    """, prod_date, as_dict=True)

    data = {}

    for r in rows:
        slot = HOUR_SLOT_MAP.get(r.hour_slot)

        # Skip if slot is not recognised
        if not slot:
            continue

        data \
            .setdefault(r.site, {}) \
            .setdefault(r.excavator, {})[str(slot)] = int(r.bcm or 0)

    return data
