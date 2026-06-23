# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, now_datetime
from datetime import timedelta


GROUP_A = {"Klipfontein", "Gwab"}
GROUP_B = {"Kriel Rehabilitation", "Bankfontein", "Uitgevallen", "Koppie"}
PRODUCTIVITY_RATE = 220


def flt(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def get_columns():
    return [
        {"fieldname": "site", "label": "Site", "fieldtype": "Data", "width": 180},
        {"fieldname": "prod_start", "label": "Production Start", "fieldtype": "Date", "width": 120},
        {"fieldname": "prod_end", "label": "Production End", "fieldtype": "Date", "width": 120},

        {"fieldname": "month_target_bcm", "label": "Month Target (bcm)", "fieldtype": "Float", "width": 140},
        {"fieldname": "forecast_bcm", "label": "Forecast (bcm)", "fieldtype": "Float", "width": 130},
        {"fieldname": "forecast_var", "label": "Forecast Variance", "fieldtype": "Float", "width": 130},
        {"fieldname": "days_left", "label": "Days Left", "fieldtype": "Float", "width": 100},
        {"fieldname": "original_daily_target", "label": "Original Daily Target", "fieldtype": "Float", "width": 150},
        {"fieldname": "current_avg_per_day", "label": "Current Avg / Day", "fieldtype": "Float", "width": 150},
        {"fieldname": "required_daily", "label": "Required Daily", "fieldtype": "Float", "width": 130},

        {"fieldname": "month_coal_t", "label": "Month Coal (t)", "fieldtype": "Float", "width": 130},
        {"fieldname": "month_waste_bcm", "label": "Month Waste (bcm)", "fieldtype": "Float", "width": 140},

        {"fieldname": "mtd_act_bcm", "label": "MTD Actual (bcm)", "fieldtype": "Float", "width": 140},
        {"fieldname": "mtd_plan_bcm", "label": "MTD Plan (bcm)", "fieldtype": "Float", "width": 130},
        {"fieldname": "mtd_var_bcm", "label": "MTD Variance", "fieldtype": "Float", "width": 130},

        {"fieldname": "mtd_coal_t", "label": "MTD Coal (t)", "fieldtype": "Float", "width": 130},
        {"fieldname": "mtd_coal_plan_t", "label": "MTD Coal Plan (t)", "fieldtype": "Float", "width": 150},
        {"fieldname": "mtd_coal_var_t", "label": "MTD Coal Variance", "fieldtype": "Float", "width": 150},

        {"fieldname": "mtd_waste_bcm", "label": "MTD Waste (bcm)", "fieldtype": "Float", "width": 150},
        {"fieldname": "mtd_waste_plan_bcm", "label": "MTD Waste Plan (bcm)", "fieldtype": "Float", "width": 160},
        {"fieldname": "mtd_waste_var_bcm", "label": "MTD Waste Variance", "fieldtype": "Float", "width": 160},

        {"fieldname": "day_bcm", "label": "Day BCM", "fieldtype": "Float", "width": 120},
        {"fieldname": "day_target_bcm", "label": "Day Target (bcm)", "fieldtype": "Float", "width": 140},
        {"fieldname": "day_var_bcm", "label": "Day Variance", "fieldtype": "Float", "width": 130},

        {"fieldname": "employee_count", "label": "Employees", "fieldtype": "Int", "width": 100},
        {"fieldname": "bcm_per_man", "label": "BCM / Man", "fieldtype": "Float", "width": 120},
        {"fieldname": "projected_bcm_per_man", "label": "Projected BCM / Man", "fieldtype": "Float", "width": 160},
    ]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    dmp_name = filters.get("define_monthly_production")

    if not dmp_name:
        return get_columns(), []

    dmp = frappe.get_doc("Define Monthly Production", dmp_name)
    define_rows = list(dmp.get("define") or [])

    if not define_rows:
        return get_columns(), []

    sites = [(row.site or "").strip() for row in define_rows if row.site]
    sites = [site for site in sites if site]

    if not sites:
        return get_columns(), []

    prod_date = get_production_date()

    monthly_plans = get_monthly_plans_bulk(define_rows)
    today_bcm_map = get_today_bcm_bulk(sites, prod_date)
    employee_count_map = get_active_employee_count_bulk(sites)

    data = []

    for define_row in define_rows:
        site = (define_row.site or "").strip()

        if not site:
            continue

        mpp = monthly_plans.get(site)

        if not mpp:
            continue

        data.append(
            build_data_row(
                site=site,
                prod_start=getdate(define_row.start_date) if define_row.start_date else None,
                prod_end=getdate(define_row.end_date) if define_row.end_date else None,
                mpp=mpp,
                day_bcm=today_bcm_map.get(site, 0),
                employee_count=employee_count_map.get(site, 0),
            )
        )

    return get_columns(), data


# ==========================================================
# Production date/window logic: production day is 06:00 -> 06:00
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


def get_productive_hours(site):
    start_dt, now = get_production_window()
    weekday = start_dt.weekday()  # Mon=0, Sun=6

    if site in GROUP_A:
        if weekday == 6:
            work_end = start_dt.replace(hour=14)
        else:
            work_end = start_dt + timedelta(days=1)
    else:
        if weekday == 6:
            return 0

        if weekday == 5:
            work_end = start_dt.replace(hour=0) + timedelta(days=1)
        else:
            work_end = start_dt + timedelta(days=1)

    effective_end = min(now, work_end)

    excluded_slots = {
        (6, 7),
        (7, 8),
        (13, 14),
        (1, 2),
    }

    productive = 0
    cursor = start_dt

    while cursor + timedelta(hours=1) <= effective_end:
        slot = (cursor.hour, (cursor.hour + 1) % 24)

        if slot not in excluded_slots:
            productive += 1

        cursor += timedelta(hours=1)

    return productive


# ==========================================================
# Data access
# ==========================================================

def get_today_bcm_bulk(sites, prod_date):
    if not sites:
        return {}

    rows = frappe.db.sql(
        """
        SELECT
            location,
            SUM(total_ts_bcm + total_dozing_bcm) AS bcm
        FROM `tabHourly Production`
        WHERE location IN %(sites)s
          AND prod_date = %(prod_date)s
        GROUP BY location
        """,
        {
            "sites": tuple(sites),
            "prod_date": prod_date,
        },
        as_dict=True,
    )

    return {
        row.location: flt(row.bcm)
        for row in rows
    }


def get_monthly_plans_bulk(define_rows):
    plans = {}

    for row in define_rows:
        site = (row.site or "").strip()

        if not site or not row.end_date:
            continue

        name = frappe.db.get_value(
            "Monthly Production Planning",
            {
                "location": site,
                "prod_month_start_date": ["<=", row.end_date],
                "prod_month_end_date": [">=", row.end_date],
            },
            "name",
            order_by="modified desc",
        )

        if name:
            plans[site] = frappe.get_doc("Monthly Production Planning", name)

    return plans


def get_active_employee_count_bulk(sites):
    if not sites:
        return {}

    rows = frappe.db.sql(
        """
        SELECT
            branch AS site,
            COUNT(name) AS employee_count
        FROM `tabEmployee`
        WHERE status = 'Active'
          AND branch IN %(sites)s
        GROUP BY branch
        """,
        {
            "sites": tuple(sites),
        },
        as_dict=True,
    )

    return {
        row.site: int(row.employee_count or 0)
        for row in rows
    }


# ==========================================================
# Row builder
# ==========================================================

def build_data_row(site, prod_start, prod_end, mpp, day_bcm, employee_count):
    month_target = flt(mpp.get("monthly_target_bcm"))
    forecast = flt(mpp.get("month_forecated_bcm"))
    forecast_var = forecast - month_target

    month_coal = flt(mpp.get("coal_tons_planned"))
    month_waste = flt(mpp.get("waste_bcms_planned"))

    mtd_actual = flt(mpp.get("month_actual_bcm"))
    mtd_coal = flt(mpp.get("month_actual_coal"))
    mtd_waste = mtd_actual - (mtd_coal / 1.5 if mtd_coal else 0)

    total_prod_days = flt(mpp.get("num_prod_days"))
    prod_days_done = flt(mpp.get("prod_days_completed"))
    days_left = flt(mpp.get("month_remaining_production_days"))

    mtd_plan = (month_target / total_prod_days * prod_days_done) if total_prod_days else 0
    coal_plan = (month_coal / total_prod_days * prod_days_done) if total_prod_days else 0
    waste_plan = (month_waste / total_prod_days * prod_days_done) if total_prod_days else 0

    mtd_var = mtd_actual - mtd_plan
    coal_var = mtd_coal - coal_plan
    waste_var = mtd_waste - waste_plan

    productive_hours = get_productive_hours(site)
    day_target = flt(mpp.get("num_excavators")) * PRODUCTIVITY_RATE * productive_hours
    day_var = flt(day_bcm) - day_target

    current_avg = (mtd_actual / prod_days_done) if prod_days_done else 0
    required_daily = ((month_target - mtd_actual) / days_left) if days_left else 0

    original_daily_target = flt(mpp.get("target_bcm_day"))

    bcm_per_man = (mtd_actual / employee_count) if employee_count else 0
    projected_bcm_per_man = (forecast / employee_count) if employee_count else 0

    return {
        "site": site,
        "prod_start": prod_start,
        "prod_end": prod_end,

        "month_target_bcm": month_target,
        "forecast_bcm": forecast,
        "forecast_var": forecast_var,
        "days_left": days_left,
        "original_daily_target": original_daily_target,
        "current_avg_per_day": current_avg,
        "required_daily": required_daily,

        "month_coal_t": month_coal,
        "month_waste_bcm": month_waste,

        "mtd_act_bcm": mtd_actual,
        "mtd_plan_bcm": mtd_plan,
        "mtd_var_bcm": mtd_var,

        "mtd_coal_t": mtd_coal,
        "mtd_coal_plan_t": coal_plan,
        "mtd_coal_var_t": coal_var,

        "mtd_waste_bcm": mtd_waste,
        "mtd_waste_plan_bcm": waste_plan,
        "mtd_waste_var_bcm": waste_var,

        "day_bcm": flt(day_bcm),
        "day_target_bcm": day_target,
        "day_var_bcm": day_var,

        "employee_count": employee_count,
        "month_actual_bcm_source": mtd_actual,
        "month_forecated_bcm_source": forecast,
        "bcm_per_man": bcm_per_man,
        "projected_bcm_per_man": projected_bcm_per_man,
    }