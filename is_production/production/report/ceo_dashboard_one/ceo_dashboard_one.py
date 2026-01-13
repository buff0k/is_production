import frappe
from frappe.utils import format_date, getdate
from datetime import datetime, timedelta

# =========================================================
# COLOUR CONSTANTS
# =========================================================
GREEN = "#C9F2D8"
RED = "#F9CACA"

FORECAST_TARGET = 619_380


# =========================================================
# OPERATIONAL DAY (06:00 → 05:59)
# =========================================================
def get_operational_dates():
    now = datetime.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    return [yesterday, today] if now.hour < 6 else [today]


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

    # 🔒 Fetch all Monthly Production Plans ONCE
    mpp_map = get_monthly_plans(dmp.define)

    site_sections = []

    for row in dmp.define:
        mpp = mpp_map.get(row.site)
        if not mpp:
            continue

        site_sections.append(
            build_site_section(
                site=row.site,
                start_date=getdate(row.start_date),
                end_date=getdate(row.end_date),
                mpp=mpp
            )
        )

    html = f"""
    <style>
        @page {{ size: landscape; margin: 10mm; }}

        body {{
            font-family: Arial, Helvetica, sans-serif;
            font-weight: bold;
            color: #002244;
        }}

        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(700px, 1fr));
            gap: 30px;
        }}

        .site-section {{
            border: 4px solid #002244;
        }}

        .site-header {{
            padding: 12px 16px;
            font-weight: 800;
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
            background: #DCEAF7;
            color: #002244;
            text-align: center;
        }}
    </style>

    <div class="dashboard-grid">
        {''.join(site_sections)}
    </div>
    """

    return [], None, html


# =========================================================
# SITE SECTION
# =========================================================
def build_site_section(site, start_date, end_date, mpp):
    colours = {
        "Klipfontein": "#4DA3FF",
        "Gwab": "#00B3A4",
        "Kriel Rehabilitation": "#2ECC71",
        "Koppie": "#F39C12",
        "Uitgevallen": "#9B59B6",
        "Bankfontein": "#E74C3C",
    }

    bg = colours.get(site, "#BDC3C7")

    return f"""
    <div class="site-section">
        <div class="site-header" style="background:{bg};">
            <div class="site-title">SITE: {site}</div>
            <div class="site-period">
                PRODUCTION PERIOD: {format_date(start_date)} → {format_date(end_date)}
            </div>
        </div>
        <div class="site-body">
            {build_daily_report_html(site, start_date, end_date, mpp)}
        </div>
    </div>
    """


# =========================================================
# DAILY REPORT
# =========================================================
def build_daily_report_html(site, start_date, end_date, mpp):
    operational_dates = get_operational_dates()

    data = get_aggregated_production_data(
        site=site,
        start_date=start_date,
        end_date=end_date,
        operational_dates=operational_dates
    )

    day_bcm = data["day_ts"] + data["day_dz"]

    # 🔒 AUTHORITATIVE MTD (unchanged behaviour)
    mtd_actual = mpp.month_actual_bcm

    mtd_coal = data["mtd_coal"]
    mtd_waste = mtd_actual - (mtd_coal / 1.5)

    return build_html(
        mpp=mpp,
        mtd_actual=mtd_actual,
        mtd_coal=mtd_coal,
        mtd_waste=mtd_waste,
        ts=data["day_ts"],
        dz=data["day_dz"]
    )


# =========================================================
# AGGREGATED PRODUCTION DATA (SINGLE QUERY PER SITE)
# =========================================================
def get_aggregated_production_data(site, start_date, end_date, operational_dates):
    row = frappe.db.sql("""
        SELECT
            SUM(CASE WHEN hp.prod_date IN %(ops)s THEN hp.total_ts_bcm ELSE 0 END) AS day_ts,
            SUM(CASE WHEN hp.prod_date IN %(ops)s THEN hp.total_dozing_bcm ELSE 0 END) AS day_dz,
            SUM(
                CASE
                    WHEN LOWER(tl.mat_type) LIKE '%%coal%%'
                    THEN tl.bcms
                    ELSE 0
                END
            ) * 1.5 AS mtd_coal
        FROM `tabHourly Production` hp
        LEFT JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.location = %(site)s
          AND hp.prod_date BETWEEN %(start)s AND %(end)s
    """, {
        "site": site,
        "start": start_date,
        "end": end_date,
        "ops": tuple(operational_dates),
    }, as_dict=True)[0]

    return {
        "day_ts": row.day_ts or 0,
        "day_dz": row.day_dz or 0,
        "mtd_coal": row.mtd_coal or 0,
    }


# =========================================================
# FETCH MONTHLY PLANS ONCE (KEY UPGRADE)
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


# =========================================================
# HTML SUMMARY TABLE (UNCHANGED)
# =========================================================
def build_html(mpp, mtd_actual, mtd_coal, mtd_waste, ts, dz):

    def fmt(v):
        return f"{int(round(v)):,}"

    def cell(val, good):
        return f"<td style='background:{GREEN if good else RED};'>{fmt(val)}</td>"

    day_bcm = ts + dz
    daily_remaining = mpp.target_bcm_day - day_bcm

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
            <th>Daily Target</th><th>Day BCM</th><th>Daily Left</th>
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
            <td>{fmt(day_bcm)}</td>
            <td>{fmt(daily_remaining)}</td>
        </tr>
    </table>
    """
