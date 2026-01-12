import frappe
from frappe.utils import format_date, getdate
from datetime import datetime, timedelta


GREEN = "#E9F5EC"
RED = "#FDEAEA"
FORECAST_TARGET = 619_380


# =========================================================
# OPERATIONAL DAY (06:00 → 05:59)
# =========================================================
def get_operational_dates():
    now = datetime.now()
    today = now.date()
    yesterday = today - timedelta(days=1)

    if now.hour < 6:
        return [yesterday, today]

    return [today]


# =========================================================
# MAIN EXECUTE
# =========================================================
def execute(filters=None):
    if not filters:
        return [], None, "<b>Please select a Monthly Production Definition.</b>"

    dmp = frappe.get_doc(
        "Define Monthly Production",
        filters.get("define_monthly_production")
    )

    if not dmp.define:
        return [], None, "<b>No sites configured.</b>"

    site_sections = []

    for row in dmp.define:
        site_sections.append(
            build_site_section(
                site=row.site,
                start_date=getdate(row.start_date),
                end_date=getdate(row.end_date)
            )
        )

    final_html = f"""
    <style>
        @page {{ size: landscape; margin: 10mm; }}

        body {{
            font-family: Arial, Helvetica, sans-serif;
            font-weight: bold;
        }}

        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(700px, 1fr));
            gap: 30px;
        }}

        .site-section {{
            border: 3px solid #003366;
        }}

        .site-header {{
            padding: 10px 14px;
            color: #003366;
        }}

        .site-title {{
            font-size: 18px;
            margin-bottom: 4px;
        }}

        .site-period {{
            font-size: 13px;
        }}

        .site-body {{
            padding: 12px;
        }}

        table.summary-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            font-size: 12px;
        }}

        table.summary-table th,
        table.summary-table td {{
            border: 1px solid #9FB6D1;
            padding: 4px 6px;
            text-align: right;
            white-space: nowrap;
        }}

        table.summary-table th {{
            background: #EAF3FA;
            color: #003366;
            text-align: center;
        }}
    </style>

    <div class="dashboard-grid">
        {''.join(site_sections)}
    </div>
    """

    return [], None, final_html


# =========================================================
# SITE SECTION
# =========================================================
def build_site_section(site, start_date, end_date):
    site_colours = {
        "Klipfontein": "#E6F0FA",
        "Gwab": "#F2F2F2",
        "Kriel Rehabilitation": "#E9F5EC",
        "Koppie": "#F7F3E8",
        "Uitgevallen": "#F1ECF8",
        "Bankfontein": "#FCEEE6",
    }

    bg_colour = site_colours.get(site, "#FFFFFF")

    return f"""
    <div class="site-section">
        <div class="site-header" style="background:{bg_colour};">
            <div class="site-title">SITE: {site}</div>
            <div class="site-period">
                PRODUCTION PERIOD: {format_date(start_date)} → {format_date(end_date)}
            </div>
        </div>
        <div class="site-body">
            {build_daily_report_html(site, start_date, end_date)}
        </div>
    </div>
    """


# =========================================================
# DAILY REPORT
# =========================================================
def build_daily_report_html(site, start_date, end_date):
    mpp = get_monthly_plan(site, end_date)
    month_start = start_date

    operational_dates = get_operational_dates()

    actual_ts_day = frappe.db.sql("""
        SELECT COALESCE(SUM(total_ts_bcm),0)
        FROM `tabHourly Production`
        WHERE location=%s AND prod_date IN %s
    """, (site, tuple(operational_dates)))[0][0]

    actual_dozer_day = frappe.db.sql("""
        SELECT COALESCE(SUM(total_dozing_bcm),0)
        FROM `tabHourly Production`
        WHERE location=%s AND prod_date IN %s
    """, (site, tuple(operational_dates)))[0][0]

    mtd_actual_bcms = get_actual_bcms_for_date(site, end_date, month_start)
    mtd_coal = get_mtd_coal_dynamic(site, end_date, month_start)
    mtd_waste = mtd_actual_bcms - (mtd_coal / 1.5)

    return build_html(
        mpp,
        mtd_actual_bcms,
        mtd_coal,
        mtd_waste,
        actual_ts_day,
        actual_dozer_day
    )


# =========================================================
# MONTHLY PLAN
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


# =========================================================
# MTD BCMs
# =========================================================
def get_actual_bcms_for_date(site, end_date, month_start):
    ts, dz = get_hourly_bcms(month_start, end_date, site)
    return ts + dz


def get_hourly_bcms(start_date, end_date, site):
    ts = frappe.db.sql("""
        SELECT COALESCE(SUM(tl.bcms),0)
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s AND hp.location = %s
    """, (start_date, end_date, site))[0][0]

    dz = frappe.db.sql("""
        SELECT COALESCE(SUM(dp.bcm_hour),0)
        FROM `tabHourly Production` hp
        JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s AND hp.location = %s
    """, (start_date, end_date, site))[0][0]

    return ts or 0, dz or 0


# =========================================================
# COAL
# =========================================================
def get_mtd_coal_dynamic(site, end_date, month_start):
    COAL_CONVERSION = 1.5

    coal_bcm = frappe.db.sql("""
        SELECT COALESCE(SUM(tl.bcms),0)
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
          AND LOWER(tl.mat_type) LIKE '%%coal%%'
    """, (month_start, end_date, site))[0][0]

    return (coal_bcm or 0) * COAL_CONVERSION


# =========================================================
# HTML SUMMARY TABLE (WITH COLOUR LOGIC)
# =========================================================
def build_html(mpp, mtd_actual, mtd_coal, mtd_waste, ts, dz):

    def fmt(v): return f"{int(round(v)):,}"
    def cell(val, good): 
        return f"<td style='background:{GREEN if good else RED};'>{fmt(val)}</td>"

    monthly = mpp.monthly_target_bcm
    coal_total = mpp.coal_tons_planned
    waste_total = mpp.waste_bcms_planned
    days = mpp.num_prod_days
    done = mpp.prod_days_completed

    mtd_plan = monthly / days * done if days else 0
    coal_plan = coal_total / days * done if days else 0
    waste_plan = waste_total / days * done if days else 0

    forecast = mpp.month_forecated_bcm

    return f"""
    <table class="summary-table">
        <tr>
            <th>Total Target</th><th>Total Coal</th><th>Total Waste</th>
            <th>MTD Actual</th><th>MTD Plan</th>
            <th>MTD Coal</th><th>MTD C Plan</th>
            <th>MTD Waste</th><th>MTD W Plan</th>
            <th>Remaining</th><th>Forecast</th>
            <th>Daily Target</th><th>TS</th><th>Dozing</th><th>Day BCM</th>
        </tr>
        <tr>
            <td>{fmt(monthly)}</td>
            <td>{fmt(coal_total)}</td>
            <td>{fmt(waste_total)}</td>
            {cell(mtd_actual, mtd_actual >= mtd_plan)}
            <td>{fmt(mtd_plan)}</td>
            {cell(mtd_coal, mtd_coal >= coal_plan)}
            <td>{fmt(coal_plan)}</td>
            {cell(mtd_waste, mtd_waste >= waste_plan)}
            <td>{fmt(waste_plan)}</td>
            <td>{fmt(monthly - mtd_actual)}</td>
            {cell(forecast, forecast >= FORECAST_TARGET)}
            <td>{fmt(mpp.target_bcm_day)}</td>
            <td>{fmt(ts)}</td>
            <td>{fmt(dz)}</td>
            <td>{fmt(ts + dz)}</td>
        </tr>
    </table>
    """
