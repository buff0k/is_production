import frappe
from frappe.utils import getdate

REPORT_DOCTYPE = "Monthly Production Planning"
CHILD_DOCTYPE = "Monthly Production Days"
HOURLY_DOCTYPE = "Hourly Production"

COAL_BCM_TO_TONS = 1.5

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
            row = build_site_row(site, start_date, end_date)
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


def build_site_row(site, selected_start_date, selected_end_date):
    planning = get_latest_planning_record(site, selected_start_date, selected_end_date)
    if not planning:
        return None

    month_start = getdate(planning.prod_month_start_date)
    month_end = getdate(planning.prod_month_end_date)
    selected_start = getdate(selected_start_date)
    selected_end = getdate(selected_end_date)

    overlap_start = max(month_start, selected_start)
    overlap_end = min(month_end, selected_end)

    if overlap_start > overlap_end:
        return None

    is_full_month_selection = (overlap_start == month_start and overlap_end == month_end)

    # Full-month values from Monthly Production Planning
    monthly_target_bcm_full = flt0(planning.monthly_target_bcm)
    monthly_forecast_bcm_full = flt0(planning.month_forecated_bcm)
    monthly_actual_bcm_full = flt0(planning.month_actual_bcm)
    monthly_actual_coal_tons_full = flt0(planning.month_actual_coal)
    monthly_coal_tons_planned_full = flt0(planning.coal_tons_planned)
    monthly_waste_bcms_planned_full = flt0(planning.waste_bcms_planned)
    monthly_days_completed = cint0(planning.prod_days_completed)
    monthly_days_left = cint0(planning.month_remaining_production_days)
    monthly_daily_achieved = flt0(planning.mtd_bcm_day)
    monthly_strip_ratio = flt0(planning.split_ratio)

    month_day_counts = get_child_day_counts(planning.name, month_start, month_end)
    overlap_day_counts = get_child_day_counts(planning.name, overlap_start, overlap_end)

    month_planned_days = cint0(month_day_counts["planned_days"])
    selected_planned_days = cint0(overlap_day_counts["planned_days"])

    # Site card target must stay full month unchanged
    site_card_target_bcm = monthly_target_bcm_full

    # Top summary stays full month
    full_month_forecast_variance = monthly_forecast_bcm_full - monthly_target_bcm_full
    full_month_coal_variance = monthly_actual_coal_tons_full - monthly_coal_tons_planned_full
    full_month_waste_variance = (
        (monthly_actual_bcm_full - (monthly_actual_coal_tons_full / COAL_BCM_TO_TONS if monthly_actual_coal_tons_full else 0))
        - monthly_waste_bcms_planned_full
    )

    # FULL MONTH selection -> use parent MPP saved month stats so it matches the MPP screen
    if is_full_month_selection:
        card_forecast_bcm = monthly_forecast_bcm_full
        card_actual_bcm = monthly_actual_bcm_full
        card_actual_coal_tons = monthly_actual_coal_tons_full
        card_coal_variance_tons = full_month_coal_variance
        card_waste_variance_bcm = full_month_waste_variance
        card_forecast_variance_bcm = full_month_forecast_variance
        card_days_worked = monthly_days_completed
        card_days_left = monthly_days_left
        card_daily_achieved_bcm = monthly_daily_achieved
        card_strip_ratio = monthly_strip_ratio
        card_forecast_delivery_percent = (
            (monthly_forecast_bcm_full / monthly_target_bcm_full) * 100
            if monthly_target_bcm_full else 0
        )
        card_daily_required_bcm = (
            monthly_target_bcm_full / month_planned_days if month_planned_days else 0
        )

        return {
            "site": site,
            "monthly_target_bcm": round(site_card_target_bcm, 0),
            "forecast_bcm": round(card_forecast_bcm, 0),
            "forecast_variance_bcm": round(card_forecast_variance_bcm, 0),
            "waste_variance_bcm": round(card_waste_variance_bcm, 0),
            "coal_variance_tons": round(card_coal_variance_tons, 0),
            "actual_bcm": round(card_actual_bcm, 0),
            "actual_coal_tons": round(card_actual_coal_tons, 0),
            "daily_required_bcm": round(card_daily_required_bcm, 1),
            "daily_achieved_bcm": round(card_daily_achieved_bcm, 1),
            "days_worked": card_days_worked,
            "days_left": card_days_left,
            "strip_ratio": round(card_strip_ratio, 1),
            "forecast_delivery_percent": round(card_forecast_delivery_percent, 1),

            "_summary_monthly_target_bcm": round(monthly_target_bcm_full, 0),
            "_summary_forecast_bcm": round(monthly_forecast_bcm_full, 0),
            "_summary_forecast_variance_bcm": round(full_month_forecast_variance, 0),
            "_summary_waste_variance_bcm": round(full_month_waste_variance, 0),
            "_summary_coal_variance_tons": round(full_month_coal_variance, 0),
        }

    # SMALLER SELECTED RANGE -> only inside card values change
    selected_target_bcm = prorate_value(
        monthly_target_bcm_full,
        selected_planned_days,
        month_planned_days
    )
    selected_planned_coal_tons = prorate_value(
        monthly_coal_tons_planned_full,
        selected_planned_days,
        month_planned_days
    )

    selected_planned_coal_bcm = (
        selected_planned_coal_tons / COAL_BCM_TO_TONS if selected_planned_coal_tons else 0
    )
    selected_planned_waste_bcm = selected_target_bcm - selected_planned_coal_bcm

    child_period = get_child_period_metrics(planning.name, overlap_start, overlap_end)
    actual_bcm_from_days = flt0(child_period["actual_bcm"])
    child_worked_days = cint0(child_period["worked_days"])

    hourly_period = get_hourly_period_metrics(site, overlap_start, overlap_end)
    actual_bcm_from_hourly = flt0(hourly_period["actual_bcm"])
    actual_coal_tons_hourly = flt0(hourly_period["actual_coal_tons"])
    hourly_worked_days = cint0(hourly_period["worked_days"])

    coal_tons_from_truck_loads = get_truck_load_coal_tons(site, overlap_start, overlap_end)

    base_actual_bcm = max(actual_bcm_from_hourly, actual_bcm_from_days)
    survey_variance_delta = get_survey_variance_delta(planning.name, overlap_start, overlap_end)

    selected_actual_bcm = base_actual_bcm + survey_variance_delta
    selected_actual_coal_tons = max(actual_coal_tons_hourly, coal_tons_from_truck_loads)

    worked_days = max(hourly_worked_days, child_worked_days)
    days_left = max(selected_planned_days - worked_days, 0)

    selected_forecast_variance_bcm = selected_actual_bcm - selected_target_bcm

    selected_actual_waste_bcm = selected_actual_bcm - (
        selected_actual_coal_tons / COAL_BCM_TO_TONS if selected_actual_coal_tons else 0
    )
    selected_waste_variance_bcm = selected_actual_waste_bcm - selected_planned_waste_bcm
    selected_coal_variance_tons = selected_actual_coal_tons - selected_planned_coal_tons

    daily_required_bcm = (
        selected_target_bcm / selected_planned_days if selected_planned_days else 0
    )
    daily_achieved_bcm = (
        selected_actual_bcm / worked_days if worked_days else 0
    )

    strip_ratio = (
        selected_actual_waste_bcm / selected_actual_coal_tons
        if selected_actual_coal_tons else 0
    )
    forecast_delivery_percent = (
        (selected_actual_bcm / selected_target_bcm) * 100
        if selected_target_bcm else 0
    )

    return {
        "site": site,
        "monthly_target_bcm": round(site_card_target_bcm, 0),
        "forecast_bcm": round(selected_actual_bcm, 0),
        "forecast_variance_bcm": round(selected_forecast_variance_bcm, 0),
        "waste_variance_bcm": round(selected_waste_variance_bcm, 0),
        "coal_variance_tons": round(selected_coal_variance_tons, 0),
        "actual_bcm": round(selected_actual_bcm, 0),
        "actual_coal_tons": round(selected_actual_coal_tons, 0),
        "daily_required_bcm": round(daily_required_bcm, 1),
        "daily_achieved_bcm": round(daily_achieved_bcm, 1),
        "days_worked": worked_days,
        "days_left": days_left,
        "strip_ratio": round(strip_ratio, 1),
        "forecast_delivery_percent": round(forecast_delivery_percent, 1),

        "_summary_monthly_target_bcm": round(monthly_target_bcm_full, 0),
        "_summary_forecast_bcm": round(monthly_forecast_bcm_full, 0),
        "_summary_forecast_variance_bcm": round(full_month_forecast_variance, 0),
        "_summary_waste_variance_bcm": round(full_month_waste_variance, 0),
        "_summary_coal_variance_tons": round(full_month_coal_variance, 0),
    }


def get_latest_planning_record(site, start_date, end_date):
    rows = frappe.db.sql(
        """
        SELECT
            name,
            location,
            prod_month_start_date,
            prod_month_end_date,
            IFNULL(monthly_target_bcm, 0) AS monthly_target_bcm,
            IFNULL(month_forecated_bcm, 0) AS month_forecated_bcm,
            IFNULL(month_actual_bcm, 0) AS month_actual_bcm,
            IFNULL(month_actual_coal, 0) AS month_actual_coal,
            IFNULL(coal_tons_planned, 0) AS coal_tons_planned,
            IFNULL(waste_bcms_planned, 0) AS waste_bcms_planned,
            IFNULL(prod_days_completed, 0) AS prod_days_completed,
            IFNULL(month_remaining_production_days, 0) AS month_remaining_production_days,
            IFNULL(mtd_bcm_day, 0) AS mtd_bcm_day,
            IFNULL(split_ratio, 0) AS split_ratio
        FROM `tabMonthly Production Planning`
        WHERE location = %(site)s
          AND prod_month_end_date >= %(start_date)s
          AND prod_month_start_date <= %(end_date)s
        ORDER BY prod_month_end_date DESC, modified DESC
        LIMIT 1
        """,
        {
            "site": site,
            "start_date": start_date,
            "end_date": end_date,
        },
        as_dict=True,
    )
    return rows[0] if rows else None


def get_child_day_counts(parent_name, start_date, end_date):
    rows = frappe.db.sql(
        f"""
        SELECT
            COUNT(*) AS planned_days
        FROM `tab{CHILD_DOCTYPE}`
        WHERE parent = %(parent)s
          AND parenttype = %(parenttype)s
          AND parentfield = 'month_prod_days'
          AND shift_start_date BETWEEN %(start_date)s AND %(end_date)s
        """,
        {
            "parent": parent_name,
            "parenttype": REPORT_DOCTYPE,
            "start_date": start_date,
            "end_date": end_date,
        },
        as_dict=True,
    )

    row = rows[0] if rows else {}
    return {
        "planned_days": cint0(row.get("planned_days")),
    }


def get_child_period_metrics(parent_name, start_date, end_date):
    rows = frappe.db.sql(
        f"""
        SELECT
            SUM(IFNULL(total_daily_bcms, 0)) AS actual_bcm,
            COUNT(
                CASE
                    WHEN IFNULL(total_daily_bcms, 0) > 0 THEN 1
                    ELSE NULL
                END
            ) AS worked_days
        FROM `tab{CHILD_DOCTYPE}`
        WHERE parent = %(parent)s
          AND parenttype = %(parenttype)s
          AND parentfield = 'month_prod_days'
          AND shift_start_date BETWEEN %(start_date)s AND %(end_date)s
        """,
        {
            "parent": parent_name,
            "parenttype": REPORT_DOCTYPE,
            "start_date": start_date,
            "end_date": end_date,
        },
        as_dict=True,
    )

    row = rows[0] if rows else {}
    return {
        "actual_bcm": flt0(row.get("actual_bcm")),
        "worked_days": cint0(row.get("worked_days")),
    }


def get_cumulative_survey_variance(parent_name, comparator, cutoff_date):
    rows = frappe.db.sql(
        f"""
        SELECT
            (IFNULL(cum_dozing_variance, 0) + IFNULL(cum_ts_variance, 0)) AS cumulative_variance
        FROM `tab{CHILD_DOCTYPE}`
        WHERE parent = %(parent)s
          AND parenttype = %(parenttype)s
          AND parentfield = 'month_prod_days'
          AND shift_start_date {comparator} %(cutoff_date)s
          AND (
              IFNULL(cum_dozing_variance, 0) <> 0
              OR IFNULL(cum_ts_variance, 0) <> 0
          )
        ORDER BY shift_start_date DESC
        LIMIT 1
        """,
        {
            "parent": parent_name,
            "parenttype": REPORT_DOCTYPE,
            "cutoff_date": cutoff_date,
        },
        as_dict=True,
    )

    if not rows:
        return 0

    return flt0(rows[0].get("cumulative_variance"))


def get_survey_variance_delta(parent_name, start_date, end_date):
    end_cumulative = get_cumulative_survey_variance(parent_name, "<=", end_date)
    before_start_cumulative = get_cumulative_survey_variance(parent_name, "<", start_date)
    return end_cumulative - before_start_cumulative


def get_hourly_period_metrics(site, start_date, end_date):
    rows = frappe.db.sql(
        f"""
        SELECT
            SUM(IFNULL(total_ts_bcm, 0) + IFNULL(total_dozing_bcm, 0)) AS actual_bcm,
            SUM(IFNULL(coal_tons_total, 0)) AS actual_coal_tons,
            COUNT(
                DISTINCT CASE
                    WHEN (IFNULL(total_ts_bcm, 0) + IFNULL(total_dozing_bcm, 0)) > 0
                    THEN prod_date
                    ELSE NULL
                END
            ) AS worked_days
        FROM `tab{HOURLY_DOCTYPE}`
        WHERE location = %(site)s
          AND prod_date BETWEEN %(start_date)s AND %(end_date)s
        """,
        {
            "site": site,
            "start_date": start_date,
            "end_date": end_date,
        },
        as_dict=True,
    )

    row = rows[0] if rows else {}
    return {
        "actual_bcm": flt0(row.get("actual_bcm")),
        "actual_coal_tons": flt0(row.get("actual_coal_tons")),
        "worked_days": cint0(row.get("worked_days")),
    }


def get_truck_load_coal_tons(site, start_date, end_date):
    rows = frappe.db.sql(
        """
        SELECT
            SUM(IFNULL(tl.bcms, 0)) AS coal_bcm
        FROM `tabHourly Production` hp
        INNER JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.location = %(site)s
          AND hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND LOWER(IFNULL(tl.mat_type, '')) LIKE '%%coal%%'
        """,
        {
            "site": site,
            "start_date": start_date,
            "end_date": end_date,
        },
        as_dict=True,
    )

    coal_bcm = flt0(rows[0].get("coal_bcm")) if rows else 0
    return coal_bcm * COAL_BCM_TO_TONS


def prorate_value(full_value, selected_days, full_days):
    if not full_days or full_days <= 0:
        return 0
    return full_value * (selected_days / full_days)


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