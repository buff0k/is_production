import frappe
from frappe.utils import getdate, format_date, nowdate
import calendar
from datetime import date

# =========================================================
# CONSTANTS
# =========================================================
Y_AXIS_STEP = 10_000

SITE_COLORS = {
    "Klipfontein": "#4DA3FF",
    "Gwab": "#00B3A4",
    "Kriel Rehabilitation": "#2ECC71",
    "Koppie": "#F39C12",
    "Uitgevallen": "#9B59B6",
    "Bankfontein": "#E74C3C",
}

TARGET_LINE_COLOR = "#0B2C4D"
ACTUAL_LINE_COLOR = "#1E8449"


# =========================================================
# MAIN EXECUTE
# =========================================================
def execute(filters=None):
    if not filters or not filters.get("monthly_production_plan"):
        return [], None, "<b>Please select a Monthly Production Plan.</b>"

    today = getdate(nowdate())

    dmp = frappe.get_doc(
        "Define Monthly Production",
        filters.get("monthly_production_plan")
    )

    if not dmp.define:
        return [], None, "<b>No sites configured.</b>"

    # 🔒 FETCH MONTHLY PLANS ONCE (KEY FIX)
    mpp_map = get_monthly_plans(dmp.define)

    site_blocks = []

    for row in dmp.define:
        mpp = mpp_map.get(row.site)
        if not mpp:
            continue

        site_blocks.append(
            build_site_graph(
                site=row.site,
                start_date=getdate(row.start_date),
                end_date=getdate(row.end_date),
                monthly_target=mpp.monthly_target_bcm,
                today=today
            )
        )

    return [], None, f"""
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 14px;
            padding: 12px;
        }}

        .graph-card {{
            border: 2px solid #000;
            background: #fff;
        }}

        .site-banner {{
            padding: 10px 14px;
            color: #000;
        }}

        .site-title {{
            font-size: 18px;
            font-weight: 800;
        }}

        .site-meta {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: 4px;
            font-size: 12px;
            font-weight: 700;
        }}

        .legend {{
            display: flex;
            gap: 12px;
            align-items: center;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        .legend-box {{
            width: 12px;
            height: 12px;
        }}

        .chart-wrapper {{
            padding: 6px 10px 10px 10px;
        }}

        canvas {{
            max-height: 190px !important;
        }}
    </style>

    <div class="dashboard-grid">
        {''.join(site_blocks)}
    </div>
    """


# =========================================================
# SITE GRAPH
# =========================================================
def build_site_graph(site, start_date, end_date, monthly_target, today):
    labels = build_month_labels(start_date)
    target_line = build_cumulative_target(monthly_target, len(labels))
    actual_line = build_cumulative_actual(
        site=site,
        start_date=start_date,
        end_date=end_date,
        labels=labels,
        today=today
    )

    chart_id = f"chart_{site.replace(' ', '_')}"
    site_color = SITE_COLORS.get(site, "#CCCCCC")

    y_max = ((monthly_target + Y_AXIS_STEP - 1) // Y_AXIS_STEP) * Y_AXIS_STEP

    return f"""
    <div class="graph-card">
        <div class="site-banner" style="background:{site_color}">
            <div class="site-title">SITE: {site}</div>
            <div class="site-meta">
                <div>
                    PRODUCTION PERIOD: {format_date(start_date)} → {format_date(end_date)}
                </div>
                <div class="legend">
                    <div class="legend-item">
                        <div class="legend-box" style="background:{TARGET_LINE_COLOR}"></div>
                        Target
                    </div>
                    <div class="legend-item">
                        <div class="legend-box" style="background:{ACTUAL_LINE_COLOR}"></div>
                        Actual
                    </div>
                </div>
            </div>
        </div>

        <div class="chart-wrapper">
            <canvas id="{chart_id}" height="180"></canvas>
        </div>

        <script>
            new Chart(document.getElementById("{chart_id}"), {{
                type: "line",
                data: {{
                    labels: {labels},
                    datasets: [
                        {{
                            label: "Target",
                            data: {target_line},
                            borderColor: "{TARGET_LINE_COLOR}",
                            borderWidth: 3,
                            tension: 0.25,
                            pointRadius: 0
                        }},
                        {{
                            label: "Actual",
                            data: {actual_line},
                            borderColor: "{ACTUAL_LINE_COLOR}",
                            borderWidth: 3,
                            tension: 0.25,
                            pointRadius: 0,
                            spanGaps: false
                        }}
                    ]
                }},
                options: {{
                    animation: false,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        x: {{
                            grid: {{ display: false }},
                            ticks: {{
                                font: {{ size: 9 }},
                                autoSkip: true,
                                maxTicksLimit: 15
                            }}
                        }},
                        y: {{
                            beginAtZero: true,
                            max: {y_max},
                            grid: {{ display: false }},
                            ticks: {{
                                stepSize: {Y_AXIS_STEP},
                                font: {{ size: 9 }}
                            }}
                        }}
                    }}
                }}
            }});
        </script>
    </div>
    """


# =========================================================
# HELPERS
# =========================================================
def build_month_labels(start_date):
    year = start_date.year
    month = start_date.month
    days = calendar.monthrange(year, month)[1]
    return [str(d) for d in range(1, days + 1)]


def build_cumulative_target(monthly_target, days):
    daily = monthly_target / days if days else 0
    cumulative = 0
    return [round((cumulative := cumulative + daily), 2) for _ in range(days)]


# =========================================================
# OPTIMISED ACTUALS (SINGLE QUERY PER SITE)
# =========================================================
def build_cumulative_actual(site, start_date, end_date, labels, today):
    daily_map = get_daily_actuals(site, start_date, end_date)

    cumulative = 0
    values = []

    for day in labels:
        prod_date = date(start_date.year, start_date.month, int(day))

        if prod_date > today:
            values.append(None)
            continue

        bcm = daily_map.get(prod_date, 0)
        cumulative += bcm
        values.append(round(cumulative, 2))

    return values


def get_daily_actuals(site, start_date, end_date):
    rows = frappe.db.sql("""
        SELECT
            prod_date,
            SUM(total_ts_bcm + total_dozing_bcm) AS bcm
        FROM `tabHourly Production`
        WHERE location = %s
          AND prod_date BETWEEN %s AND %s
        GROUP BY prod_date
        ORDER BY prod_date
    """, (site, start_date, end_date), as_dict=True)

    return {row.prod_date: row.bcm for row in rows}


# =========================================================
# FETCH MONTHLY PLANS ONCE
# =========================================================
def get_monthly_plans(define_rows):
    plans = {}

    for row in define_rows:
        plan_name = frappe.db.get_value(
            "Monthly Production Planning",
            {
                "location": row.site,
                "prod_month_start_date": ["<=", row.end_date],
                "prod_month_end_date": [">=", row.end_date],
            },
            "name",
        )

        if plan_name:
            plans[row.site] = frappe.get_doc(
                "Monthly Production Planning",
                plan_name
            )

    return plans
