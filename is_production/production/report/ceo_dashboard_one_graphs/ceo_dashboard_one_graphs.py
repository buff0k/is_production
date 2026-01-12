import frappe
from frappe.utils import getdate, format_date
import calendar
from datetime import date


Y_AXIS_STEP = 10_000  # 🔒 Fixed Y-axis interval


# =========================================================
# MAIN EXECUTE
# =========================================================
def execute(filters=None):
    if not filters or not filters.get("monthly_production_plan"):
        return [], None, "<b>Please select a Monthly Production Plan.</b>"

    dmp = frappe.get_doc(
        "Define Monthly Production",
        filters.get("monthly_production_plan")
    )

    if not dmp.define:
        return [], None, "<b>No sites configured.</b>"

    site_blocks = []

    for row in dmp.define:
        mpp = get_monthly_plan(row.site, getdate(row.end_date))
        if not mpp:
            continue

        site_blocks.append(
            build_site_graph(
                site=row.site,
                start_date=getdate(row.start_date),
                end_date=getdate(row.end_date),
                monthly_target=mpp.monthly_target_bcm
            )
        )

    return [], None, f"""
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            padding: 12px;
        }}

        .graph-card {{
            border: 1.5px solid #333;
            border-radius: 5px;
            background: #fff;
            padding: 6px;
        }}

        .graph-header {{
            font-weight: bold;
            font-size: 13px;
            margin-bottom: 2px;
        }}

        .graph-header small {{
            font-weight: normal;
            font-size: 11px;
        }}

        canvas {{
            max-height: 160px !important;
        }}
    </style>

    <div class="dashboard-grid">
        {''.join(site_blocks)}
    </div>
    """


# =========================================================
# SITE GRAPH
# =========================================================
def build_site_graph(site, start_date, end_date, monthly_target):
    labels = build_month_labels(start_date)
    target_line = build_cumulative_target(monthly_target, len(labels))
    actual_line = build_cumulative_actual(site, start_date, labels)

    chart_id = f"chart_{site.replace(' ', '_')}"

    # Ensure Y-axis max is rounded UP to nearest 10k
    y_max = ((monthly_target + Y_AXIS_STEP - 1) // Y_AXIS_STEP) * Y_AXIS_STEP

    return f"""
    <div class="graph-card">
        <div class="graph-header">
            {site}<br>
            <small>{format_date(start_date)} → {format_date(end_date)}</small>
        </div>

        <canvas id="{chart_id}" height="140"></canvas>

        <script>
            new Chart(document.getElementById("{chart_id}"), {{
                type: "line",
                data: {{
                    labels: {labels},
                    datasets: [
                        {{
                            label: "Target",
                            data: {target_line},
                            borderColor: "#003366",
                            borderWidth: 1.5,
                            tension: 0.25,
                            pointRadius: 0
                        }},
                        {{
                            label: "Actual",
                            data: {actual_line},
                            borderColor: "#2E7D32",
                            borderWidth: 1.5,
                            tension: 0.25,
                            pointRadius: 0
                        }}
                    ]
                }},
                options: {{
                    animation: false,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: "top",
                            labels: {{
                                boxWidth: 10,
                                font: {{ size: 10 }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{
                                font: {{ size: 9 }},
                                autoSkip: true,
                                maxTicksLimit: 15
                            }}
                        }},
                        y: {{
                            beginAtZero: true,
                            max: {y_max},
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
# MONTH LABELS
# =========================================================
def build_month_labels(start_date):
    year = start_date.year
    month = start_date.month
    days = calendar.monthrange(year, month)[1]
    return [str(d) for d in range(1, days + 1)]


# =========================================================
# TARGET (CUMULATIVE)
# =========================================================
def build_cumulative_target(monthly_target, days):
    daily = monthly_target / days if days else 0
    cumulative = 0
    return [round((cumulative := cumulative + daily), 2) for _ in range(days)]


# =========================================================
# ACTUAL (CUMULATIVE)
# =========================================================
def build_cumulative_actual(site, start_date, labels):
    cumulative = 0
    values = []

    for day in labels:
        prod_date = date(start_date.year, start_date.month, int(day))
        bcm = frappe.db.sql("""
            SELECT COALESCE(SUM(total_ts_bcm + total_dozing_bcm), 0)
            FROM `tabHourly Production`
            WHERE location = %s
              AND prod_date = %s
        """, (site, prod_date))[0][0]

        cumulative += bcm
        values.append(round(cumulative, 2))

    return values


# =========================================================
# MONTHLY PRODUCTION PLANNING
# =========================================================
def get_monthly_plan(site, date):
    plan_name = frappe.db.get_value(
        "Monthly Production Planning",
        {
            "location": site,
            "prod_month_start_date": ["<=", date],
            "prod_month_end_date": [">=", date],
        },
        "name",
    )
    return frappe.get_doc("Monthly Production Planning", plan_name) if plan_name else None
