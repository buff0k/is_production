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
    "Bankfontein": "#F1C40F",
}

TARGET_LINE_COLOR = "#0B2C4D"
ACTUAL_LINE_COLOR = "#1E8449"


# =========================================================
# MAIN EXECUTE
# =========================================================
def execute(filters=None):
    if not filters or not filters.get("monthly_production_plan"):
        return [], None, "<b>Please select a Monthly Production Plan.</b>"

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

    return [], None, f"""
    <style>
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 22px;
            padding: 18px;
        }}

        .graph-card {{
            border: 1px solid #cfcfcf;
            background: #fff;
            height: 420px;
            display: flex;
            flex-direction: column;
        }}

        .site-banner {{
            padding: 10px 14px;
            font-weight: 700;
            font-size: 13px;
            line-height: 1.4;
        }}

        .chart-wrapper {{
            flex: 1;
            padding: 18px 22px 22px 22px;
        }}

        .chart-wrapper canvas {{
            width: 100% !important;
            height: 100% !important;
        }}
    </style>

    <div class="dashboard-grid">
        {''.join(site_blocks)}
    </div>
    """


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
                    "borderWidth": 3,
                    "tension": 0.25,
                    "pointRadius": 3,
                },
                {
                    "label": "MTD Actual",
                    "data": actual,
                    "borderColor": ACTUAL_LINE_COLOR,
                    "borderWidth": 3,
                    "tension": 0.25,
                    "pointRadius": 3,
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

    return f"""
    <div class="graph-card">
        <div class="site-banner" style="background:{SITE_COLORS.get(site)}">
            Site: {site}<br>
            Production Period: {prod_start} → {prod_end}<br>
            MTD up to: {yesterday}
        </div>
        <div class="chart-wrapper">
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
