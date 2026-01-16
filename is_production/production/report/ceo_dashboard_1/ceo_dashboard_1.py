import frappe
from frappe.utils import format_date, getdate, now_datetime
from datetime import timedelta, datetime

GREEN = "#C9F2D8"
RED = "#F9CACA"
HEADER_BG = "#EEF4FB"

SITE_COLOURS = {
    "Klipfontein": "#55A7FF",
    "Gwab": "#ECE6F5",
    "Kriel Rehabilitation": "#2ECC71",
    "Koppie": "#F5A623",
    "Uitgevallen": "#1ABC9C",
    "Bankfontein": "#F1C40F",
}

GROUP_A = {"Klipfontein", "Gwab"}
GROUP_B = {"Kriel Rehabilitation", "Bankfontein", "Uitgevallen", "Koppie"}

PRODUCTIVITY_RATE = 220

# ==========================================================
# PRODUCTION DATE (06:00 → 06:00)
# ==========================================================

def get_production_date():
    now = now_datetime()
    six_am = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now < six_am:
        return (now - timedelta(days=1)).date()
    return now.date()


def get_production_window():
    now = now_datetime()
    start = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now < start:
        start -= timedelta(days=1)
    return start, now


# ==========================================================
# PRODUCTIVE HOURS LOGIC
# ==========================================================

def get_productive_hours(site):
    start_dt, now = get_production_window()
    weekday = start_dt.weekday()  # Mon=0

    # ---- determine work end ----
    if site in GROUP_A:
        if weekday == 6:  # Sunday
            work_end = start_dt.replace(hour=14)
        else:
            work_end = start_dt + timedelta(days=1)
    else:
        if weekday == 6:  # Sunday
            return 0
        elif weekday == 5:  # Saturday
            work_end = start_dt.replace(hour=0) + timedelta(days=1)
        else:
            work_end = start_dt + timedelta(days=1)

    effective_end = min(now, work_end)

    excluded = {
        (6, 7), (7, 8),   # startup
        (13, 14),         # lunch
        (1, 2),           # fatigue
    }

    productive = 0
    cursor = start_dt

    while cursor + timedelta(hours=1) <= effective_end:
        slot = (cursor.hour, (cursor.hour + 1) % 24)
        if slot not in excluded:
            productive += 1
        cursor += timedelta(hours=1)

    return productive


# ==========================================================
# MAIN EXECUTE
# ==========================================================

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
    prod_date = get_production_date()

    start_date = min(r.start_date for r in dmp.define)
    end_date = max(r.end_date for r in dmp.define)

    mpp_map = get_monthly_plans_bulk(dmp.define)
    today_bcm_map = get_today_bcm_bulk(sites, prod_date)

    survey_map = get_latest_coal_surveys_bulk(
        sites, start_date, end_date
    )

    mtd_coal_map = get_mtd_coal_bulk(
        sites, start_date, end_date, survey_map
    )

    site_sections = []

    for row in dmp.define:
        mpp = mpp_map.get(row.site)
        if not mpp:
            continue

        day_bcm = today_bcm_map.get(row.site, 0)

        mtd_actual = mpp.month_actual_bcm or 0
        mtd_coal = mtd_coal_map.get(row.site, 0)
        mtd_waste = mtd_actual - (mtd_coal / 1.5)

        productive_hours = get_productive_hours(row.site)

        day_target = (
            (mpp.num_excavators or 0)
            * PRODUCTIVITY_RATE
            * productive_hours
        )

        site_sections.append(
            build_site_section(
                row.site,
                getdate(row.start_date),
                getdate(row.end_date),
                mpp,
                mtd_actual,
                mtd_coal,
                mtd_waste,
                day_bcm,
                day_target
            )
        )

    html = f"""
    <style>
        body {{
            font-family: Arial, Helvetica, sans-serif;
            font-weight: bold;
            color: #002244;
        }}

        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(900px, 1fr));
            gap: 10px;
        }}

        .site-section {{
            border: 4px solid #000;
            background: #ffffff;
        }}

        .kpi-bar {{
            display: flex;
            gap: 6px;
            margin-top: 6px;
            flex-wrap: wrap;
        }}

        .kpi-box {{
            background: white;
            border: 2px solid #000;
            padding: 6px 10px;
            text-align: center;
            min-width: 120px;
        }}

        table.summary-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}

        table.summary-table th {{
            background: {HEADER_BG};
            border: 1px solid #000;
            padding: 6px;
            text-align: center;
        }}

        table.summary-table td {{
            border: 1px solid #000;
            padding: 4px 6px;
            text-align: right;
        }}
    </style>

    <div class="dashboard-grid">
        {''.join(site_sections)}
    </div>
    """

    return [], None, html


# ==========================================================
# BULK QUERIES
# ==========================================================

def get_today_bcm_bulk(sites, prod_date):
    rows = frappe.db.sql("""
        SELECT location,
               SUM(total_ts_bcm + total_dozing_bcm) AS bcm
        FROM `tabHourly Production`
        WHERE location IN %(sites)s
          AND prod_date = %(prod_date)s
        GROUP BY location
    """, {"sites": sites, "prod_date": prod_date}, as_dict=True)

    return {r.location: r.bcm or 0 for r in rows}


def get_latest_coal_surveys_bulk(sites, start_date, end_date):
    rows = frappe.db.sql("""
        SELECT s.location,
               s.survey_datetime,
               s.total_surveyed_coal_tons
        FROM `tabSurvey` s
        INNER JOIN (
            SELECT location,
                   MAX(survey_datetime) AS max_dt
            FROM `tabSurvey`
            WHERE location IN %(sites)s
              AND DATE(survey_datetime) BETWEEN %(start)s AND %(end)s
            GROUP BY location
        ) latest
        ON latest.location = s.location
       AND latest.max_dt = s.survey_datetime
    """, {
        "sites": sites,
        "start": start_date,
        "end": end_date
    }, as_dict=True)

    return {
        r.location: {
            "survey_date": r.survey_datetime.date(),
            "survey_tons": r.total_surveyed_coal_tons or 0
        }
        for r in rows
    }


def get_mtd_coal_bulk(sites, start_date, end_date, survey_map):
    rows = frappe.db.sql("""
        SELECT hp.location,
               hp.prod_date,
               SUM(
                   CASE WHEN LOWER(tl.mat_type) LIKE '%%coal%%'
                   THEN tl.bcms ELSE 0 END
               ) AS coal_bcm
        FROM `tabHourly Production` hp
        LEFT JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.location IN %(sites)s
          AND hp.prod_date BETWEEN %(start)s AND %(end)s
        GROUP BY hp.location, hp.prod_date
    """, {
        "sites": sites,
        "start": start_date,
        "end": end_date
    }, as_dict=True)

    bcm_map = {}

    for r in rows:
        survey = survey_map.get(r.location)
        if survey and r.prod_date <= survey["survey_date"]:
            continue
        bcm_map.setdefault(r.location, 0)
        bcm_map[r.location] += r.coal_bcm or 0

    mtd_map = {}
    for site in sites:
        survey = survey_map.get(site)
        post_survey_tons = bcm_map.get(site, 0) * 1.5
        mtd_map[site] = (
            survey["survey_tons"] + post_survey_tons
            if survey else post_survey_tons
        )

    return mtd_map


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
            plans[r.site] = frappe.get_doc("Monthly Production Planning", name)
    return plans


# ==========================================================
# HTML BUILDERS
# ==========================================================

def build_site_section(site, start_date, end_date, mpp,
                       mtd_actual, mtd_coal, mtd_waste,
                       day_bcm, day_target):

    def fmt(v): return f"{int(round(v)):,}"

    forecast = mpp.month_forecated_bcm or 0
    month_target = mpp.monthly_target_bcm or 0
    forecast_var = forecast - month_target

    prod_days_done = mpp.prod_days_completed or 0
    days_left = mpp.month_remaining_production_days or 0

    current_avg = (mtd_actual / prod_days_done) if prod_days_done else 0
    required_daily = (
        (month_target - mtd_actual) / days_left
    ) if days_left else 0

    bg = SITE_COLOURS.get(site, "#BDC3C7")

    return f"""
    <div class="site-section">
        <div style="padding:8px;background:{bg};">
            <div style="font-size:17px;">SITE: {site}</div>
            <div style="font-size:12px;">
                PRODUCTION PERIOD: {format_date(start_date)} → {format_date(end_date)}
            </div>

            <div class="kpi-bar">
                {kpi("Month Target", month_target)}
                {kpi("Forecast", forecast)}
                {kpi("Var", forecast_var, True)}
                {kpi("Days Left", days_left)}
                {kpi("Original Daily Target", mpp.target_bcm_day)}
                {kpi("Current Avg / Day", current_avg)}
                {kpi("Required Daily for Target", required_daily)}
            </div>
        </div>

        <div style="padding:6px;">
            {build_html(mpp, mtd_actual, mtd_coal, mtd_waste, day_bcm, day_target)}
        </div>
    </div>
    """


def kpi(label, value, coloured=False):
    bg = GREEN if value >= 0 else RED
    style = f"background:{bg};" if coloured else ""
    return f"""
    <div class="kpi-box" style="{style}">
        <div style="font-size:11px;">{label}</div>
        <div style="font-size:16px;">{int(round(value)):,}</div>
    </div>
    """


def build_html(mpp, mtd_actual, mtd_coal, mtd_waste, day_bcm, day_target):

    def fmt(v): return f"{int(round(v)):,}"
    def var_cell(v):
        return f"<td style='background:{GREEN if v >= 0 else RED};'>{fmt(v)}</td>"

    days = mpp.num_prod_days
    done = mpp.prod_days_completed

    mtd_plan = mpp.monthly_target_bcm / days * done if days else 0
    coal_plan = mpp.coal_tons_planned / days * done if days else 0
    waste_plan = mpp.waste_bcms_planned / days * done if days else 0

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
            <td>{fmt(mpp.monthly_target_bcm)}</td>
            <td>{fmt(mpp.coal_tons_planned)}</td>
            <td>{fmt(mpp.waste_bcms_planned)}</td>

            <td>{fmt(mtd_actual)}</td>
            <td>{fmt(mtd_plan)}</td>
            {var_cell(mtd_actual - mtd_plan)}

            <td>{fmt(mtd_coal)}</td>
            <td>{fmt(coal_plan)}</td>
            {var_cell(mtd_coal - coal_plan)}

            <td>{fmt(mtd_waste)}</td>
            <td>{fmt(waste_plan)}</td>
            {var_cell(mtd_waste - waste_plan)}

            <td>{fmt(day_bcm)}</td>
            <td>{fmt(day_target)}</td>
            {var_cell(day_bcm - day_target)}
        </tr>
    </table>
    """
