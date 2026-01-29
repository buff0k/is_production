import frappe
from frappe.utils import getdate, nowdate
from datetime import timedelta

# =========================================================
# CONSTANTS
# =========================================================
Y_AXIS_STEP = 10_000

SITE_COLORS = {
    "Klipfontein": "#55A7FF",
    "Gwab": "#ECE6F5",
    "Kriel Rehabilitation": "#2ECC71",
    "Koppie": "#F5A623",
    "Uitgevallen": "#1ABC9C",
    "Bankfontein": "#9E9E9E",
}

TARGET_LINE_COLOR = "#9E9E9E"
ACTUAL_LINE_COLOR = "#0B2C4D"


# =========================================================
# MAIN EXECUTE
# =========================================================
def execute(filters=None):
    # Always return at least 1 column + 1 row so Frappe (v16) doesn't show "Nothing to show"
    columns = [{"fieldname": "noop", "label": "", "fieldtype": "Data", "width": 1}]
    data = [{"noop": ""}]

    if not filters or not filters.get("monthly_production_plan"):
        return columns, data, "<b>Please select a Monthly Production Plan.</b>"

    yesterday = getdate(nowdate()) - timedelta(days=1)

    dmp = frappe.get_doc(
        "Define Monthly Production",
        filters.get("monthly_production_plan")
    )

    mpp_map = get_monthly_plans(dmp.define)
    site_blocks = []

    for row in dmp.define:
        mpp = mpp_map.get(row.site)
        if not mpp:
            continue

        prod_start = getdate(mpp.prod_month_start_date)
        prod_end = getdate(mpp.prod_month_end_date)

        actual_map = extract_actuals_mtd(
            mpp.month_prod_days,
            prod_start,
            prod_end,
            yesterday
        )

        site_blocks.append(
            build_site_block(
                site=row.site,
                prod_start=prod_start,
                prod_end=prod_end,
                monthly_target=mpp.monthly_target_bcm,
                actual_map=actual_map,
                yesterday=yesterday
            )
        )

    # Theme-aware, scoped styling (no bleed into other pages)
    html = f"""
    <style>
        .isd-ceo-graphs {{
            --isd-gap: 14px;

            /* Frappe theme vars with fallbacks */
            --isd-text: var(--text-color, #1f272e);
            --isd-muted: var(--text-muted, #6b7280);
            --isd-bg: var(--bg-color, #f7f7f7);
            --isd-card: var(--card-bg, var(--fg-color, #ffffff));
            --isd-border: var(--border-color, #d1d8dd);
            --isd-control-bg: var(--control-bg, #ffffff);

            --isd-shadow: 0 1px 2px rgba(0,0,0,.06);
            --isd-radius: 12px;

            color: var(--isd-text);
        }}

        .isd-ceo-graphs .isd-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: var(--isd-gap);
            padding: 14px;
            align-items: start;
        }}

        /* Cards */
        .isd-ceo-graphs .isd-card {{
            background: var(--isd-card);
            border: 1px solid var(--isd-border);
            border-radius: var(--isd-radius);
            overflow: hidden;
            box-shadow: var(--isd-shadow);
            height: 420px;
            display: flex;
            flex-direction: column;
        }}

        /* Header/Banner (keeps your site colour but makes text theme-friendly) */
        .isd-ceo-graphs .isd-banner {{
            padding: 10px 14px;
            font-weight: 800;
            font-size: 12px;
            line-height: 1.35;
            color: var(--isd-text);
            border-bottom: 1px solid var(--isd-border);
        }}

        .isd-ceo-graphs .isd-banner .isd-sub {{
            font-weight: 600;
            font-size: 11px;
            color: var(--isd-muted);
            margin-top: 4px;
        }}

        /* Chart area */
        .isd-ceo-graphs .isd-chart {{
            flex: 1;
            padding: 12px 14px 14px 14px;
            background: transparent;
        }}

        .isd-ceo-graphs .isd-chart canvas {{
            width: 100% !important;
            height: 100% !important;
        }}

        /* Responsive: 1 column on smaller widths */
        @media (max-width: 1200px) {{
            .isd-ceo-graphs .isd-grid {{
                grid-template-columns: 1fr;
            }}
            .isd-ceo-graphs .isd-card {{
                height: 380px;
            }}
        }}
    </style>

    <div class="isd-ceo-graphs">
        <div class="isd-grid">
            {''.join(site_blocks)}
        </div>
    </div>
    """

    return columns, data, html


# =========================================================
# SITE BLOCK
# =========================================================
def build_site_block(site, prod_start, prod_end, monthly_target, actual_map, yesterday):
    labels, dates = build_date_axis(prod_start, prod_end)

    target = build_mtd_target(monthly_target, len(labels))
    actual = build_mtd_actual(dates, actual_map, yesterday)

    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "MTD Target",
                    "data": target,
                    "borderColor": TARGET_LINE_COLOR,
                    "borderWidth": 2,
                    "tension": 0.25,
                    "pointRadius": 3,
                    "pointBorderWidth": 1,
                },
                {
                    "label": "MTD Actual",
                    "data": actual,
                    "borderColor": ACTUAL_LINE_COLOR,
                    "borderWidth": 2,
                    "tension": 0.25,
                    "pointRadius": 3,
                    "pointBorderWidth": 1,
                    "spanGaps": False,
                },
            ],
        },
        "options": {
            "animation": False,
            "maintainAspectRatio": False,
            "layout": {
                "padding": {
                    "left": 10,
                    "right": 10,
                    "top": 10,
                    "bottom": 10,
                }
            },
            "plugins": {
                "legend": {"display": False}
            },
            "scales": {
                "x": {
                    "ticks": {
                        "autoSkip": True,
                        "font": {"size": 11},
                    }
                },
                "y": {
                    "beginAtZero": True,
                    "ticks": {
                        "stepSize": Y_AXIS_STEP,
                        "font": {"size": 11},
                    }
                },
            },
        },
    }

    banner_bg = SITE_COLORS.get(site) or "#e5e7eb"

    return f"""
    <div class="isd-card">
        <div class="isd-banner" style="background:{banner_bg}">
            <div>Site: {site}</div>
            <div class="isd-sub">
                Production Period: {prod_start} → {prod_end}<br>
                MTD up to: {yesterday}
            </div>
        </div>

        <div class="isd-chart">
            <canvas data-chart='{frappe.as_json(chart_config)}'></canvas>
        </div>
    </div>
    """


# =========================================================
# ACTUALS (MTD)
# =========================================================
def extract_actuals_mtd(rows, prod_start, prod_end, cutoff):
    actuals = {}

    for r in rows:
        if not r.shift_start_date:
            continue

        d = getdate(r.shift_start_date)

        if d < prod_start or d > prod_end or d > cutoff:
            continue

        actuals[d] = round(
            (r.cum_ts_bcms or 0) + (r.tot_cumulative_dozing_bcms or 0),
            2,
        )

    return actuals


def build_mtd_actual(dates, actual_map, cutoff):
    return [None if d > cutoff else actual_map.get(d) for d in dates]


# =========================================================
# TARGET (MTD)
# =========================================================
def build_mtd_target(monthly_target, days):
    daily = monthly_target / days if days else 0
    total = 0
    return [round((total := total + daily), 2) for _ in range(days)]


# =========================================================
# HELPERS
# =========================================================
def build_date_axis(start, end):
    labels, dates = [], []
    cur = start
    while cur <= end:
        labels.append(str(cur.day))
        dates.append(cur)
        cur += timedelta(days=1)
    return labels, dates


def get_monthly_plans(rows):
    plans = {}
    for r in rows:
        name = frappe.db.get_value(
            "Monthly Production Planning",
            {
                "location": r.site,
                "prod_month_start_date": ["<=", r.end_date],
                "prod_month_end_date": [">=", r.start_date],
            },
            "name",
        )
        if name:
            plans[r.site] = frappe.get_doc("Monthly Production Planning", name)
    return plans
