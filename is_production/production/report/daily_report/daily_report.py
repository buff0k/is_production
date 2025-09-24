import frappe
import calendar
from frappe.utils import getdate, nowdate


def execute(filters=None):
    columns = get_columns()
    data = [get_report_data(filters)]
    return columns, data


def get_columns():
    return [
        {"label": "Monthly Target (BCM)", "fieldname": "monthly_target_bcm", "fieldtype": "Float", "width": 160},
        {"label": "Monthly Coal Target (Tons)", "fieldname": "coal_tons_planned", "fieldtype": "Float", "width": 200},
        {"label": "MTD Coal (Tons)", "fieldname": "mtd_coal", "fieldtype": "Float", "width": 160},
        {"label": "Forecasted Value (BCM)", "fieldname": "forecasted_value", "fieldtype": "Float", "width": 200},
        {"label": "Actual Total BCM MTD", "fieldname": "actual_bcm_mtd", "fieldtype": "Float", "width": 200},
        {"label": "Remaining Volume (BCM)", "fieldname": "remaining_volume", "fieldtype": "Float", "width": 200},
        {"label": "Daily Target (BCM)", "fieldname": "target_bcm_day", "fieldtype": "Float", "width": 160},
        {"label": "Dozing Tallies (BCM)", "fieldname": "dozing_tallies", "fieldtype": "Float", "width": 180},
        {"label": "TS Tallies (BCM)", "fieldname": "ts_tallies", "fieldtype": "Float", "width": 150},
        {"label": "Total BCM (BCM)", "fieldname": "total_bcm", "fieldtype": "Float", "width": 150},
        {"label": "Excavator Hours", "fieldname": "excavator_hours", "fieldtype": "Float", "width": 160},
        {"label": "Dozer Hours", "fieldname": "dozer_hours", "fieldtype": "Float", "width": 160},
    ]


def get_report_data(filters):
    site = filters.get("site")
    start_date = filters.get("start_date")
    end_date = filters.get("end_date") or nowdate()

    # --- Monthly Planning values (SQL instead of get_all) ---
    planning_conditions = ["posting_date BETWEEN %s AND %s"]
    params = [start_date, end_date]
    if site and frappe.db.has_column("Monthly Production Planning", "site"):
        planning_conditions.append("site = %s")
        params.insert(0, site)

    planning = frappe.db.sql(f"""
        SELECT monthly_target_bcm, coal_tons_planned, target_bcm_day
        FROM `tabMonthly Production Planning`
        WHERE {" AND ".join(planning_conditions)}
        ORDER BY posting_date DESC
        LIMIT 1
    """, tuple(params), as_dict=True)

    monthly_target_bcm = planning[0].monthly_target_bcm if planning else 0
    coal_tons_planned = planning[0].coal_tons_planned if planning else 0
    daily_target = planning[0].target_bcm_day if planning else 0

    # --- Latest Survey ---
    survey_conditions = ["posting_date BETWEEN %s AND %s"]
    params = [start_date, end_date]
    if site and frappe.db.has_column("Survey", "site"):
        survey_conditions.append("site = %s")
        params.insert(0, site)

    survey = frappe.db.sql(f"""
        SELECT posting_date, total_surveyed_coal_tons, total_surveyed_bcm
        FROM `tabSurvey`
        WHERE {" AND ".join(survey_conditions)}
        ORDER BY posting_date DESC
        LIMIT 1
    """, tuple(params), as_dict=True)

    survey_date, surveyed_coal, surveyed_bcm = None, 0, 0
    if survey:
        survey_date = survey[0].posting_date
        surveyed_coal = survey[0].total_surveyed_coal_tons or 0
        surveyed_bcm = survey[0].total_surveyed_bcm or 0

    # --- Hourly Production ---
    hp_conditions = ["posting_date BETWEEN %s AND %s"]
    hp_params = [start_date, end_date]
    if site and frappe.db.has_column("Hourly Production", "site"):
        hp_conditions.append("site = %s")
        hp_params.insert(0, site)
    if survey_date:
        hp_conditions.append("posting_date > %s")
        hp_params.append(survey_date)

    hp_data = frappe.db.sql(f"""
        SELECT
            SUM(coal_tons_total) as coal,
            SUM(total_softs_bcm + total_hards_bcm + total_coal_bcm) as bcm,
            SUM(total_dozing_bcm) as dozing,
            SUM(total_ts_bcm) as ts
        FROM `tabHourly Production`
        WHERE {" AND ".join(hp_conditions)}
    """, tuple(hp_params), as_dict=True)[0]

    coal_sum = hp_data.coal or 0
    bcm_from_hourly = hp_data.bcm or 0
    dozing_tallies = hp_data.dozing or 0
    ts_tallies = hp_data.ts or 0

    # --- Combine survey + hourly ---
    mtd_coal = (surveyed_coal + coal_sum) if survey_date else coal_sum
    actual_bcm_mtd = (surveyed_bcm + bcm_from_hourly) if survey_date else bcm_from_hourly

    # --- Remaining volume ---
    remaining_volume = monthly_target_bcm - actual_bcm_mtd

    # --- Total BCM ---
    total_bcm = dozing_tallies + ts_tallies

    # --- Pre Use Hours ---
    pre_conditions = ["posting_date BETWEEN %s AND %s"]
    pre_params = [start_date, end_date]
    if site and frappe.db.has_column("Pre Use Asset", "site"):
        pre_conditions.append("site = %s")
        pre_params.insert(0, site)

    pre_use = frappe.db.sql(f"""
        SELECT plant_category, SUM(working_hours) as hours
        FROM `tabPre Use Asset`
        WHERE {" AND ".join(pre_conditions)}
        GROUP BY plant_category
    """, tuple(pre_params), as_dict=True)

    excavator_hours = sum(x.hours for x in pre_use if x.plant_category == "Excavator")
    dozer_hours = sum(x.hours for x in pre_use if x.plant_category == "Dozer")

    # --- Forecasted value (performance projection) ---
    days_passed = (getdate(end_date) - getdate(start_date)).days + 1
    days_in_month = calendar.monthrange(getdate(start_date).year, getdate(start_date).month)[1]
    forecasted_value = 0
    if days_passed > 0:
        forecasted_value = (actual_bcm_mtd / days_passed) * days_in_month

    return {
        "monthly_target_bcm": monthly_target_bcm or 0,
        "coal_tons_planned": coal_tons_planned or 0,
        "mtd_coal": mtd_coal or 0,
        "forecasted_value": forecasted_value or 0,
        "actual_bcm_mtd": actual_bcm_mtd or 0,
        "remaining_volume": remaining_volume or 0,
        "target_bcm_day": daily_target or 0,
        "dozing_tallies": dozing_tallies or 0,
        "ts_tallies": ts_tallies or 0,
        "total_bcm": total_bcm or 0,
        "excavator_hours": excavator_hours or 0,
        "dozer_hours": dozer_hours or 0
    }


