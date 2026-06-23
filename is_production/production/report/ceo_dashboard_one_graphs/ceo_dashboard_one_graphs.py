# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt


import frappe
from frappe.utils import getdate, nowdate
from datetime import timedelta


Y_AXIS_STEP = 10_000


def execute(filters=None):
    filters = frappe._dict(filters or {})

    define_monthly_production = (
        filters.get("define_monthly_production")
        or filters.get("monthly_production_plan")
    )

    if not define_monthly_production:
        return get_columns(), []

    yesterday = getdate(nowdate()) - timedelta(days=1)

    dmp = frappe.get_doc("Define Monthly Production", define_monthly_production)
    define_rows = list(dmp.get("define") or [])

    if not define_rows:
        return get_columns(), []

    monthly_plan_map = get_monthly_plans(define_rows)

    data = []

    for idx, define_row in enumerate(define_rows):
        site = (define_row.site or "").strip()

        if not site:
            continue

        monthly_plan = monthly_plan_map.get(site)

        if not monthly_plan:
            continue

        prod_start = getdate(monthly_plan.prod_month_start_date)
        prod_end = getdate(monthly_plan.prod_month_end_date)

        labels, dates = build_date_axis(prod_start, prod_end)

        cumulative_actual_map = extract_cumulative_actuals_mtd(
            monthly_plan.get("month_prod_days") or [],
            prod_start,
            prod_end,
            yesterday,
        )

        monthly_target = monthly_plan.get("monthly_target_bcm") or 0

        mtd_target_data = build_mtd_target(
            monthly_target=monthly_target,
            days=len(labels),
        )

        mtd_actual_data = build_mtd_actual(
            dates=dates,
            cumulative_actual_map=cumulative_actual_map,
            cutoff=yesterday,
        )

        data.append({
            "site": site,
            "site_order": idx,
            "prod_start": prod_start,
            "prod_end": prod_end,
            "mtd_upto": yesterday,
            "monthly_target_bcm": monthly_target,
            "chart_labels": frappe.as_json(labels),
            "mtd_target_data": frappe.as_json(mtd_target_data),
            "mtd_actual_data": frappe.as_json(mtd_actual_data),
            "y_axis_step": Y_AXIS_STEP,
        })

    return get_columns(), data


def get_columns():
    return [
        {
            "fieldname": "site",
            "label": "Site",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "fieldname": "site_order",
            "label": "Site Order",
            "fieldtype": "Int",
            "width": 90,
            "hidden": 1,
        },
        {
            "fieldname": "prod_start",
            "label": "Production Start",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "fieldname": "prod_end",
            "label": "Production End",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "fieldname": "mtd_upto",
            "label": "MTD Up To",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "fieldname": "monthly_target_bcm",
            "label": "Monthly Target BCM",
            "fieldtype": "Float",
            "width": 150,
        },
        {
            "fieldname": "chart_labels",
            "label": "Chart Labels",
            "fieldtype": "Long Text",
            "width": 80,
            "hidden": 1,
        },
        {
            "fieldname": "mtd_target_data",
            "label": "MTD Target Data",
            "fieldtype": "Long Text",
            "width": 80,
            "hidden": 1,
        },
        {
            "fieldname": "mtd_actual_data",
            "label": "MTD Actual Data",
            "fieldtype": "Long Text",
            "width": 80,
            "hidden": 1,
        },
        {
            "fieldname": "y_axis_step",
            "label": "Y Axis Step",
            "fieldtype": "Int",
            "width": 80,
            "hidden": 1,
        },
    ]


def extract_cumulative_actuals_mtd(rows, prod_start, prod_end, cutoff):
    actuals = {}

    for row in rows:
        if not row.shift_start_date:
            continue

        production_date = getdate(row.shift_start_date)

        if production_date < prod_start:
            continue

        if production_date > prod_end:
            continue

        if production_date > cutoff:
            continue

        actuals[production_date] = round(
            (row.cum_ts_bcms or 0)
            + (row.tot_cumulative_dozing_bcms or 0),
            2,
        )

    return actuals


def build_mtd_actual(dates, cumulative_actual_map, cutoff):
    return [
        None if production_date > cutoff else cumulative_actual_map.get(production_date)
        for production_date in dates
    ]


def build_mtd_target(monthly_target, days):
    monthly_target = float(monthly_target or 0)
    daily_target = monthly_target / days if days else 0

    running_total = 0
    values = []

    for _ in range(days):
        running_total += daily_target
        values.append(round(running_total, 2))

    return values


def build_date_axis(start, end):
    labels = []
    dates = []

    current = start

    while current <= end:
        labels.append(str(current.day))
        dates.append(current)
        current += timedelta(days=1)

    return labels, dates


def get_monthly_plans(rows):
    plans = {}

    for row in rows:
        site = (row.site or "").strip()

        if not site:
            continue

        if not row.start_date or not row.end_date:
            continue

        name = frappe.db.get_value(
            "Monthly Production Planning",
            {
                "location": site,
                "prod_month_start_date": ["<=", row.end_date],
                "prod_month_end_date": [">=", row.start_date],
            },
            "name",
            order_by="modified desc",
        )

        if name:
            plans[site] = frappe.get_doc("Monthly Production Planning", name)

    return plans