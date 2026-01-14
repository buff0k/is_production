import frappe
from frappe.utils import format_date, getdate, nowdate
from datetime import datetime, timedelta

GREEN = "#C9F2D8"
RED = "#F9CACA"
HEADER_BG = "#EEF4FB"

SITE_COLOURS = {
    "Klipfontein": "#4DA3FF",
    "Gwab": "#ECE6F5",
    "Kriel Rehabilitation": "#2ECC71",
    "Koppie": "#F39C12",
    "Uitgevallen": "#1ABC9C",
    "Bankfontein": "#F1C40F",
}


def get_operational_dates():
    now = datetime.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    return [yesterday, today] if now.hour < 6 else [today]


def execute(filters=None):
    if not filters:
        return [], None, "<b>Please select a Monthly Production Definition.</b>"

    dmp = frappe.get_doc(
        "Define Monthly Production",
        filters.get("define_monthly_production")
    )

    if not dmp.define:
        return [], None, "<b>No sites configured.</b>"

    sites = [r.site for r in dmp.define]

    mpp_map = get_monthly_plans_bulk(dmp.define)
    today_bcm_map = get_today_bcm_bulk(sites)
    mtd_coal_map = get_mtd_coal_bulk(
        sites,
        min(r.start_date for r in dmp.define),
        max(r.end_date for r in dmp.define)
    )

    site_sections = []

    for row in dmp.define:
        mpp = mpp_map.get(row.site)
        if not mpp:
            continue

        day_bcm = today_bcm_map.get(row.site, 0)
        mtd_coal = mtd_coal_map.get(row.site, 0)
        mtd_actual = mpp.month_actual_bcm
        mtd_waste = mtd_actual - (mtd_coal / 1.5)

        site_sections.append(
            build_site_section(
                row.site,
                getdate(row.start_date),
                getdate(row.end_date),
                mpp,
                mtd_actual,
                mtd_coal,
                mtd_waste,
                day_bcm
            )
        )

    html = f"""
    <style>
        @page {{ size: landscape; margin: 10mm; }}

        body {{
            font-family: Arial, Helvetica, sans-serif;
            font-weight: bold;
            color: #002244;
            margin: 0;
        }}

        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(750px, 1fr));
            gap: 8px;
        }}

        .site-section {{
            border: 4px solid #000;
            margin-bottom: 6px;
        }}

        table.summary-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}

        table.summary-table th {{
            background: {HEADER_BG};
            border: 1px solid #9FB6D1;
            padding: 6px;
            text-align: center;
        }}

        table.summary-table td {{
            border: 1px solid #9FB6D1;
            padding: 4px 6px;
            text-align: right;
            white-space: nowrap;
        }}

        /* KPI GROUP BORDERS */
        .summary-table th:nth-child(4),
        .summary-table td:nth-child(4) {{ border-left: 4px solid #000; }}
        .summary-table th:nth-child(6),
        .summary-table td:nth-child(6) {{ border-right: 4px solid #000; }}

        .summary-table th:nth-child(7),
        .summary-table td:nth-child(7) {{ border-left: 4px solid #000; }}
        .summary-table th:nth-child(9),
        .summary-table td:nth-child(9) {{ border-right: 4px solid #000; }}

        .summary-table th:nth-child(10),
        .summary-table td:nth-child(10) {{ border-left: 4px solid #000; }}
        .summary-table th:nth-child(12),
        .summary-table td:nth-child(12) {{ border-right: 4px solid #000; }}

        .summary-table th:nth-child(13),
        .summary-table td:nth-child(13) {{ border-left: 4px solid #000; }}
        .summary-table th:nth-child(15),
        .summary-table td:nth-child(15) {{ border-right: 4px solid #000; }}
    </style>

    <div class="dashboard-grid">
        {''.join(site_sections)}
    </div>
    """

    return [], None, html


# ===============================
# BULK QUERIES
# ===============================

def get_today_bcm_bulk(sites):
    today = getdate(nowdate())
    rows = frappe.db.sql("""
        SELECT
            location,
            SUM(total_ts_bcm + total_dozing_bcm) AS bcm
        FROM `tabHourly Production`
        WHERE location IN %(sites)s
          AND prod_date = %(today)s
        GROUP BY location
    """, {"sites": sites, "today": today}, as_dict=True)

    return {r.location: r.bcm or 0 for r in rows}


def get_mtd_coal_bulk(sites, start_date, end_date):
    rows = frappe.db.sql("""
        SELECT
            hp.location,
            SUM(
                CASE WHEN LOWER(tl.mat_type) LIKE '%%coal%%'
                THEN tl.bcms ELSE 0 END
            ) * 1.5 AS mtd_coal
        FROM `tabHourly Production` hp
        LEFT JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.location IN %(sites)s
          AND hp.prod_date BETWEEN %(start)s AND %(end)s
        GROUP BY hp.location
    """, {"sites": sites, "start": start_date, "end": end_date}, as_dict=True)

    return {r.location: r.mtd_coal or 0 for r in rows}


def get_monthly_plans_bulk(rows):
    plans = {}

    for r in rows:
        name = frappe.db.get_value(
            "Monthly Production Planning",
            {
                "location": r.site,
                "prod_month_start_date": ["<=", r.end_date],
                "prod_month_end_date": [">=", r.end_date],
            },
            "name"
        )
        if name:
            plans[r.site] = frappe.get_doc(
                "Monthly Production Planning", name
            )

    return plans


# ===============================
# HTML BUILDERS
# ===============================

def build_site_section(site, start_date, end_date, mpp,
                       mtd_actual, mtd_coal, mtd_waste, day_bcm):
    bg = SITE_COLOURS.get(site, "#BDC3C7")

    return f"""
    <div class="site-section">
        <div style="padding:6px 10px;background:{bg};color:#002244;">
            <div style="font-size:17px;">SITE: {site}</div>
            <div style="font-size:12px;">
                PRODUCTION PERIOD: {format_date(start_date)} → {format_date(end_date)}
            </div>
        </div>
        <div style="padding:6px;">
            {build_html(mpp, mtd_actual, mtd_coal, mtd_waste, day_bcm)}
        </div>
    </div>
    """


def build_html(mpp, mtd_actual, mtd_coal, mtd_waste, day_bcm):

    def fmt(v): return f"{int(round(v)):,}"
    def var_cell(v):
        return f"<td style='background:{RED if v > 0 else GREEN};'>{fmt(v)}</td>"

    monthly = mpp.monthly_target_bcm
    coal_total = mpp.coal_tons_planned
    waste_total = mpp.waste_bcms_planned
    days = mpp.num_prod_days
    done = mpp.prod_days_completed

    mtd_plan = monthly / days * done if days else 0
    coal_plan = coal_total / days * done if days else 0
    waste_plan = waste_total / days * done if days else 0

    day_target = mpp.target_bcm_day
    day_var = day_target - day_bcm

    return f"""
    <table class="summary-table">
        <tr>
            <th>Month Target(bcm)</th>
            <th>Month Coal(t)</th>
            <th>Month Waste(bcm)</th>

            <th>MTD Act(bcm)</th>
            <th>MTD Plan(bcm)</th>
            <th>Var</th>

            <th>MTD C (t)</th>
            <th>MTD C Plan(t)</th>
            <th>Var C</th>

            <th>MTD W (bcm)</th>
            <th>MTD W Plan(bcm)</th>
            <th>Var W</th>

            <th>Day BCM</th>
            <th>Day Target(bcm)</th>
            <th>Day Var</th>
        </tr>
        <tr>
            <td>{fmt(monthly)}</td>
            <td>{fmt(coal_total)}</td>
            <td>{fmt(waste_total)}</td>

            <td>{fmt(mtd_actual)}</td>
            <td>{fmt(mtd_plan)}</td>
            {var_cell(mtd_plan - mtd_actual)}

            <td>{fmt(mtd_coal)}</td>
            <td>{fmt(coal_plan)}</td>
            {var_cell(coal_plan - mtd_coal)}

            <td>{fmt(mtd_waste)}</td>
            <td>{fmt(waste_plan)}</td>
            {var_cell(waste_plan - mtd_waste)}

            <td>{fmt(day_bcm)}</td>
            <td>{fmt(day_target)}</td>
            {var_cell(day_var)}
        </tr>
    </table>
    """
