import frappe
from frappe.utils import flt, getdate
from datetime import datetime

REPORT_DOCTYPE = "Monthly Production Planning"
CHILD_DOCTYPE = "Monthly Production Days"
COAL_CONVERSION = 1.5

PLANNING_GROUPS = [
    {
        "key": "group_1",
        "sites": ["Koppie", "Uitgevallen", "Bankfontein"],
    },
    {
        "key": "group_2",
        "sites": ["Klipfontein", "Gwab"],
    },
    {
        "key": "group_3",
        "sites": ["Kriel Rehabilitation"],
    },
]


@frappe.whitelist()
def get_dashboard_data(
    group_1_start_date=None,
    group_1_end_date=None,
    group_2_start_date=None,
    group_2_end_date=None,
    group_3_start_date=None,
    group_3_end_date=None,
):
    groups = {
        "group_1": (group_1_start_date, group_1_end_date),
        "group_2": (group_2_start_date, group_2_end_date),
        "group_3": (group_3_start_date, group_3_end_date),
    }

    rows = []

    for group in PLANNING_GROUPS:
        start_date, end_date = groups[group["key"]]

        if not start_date or not end_date:
            continue

        if getdate(start_date) > getdate(end_date):
            frappe.throw(f"Start Date cannot be after End Date for {group['key']}")

        for site in group["sites"]:
            row = build_site_row(site, end_date)
            if row:
                rows.append(row)

    summary = {
        "total_monthly_target_bcm": round(sum(flt0(r["_summary_monthly_target_bcm"]) for r in rows), 0),
        "total_forecast_bcm": round(sum(flt0(r["_summary_forecast_bcm"]) for r in rows), 0),
        "total_forecast_variance_bcm": round(sum(flt0(r["_summary_forecast_variance_bcm"]) for r in rows), 0),
        "total_waste_variance_bcm": round(sum(flt0(r["_summary_waste_variance_bcm"]) for r in rows), 0),
        "total_coal_variance_tons": round(sum(flt0(r["_summary_coal_variance_tons"]) for r in rows), 0),
    }

    clean_rows = []
    for row in rows:
        item = dict(row)
        for key in list(item.keys()):
            if key.startswith("_summary_"):
                item.pop(key, None)
        clean_rows.append(item)

    return {
        "rows": clean_rows,
        "summary": summary,
    }


def build_site_row(site, report_date):
    mpp = get_monthly_plan(site, report_date)
    if not mpp:
        return None

    month_start = getdate(mpp.prod_month_start_date) if mpp.prod_month_start_date else None
    end_date = getdate(report_date)

    monthly_target = flt0(mpp.monthly_target_bcm)
    waste_bcms_planned = flt0(mpp.waste_bcms_planned)
    coal_tons_planned = flt0(mpp.coal_tons_planned)
    num_prod_days = flt0(mpp.num_prod_days)

    worked_days = get_completed_production_days(mpp.name, month_start, end_date)
    days_left = max(num_prod_days - worked_days, 0)

    # MTD Actual BCM must be flexible according to the selected report date.
    # It sums Monthly Production Days from month start up to the selected end date.
    selected_mtd_actual_bcms = get_mtd_actual_bcms_from_days(mpp.name, month_start, end_date)

    # If the child table has no BCM values, fall back to Monthly Production Planning.
    mtd_actual_bcms = selected_mtd_actual_bcms if selected_mtd_actual_bcms else flt0(mpp.month_actual_bcm)

    # Daily achieved = Actual BCMs / Days Worked
    actual_daily = mtd_actual_bcms / worked_days if worked_days else 0

    mtd_prog_actual_coal = get_mtd_coal_dynamic(site, end_date, month_start)
    mtd_prog_actual_waste = mtd_actual_bcms - (mtd_prog_actual_coal / COAL_CONVERSION)

    mtd_prog_target_waste = (
        (waste_bcms_planned / num_prod_days) * worked_days
        if num_prod_days else 0
    )
    short_over_waste = mtd_prog_target_waste - mtd_prog_actual_waste

    mtd_prog_target_coal = (
        (coal_tons_planned / num_prod_days) * worked_days
        if num_prod_days else 0
    )
    short_over_coal = mtd_prog_target_coal - mtd_prog_actual_coal

    remaining_volume = monthly_target - mtd_actual_bcms
    daily_required = remaining_volume / max(days_left, 1)

    forecast = flt0(mpp.month_forecated_bcm)
    short_over_forecast = monthly_target - forecast

    strip_ratio = round(
        (mtd_prog_actual_waste / mtd_prog_actual_coal)
        if mtd_prog_actual_coal else 0,
        1
    )

    forecast_delivery_percent = (
        (forecast / monthly_target) * 100
        if monthly_target else 0
    )

    # Dashboard sign alignment:
    # Weekly Report shows SHORT / OVER forecast as monthly_target - forecast.
    # Dashboard forecast variance shows forecast - monthly_target, so over-target is positive
    # and under-target is negative, matching the card style currently used.
    forecast_variance_bcm = forecast - monthly_target

    # Weekly Report waste/coal SHORT / OVER uses target - actual, but dashboard variance
    # should show actual - target so that positive means over-achieved/over-actual.
    waste_variance_bcm = mtd_prog_actual_waste - mtd_prog_target_waste
    coal_variance_tons = mtd_prog_actual_coal - mtd_prog_target_coal

    return {
        "site": site,
        "monthly_target_bcm": round(monthly_target, 0),
        "forecast_bcm": round(forecast, 0),
        "forecast_variance_bcm": round(forecast_variance_bcm, 0),
        "waste_variance_bcm": round(waste_variance_bcm, 0),
        "coal_variance_tons": round(coal_variance_tons, 0),
        "actual_bcm": round(mtd_actual_bcms, 0),
        "actual_coal_tons": round(mtd_prog_actual_coal, 0),
        "daily_required_bcm": round(daily_required, 1),
        "daily_achieved_bcm": round(actual_daily, 1),
        "days_worked": cint0(worked_days),
        "days_left": cint0(days_left),
        "strip_ratio": round(strip_ratio, 1),
        "forecast_delivery_percent": round(forecast_delivery_percent, 1),

        "_summary_monthly_target_bcm": round(monthly_target, 0),
        "_summary_forecast_bcm": round(forecast, 0),
        "_summary_forecast_variance_bcm": round(forecast_variance_bcm, 0),
        "_summary_waste_variance_bcm": round(waste_variance_bcm, 0),
        "_summary_coal_variance_tons": round(coal_variance_tons, 0),
    }


def get_monthly_plan(site, date):
    if not site or not date:
        return None

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


def get_completed_production_days(parent_name, month_start, end_date):
    if not parent_name or not month_start or not end_date:
        return 0

    child_rows = frappe.get_all(
        CHILD_DOCTYPE,
        filters={
            "parent": parent_name,
            "shift_start_date": ["between", [month_start, end_date]],
        },
        fields=[
            "shift_start_date",
            "shift_day_hours",
            "shift_night_hours",
            "shift_morning_hours",
            "shift_afternoon_hours",
        ],
    )

    completed_days = 0

    for row in child_rows:
        dt = row.get("shift_start_date")

        if isinstance(dt, str):
            dt = datetime.strptime(dt, "%Y-%m-%d").date()

        # Python weekday: Monday = 0, Sunday = 6.
        if dt and dt.weekday() != 6:
            hours = (
                flt0(row.get("shift_day_hours"))
                + flt0(row.get("shift_night_hours"))
                + flt0(row.get("shift_morning_hours"))
                + flt0(row.get("shift_afternoon_hours"))
            )

            if hours:
                completed_days += 1

    return completed_days


def get_mtd_actual_bcms_from_days(parent_name, month_start, end_date):
    if not parent_name or not month_start or not end_date:
        return 0

    rows = frappe.get_all(
        CHILD_DOCTYPE,
        filters={
            "parent": parent_name,
            "shift_start_date": ["between", [month_start, end_date]],
        },
        fields=["total_daily_bcms"],
    )

    return sum(flt0(row.get("total_daily_bcms")) for row in rows)

def get_mtd_coal_dynamic(site, end_date, month_start):
    if not site or not end_date or not month_start:
        return 0

    survey_doc = frappe.get_all(
        "Survey",
        filters={
            "location": site,
            "last_production_shift_start_date": ["<=", f"{end_date} 23:59:59"],
        },
        fields=["last_production_shift_start_date", "total_surveyed_coal_tons"],
        order_by="last_production_shift_start_date desc",
        limit_page_length=1,
    )

    coal_tons_actual = 0
    end_dt = getdate(end_date)
    start_dt = getdate(month_start)

    if survey_doc:
        survey = survey_doc[0]
        survey_date = survey.get("last_production_shift_start_date")

        if isinstance(survey_date, datetime):
            survey_date = survey_date.date()

        if survey_date and start_dt <= survey_date <= end_dt:
            coal_tons_actual = survey.get("total_surveyed_coal_tons") or 0

            coal_after = frappe.db.sql(
                """
                SELECT COALESCE(SUM(tl.bcms), 0)
                FROM `tabHourly Production` hp
                JOIN `tabTruck Loads` tl ON tl.parent = hp.name
                WHERE hp.prod_date > %s
                  AND hp.prod_date <= %s
                  AND hp.location = %s
                  AND LOWER(tl.mat_type) LIKE '%%coal%%'
                """,
                (survey_date, end_date, site),
            )[0][0]

            coal_tons_actual += (coal_after or 0) * COAL_CONVERSION
        else:
            coal_tons_actual = get_coal_from_hourly(month_start, end_date, site)
    else:
        coal_tons_actual = get_coal_from_hourly(month_start, end_date, site)

    return coal_tons_actual


def get_coal_from_hourly(start_date, end_date, site):
    coal_bcm = frappe.db.sql(
        """
        SELECT COALESCE(SUM(tl.bcms), 0)
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
          AND LOWER(tl.mat_type) LIKE '%%coal%%'
        """,
        (start_date, end_date, site),
    )[0][0]

    return (coal_bcm or 0) * COAL_CONVERSION


def get_actual_daily_bcm(site, date):
    if not site or not date:
        return 0

    result = frappe.db.sql(
        """
        SELECT
            COALESCE(SUM(IFNULL(total_ts_bcm, 0) + IFNULL(total_dozing_bcm, 0)), 0) AS total_bcm
        FROM `tabHourly Production`
        WHERE location = %s
          AND prod_date = %s
        """,
        (site, date),
        as_dict=True,
    )

    return flt0(result[0].get("total_bcm")) if result else 0


def flt0(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def cint0(value):
    try:
        return int(float(value or 0))
    except Exception:
        return 0
