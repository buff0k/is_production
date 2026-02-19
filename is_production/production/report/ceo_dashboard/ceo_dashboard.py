import frappe
from frappe.utils import getdate, now_datetime
from datetime import timedelta

PRODUCTIVITY_RATE = 220

GROUP_A = {"Klipfontein", "Gwab"}
GROUP_B = {"Kriel Rehabilitation", "Bankfontein", "Uitgevallen", "Koppie"}


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
# SITE COLOUR FROM MPP CHILD TABLE (site_colour)
# ==========================================================

def get_site_colour_from_mpp(mpp_doc, site):
    """
    Reads site_colour from ANY MPP child table row that has `site_colour`,
    matching row.site or row.location to the given site.
    Returns None if not found.
    """
    try:
        table_fields = (mpp_doc.meta.get_table_fields() or [])
        for tf in table_fields:
            rows = mpp_doc.get(tf.fieldname) or []
            for r in rows:
                if not hasattr(r, "site_colour"):
                    continue

                row_site = None
                if hasattr(r, "site") and r.site:
                    row_site = r.site
                elif hasattr(r, "location") and r.location:
                    row_site = r.location

                if row_site == site:
                    return r.site_colour or None
    except Exception:
        return None

    return None


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

    return {r.location: float(r.bcm or 0) for r in rows}


def get_monthly_plans_bulk(dmp_rows):
    plans = {}
    for r in dmp_rows:
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
# SCRIPT REPORT EXECUTE (STANDARD TABLE OUTPUT ONLY)
# ==========================================================

def execute(filters=None):
    filters = filters or {}

    dmp_name = filters.get("define_monthly_production")
    if not dmp_name:
        return get_columns(), []

    dmp = frappe.get_doc("Define Monthly Production", dmp_name)
    if not getattr(dmp, "define", None):
        return get_columns(), []

    sites = [r.site for r in dmp.define]
    prod_date = get_production_date()

    mpp_map = get_monthly_plans_bulk(dmp.define)
    today_bcm_map = get_today_bcm_bulk(sites, prod_date)

    data = []

    for row in dmp.define:
        site = row.site
        mpp = mpp_map.get(site)
        if not mpp:
            continue

        # From MPP
        month_target = float(mpp.monthly_target_bcm or 0)
        forecast = float(mpp.month_forecated_bcm or 0)
        forecast_var = forecast - month_target

        prod_days_done = float(mpp.prod_days_completed or 0)
        days_left = float(mpp.month_remaining_production_days or 0)

        original_daily_target = float(mpp.target_bcm_day or 0)

        mtd_actual = float(mpp.month_actual_bcm or 0)
        mtd_coal = float(mpp.month_actual_coal or 0)
        mtd_waste = mtd_actual - (mtd_coal / 1.5)

        current_avg = (mtd_actual / prod_days_done) if prod_days_done else 0.0
        required_daily = ((month_target - mtd_actual) / days_left) if days_left else 0.0

        # Plans (derived same way as your HTML builder)
        days = float(mpp.num_prod_days or 0)
        done = float(mpp.prod_days_completed or 0)

        mtd_plan = (month_target / days * done) if days else 0.0
        coal_plan = (float(mpp.coal_tons_planned or 0) / days * done) if days else 0.0
        waste_plan = (float(mpp.waste_bcms_planned or 0) / days * done) if days else 0.0

        mtd_var = mtd_actual - mtd_plan
        coal_var = mtd_coal - coal_plan
        waste_var = mtd_waste - waste_plan

        # Day BCM / Day Target
        day_bcm = float(today_bcm_map.get(site, 0) or 0)

        productive_hours = get_productive_hours(site)
        day_target = float((mpp.num_excavators or 0) * PRODUCTIVITY_RATE * productive_hours)
        day_var = day_bcm - day_target

        # Site colour from MPP child table
        site_colour = get_site_colour_from_mpp(mpp, site)

        data.append({
            "site": site,
            "prod_start": getdate(row.start_date),
            "prod_end": getdate(row.end_date),
            "site_colour": site_colour or "",

            "month_target_bcm": month_target,
            "forecast_bcm": forecast,
            "forecast_var": forecast_var,
            "days_left": days_left,

            "original_daily_target": original_daily_target,
            "current_avg_per_day": current_avg,
            "required_daily": required_daily,

            "month_coal_t": float(mpp.coal_tons_planned or 0),
            "month_waste_bcm": float(mpp.waste_bcms_planned or 0),

            "mtd_act_bcm": mtd_actual,
            "mtd_plan_bcm": mtd_plan,
            "mtd_var_bcm": mtd_var,

            "mtd_coal_t": mtd_coal,
            "mtd_coal_plan_t": coal_plan,
            "mtd_coal_var_t": coal_var,

            "mtd_waste_bcm": mtd_waste,
            "mtd_waste_plan_bcm": waste_plan,
            "mtd_waste_var_bcm": waste_var,

            "day_bcm": day_bcm,
            "day_target_bcm": day_target,
            "day_var_bcm": day_var,
        })

    return get_columns(), data


def get_columns():
    return [
        {"fieldname": "site", "label": "Site", "fieldtype": "Data", "width": 160},
        {"fieldname": "prod_start", "label": "Prod Start", "fieldtype": "Date", "width": 110},
        {"fieldname": "prod_end", "label": "Prod End", "fieldtype": "Date", "width": 110},
        {"fieldname": "site_colour", "label": "Site Colour", "fieldtype": "Data", "width": 110},

        {"fieldname": "month_target_bcm", "label": "Month Target (bcm)", "fieldtype": "Float", "width": 140},
        {"fieldname": "forecast_bcm", "label": "Forecast (bcm)", "fieldtype": "Float", "width": 130},
        {"fieldname": "forecast_var", "label": "Forecast Var", "fieldtype": "Float", "width": 120},
        {"fieldname": "days_left", "label": "Days Left", "fieldtype": "Int", "width": 90},

        {"fieldname": "original_daily_target", "label": "Original Daily Target", "fieldtype": "Float", "width": 160},
        {"fieldname": "current_avg_per_day", "label": "Current Avg / Day", "fieldtype": "Float", "width": 140},
        {"fieldname": "required_daily", "label": "Required Daily", "fieldtype": "Float", "width": 130},

        {"fieldname": "month_coal_t", "label": "Month Coal (t)", "fieldtype": "Float", "width": 130},
        {"fieldname": "month_waste_bcm", "label": "Month Waste (bcm)", "fieldtype": "Float", "width": 140},

        {"fieldname": "mtd_act_bcm", "label": "MTD Act (bcm)", "fieldtype": "Float", "width": 130},
        {"fieldname": "mtd_plan_bcm", "label": "MTD Plan (bcm)", "fieldtype": "Float", "width": 130},
        {"fieldname": "mtd_var_bcm", "label": "MTD Var", "fieldtype": "Float", "width": 110},

        {"fieldname": "mtd_coal_t", "label": "MTD Coal (t)", "fieldtype": "Float", "width": 130},
        {"fieldname": "mtd_coal_plan_t", "label": "MTD Coal Plan (t)", "fieldtype": "Float", "width": 150},
        {"fieldname": "mtd_coal_var_t", "label": "MTD Coal Var", "fieldtype": "Float", "width": 130},

        {"fieldname": "mtd_waste_bcm", "label": "MTD Waste (bcm)", "fieldtype": "Float", "width": 140},
        {"fieldname": "mtd_waste_plan_bcm", "label": "MTD Waste Plan (bcm)", "fieldtype": "Float", "width": 160},
        {"fieldname": "mtd_waste_var_bcm", "label": "MTD Waste Var", "fieldtype": "Float", "width": 140},

        {"fieldname": "day_bcm", "label": "Day BCM", "fieldtype": "Float", "width": 110},
        {"fieldname": "day_target_bcm", "label": "Day Target (bcm)", "fieldtype": "Float", "width": 150},
        {"fieldname": "day_var_bcm", "label": "Day Var", "fieldtype": "Float", "width": 110},
    ]
