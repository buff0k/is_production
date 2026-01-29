import frappe
from frappe.utils import format_date, getdate
from datetime import datetime, timedelta

# =========================================================
# COLOUR CONSTANTS (LOGIC PRESERVED)
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

    # 🔒 Fetch all Monthly Production Plans ONCE (UNCHANGED)
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

    # Theme-aware, scoped styling (no global bleed)
    html = f"""
    <style>
        /* Scope everything */
        .isd-ceo-one {{
            --isd-gap: 12px;

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

        .isd-ceo-one .isd-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(700px, 1fr));
            gap: var(--isd-gap);
            align-items: start;
        }}

        .isd-ceo-one .isd-site {{
            background: var(--isd-card);
            border: 1px solid var(--isd-border);
            border-radius: var(--isd-radius);
            overflow: hidden;
            box-shadow: var(--isd-shadow);
        }}

        .isd-ceo-one .isd-site-header {{
            padding: 12px 14px;
            border-bottom: 1px solid var(--isd-border);
        }}

        .isd-ceo-one .isd-site-title {{
            font-size: 13px;
            font-weight: 800;
            line-height: 1.2;
            margin: 0;
            color: var(--isd-text);
        }}

        .isd-ceo-one .isd-site-period {{
            font-size: 11px;
            font-weight: 600;
            color: var(--isd-muted);
            margin-top: 4px;
        }}

        .isd-ceo-one .isd-site-body {{
            padding: 12px 12px 14px 12px;
        }}

        /* Table */
        .isd-ceo-one table.summary-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            table-layout: fixed;
            font-size: 11px;
        }}

        .isd-ceo-one table.summary-table th,
        .isd-ceo-one table.summary-table td {{
            border-right: 1px solid var(--isd-border);
            border-bottom: 1px solid var(--isd-border);
            padding: 6px 6px;
            text-align: right;
            background: var(--isd-control-bg);
            color: var(--isd-text);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .isd-ceo-one table.summary-table th {{
            font-weight: 800;
            text-align: center;
            background: var(--isd-control-bg);
        }}

        /* Round the table corners inside card */
        .isd-ceo-one table.summary-table tr:first-child th:first-child {{
            border-top-left-radius: 10px;
        }}
        .isd-ceo-one table.summary-table tr:first-child th:last-child {{
            border-top-right-radius: 10px;
        }}
        .isd-ceo-one table.summary-table tr:last-child td:first-child {{
            border-bottom-left-radius: 10px;
        }}
        .isd-ceo-one table.summary-table tr:last-child td:last-child {{
            border-bottom-right-radius: 10px;
        }}

        /* Remove extra borders at edges */
        .isd-ceo-one table.summary-table th:last-child,
        .isd-ceo-one table.summary-table td:last-child {{
            border-right: none;
        }}

        /* Subtle “status” cells that remain theme-friendly */
        .isd-ceo-one td.isd-good {{
            background: rgba(47, 179, 68, 0.16) !important;
        }}
        .isd-ceo-one td.isd-bad {{
            background: rgba(226, 76, 76, 0.16) !important;
        }}

        /* Small-screen fallback */
        @media (max-width: 860px) {{
            .isd-ceo-one .isd-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>

    <div class="isd-ceo-one">
        <div class="isd-grid">
            {''.join(site_sections)}
        </div>
    </div>
    """

    return [], None, html


# =========================================================
# SITE SECTION
# =========================================================
def build_site_section(site, start_date, end_date, mpp):
    # colours map preserved, only used for a header accent bar
    colours = {
        "Klipfontein": "#4DA3FF",
        "Gwab": "#00B3A4",
        "Kriel Rehabilitation": "#2ECC71",
        "Koppie": "#F39C12",
        "Uitgevallen": "#9B59B6",
        "Bankfontein": "#E74C3C",
    }

    accent = colours.get(site, "#BDC3C7")

    return f"""
    <div class="isd-site">
        <div class="isd-site-header" style="background: linear-gradient(90deg, {accent} 0%, rgba(0,0,0,0) 70%);">
            <div class="isd-site-title">SITE: {site}</div>
            <div class="isd-site-period">
                PRODUCTION PERIOD: {format_date(start_date)} → {format_date(end_date)}
            </div>
        </div>
        <div class="isd-site-body">
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
# HTML SUMMARY TABLE (LOGIC PRESERVED; VISUALS UPDATED)
# =========================================================
def build_html(mpp, mtd_actual, mtd_coal, mtd_waste, ts, dz):

    def fmt(v):
        return f"{int(round(v)):,}"

    # Previously: inline GREEN/RED backgrounds
    # Now: use theme-friendly classes; logic identical (good vs bad)
    def cell(val, good):
        cls = "isd-good" if good else "isd-bad"
        return f"<td class='{cls}'>{fmt(val)}</td>"

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
