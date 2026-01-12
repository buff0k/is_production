import frappe
from frappe.utils import format_date, now_datetime
from datetime import datetime, time, timedelta


THRESHOLD = 220
Y_MAX = 400


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

    if not dmp.define_site_production:
        return [], None, "<b>No sites configured.</b>"

    start_dt, end_dt = get_production_window()

    # 👉 convert to dates (Hourly Production has prod_date, not datetime)
    start_date = start_dt.date()
    end_date = end_dt.date()

    site_blocks = []

    for row in dmp.define_site_production:
        site_blocks.append(
            build_site_graph(
                site=row.site,
                start_date=start_date,
                end_date=end_date,
                start_dt=start_dt
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
def build_site_graph(site, start_date, end_date, start_dt):
    excavators = get_site_excavators(site)

    labels = []
    values = []

    for exc in excavators:
        bcm, hours = get_excavator_bcm_and_hours(
            site, exc, start_date, end_date
        )
        avg = round(bcm / hours, 2) if hours > 0 else 0

        labels.append(exc)
        values.append(avg)

    chart_id = f"chart_{site.replace(' ', '_')}"

    return f"""
    <div class="graph-card">
        <div class="graph-header">
            {site}<br>
            <small>Production day started at {start_dt.strftime('%H:%M')}</small>
        </div>

        <canvas id="{chart_id}" height="140"></canvas>

        <script>
            new Chart(document.getElementById("{chart_id}"), {{
                type: "bar",
                data: {{
                    labels: {labels},
                    datasets: [
                        {{
                            label: "Avg BCM / Hr",
                            data: {values},
                            backgroundColor: "#2E7D32"
                        }},
                        {{
                            label: "Threshold",
                            type: "line",
                            data: {[THRESHOLD] * len(labels)},
                            borderColor: "#C62828",
                            borderWidth: 1.5,
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
                                autoSkip: false
                            }}
                        }},
                        y: {{
                            beginAtZero: true,
                            max: {Y_MAX},
                            ticks: {{
                                stepSize: 100,
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
# PRODUCTION WINDOW (06:00 → NOW)
# =========================================================
def get_production_window():
    now = now_datetime()
    today_6am = datetime.combine(now.date(), time(6, 0))

    if now < today_6am:
        start = today_6am - timedelta(days=1)
    else:
        start = today_6am

    return start, now


# =========================================================
# EXCAVATORS
# =========================================================
def get_site_excavators(site):
    return frappe.db.get_all(
        "Asset",
        filters={
            "location": site,
            "asset_category": "Excavator",
            "docstatus": 0
        },
        pluck="name"
    )


# =========================================================
# BCM + HOURS (FIXED)
# =========================================================
def get_excavator_bcm_and_hours(site, excavator, start_date, end_date):
    rows = frappe.db.sql("""
        SELECT
            hp.name,
            COALESCE(SUM(tl.bcms), 0) AS bcm
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.location = %s
          AND hp.prod_date BETWEEN %s AND %s
          AND tl.asset_name_shoval = %s
        GROUP BY hp.name
    """, (site, start_date, end_date, excavator), as_dict=True)

    total_bcm = sum(r.bcm for r in rows)
    hours = len(rows)  # 1 Hourly Production record = 1 hour

    return total_bcm, hours
