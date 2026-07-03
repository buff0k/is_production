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

        projected_month_end_bcm = get_projected_month_end_bcm(
            monthly_plan=monthly_plan,
            mtd_actual_data=mtd_actual_data,
            dates=dates,
        )

        projected_mtd_data = build_projected_mtd(
            mtd_actual_data=mtd_actual_data,
            projected_month_end_bcm=projected_month_end_bcm,
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
            "projected_mtd_data": frappe.as_json(projected_mtd_data),
            "projected_month_end_bcm": projected_month_end_bcm,
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
            "fieldname": "projected_mtd_data",
            "label": "Projected MTD Data",
            "fieldtype": "Long Text",
            "width": 80,
            "hidden": 1,
        },
        {
            "fieldname": "projected_month_end_bcm",
            "label": "Projected Month End BCM",
            "fieldtype": "Float",
            "width": 150,
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


def get_projected_month_end_bcm(monthly_plan, mtd_actual_data, dates):
    """
    Prefer the same forecast value used by Site Volume Tracking if it exists on
    Monthly Production Planning. Fall back to a simple current run-rate projection.
    """
    for fieldname in (
        "month_forecated_bcm",
        "month_forecasted_bcm",
        "forecast_bcm",
        "month_forecast_bcm",
    ):
        value = monthly_plan.get(fieldname)

        if value not in (None, ""):
            try:
                value = float(value or 0)
            except Exception:
                value = 0

            if value > 0:
                return round(value, 2)

    current_index = get_latest_numeric_index(mtd_actual_data)

    if current_index < 0:
        return 0

    current_actual = float(mtd_actual_data[current_index] or 0)
    elapsed_days = current_index + 1
    total_days = len(dates or [])

    if elapsed_days <= 0 or total_days <= 0:
        return round(current_actual, 2)

    return round((current_actual / elapsed_days) * total_days, 2)


def get_latest_numeric_index(values):
    for idx in range(len(values or []) - 1, -1, -1):
        value = values[idx]

        if value in (None, ""):
            continue

        try:
            float(value)
        except Exception:
            continue

        return idx

    return -1


def build_projected_mtd(mtd_actual_data, projected_month_end_bcm):
    """
    Build a Chart.js-friendly projection array:
    - null before the latest actual point;
    - current actual at the latest actual point;
    - linear projection from that point to the projected month-end value.
    """
    values = list(mtd_actual_data or [])
    projected = [None for _ in values]

    current_index = get_latest_numeric_index(values)

    if current_index < 0:
        return projected

    current_actual = float(values[current_index] or 0)
    projected_month_end_bcm = float(projected_month_end_bcm or 0)

    if projected_month_end_bcm <= 0:
        return projected

    projected[current_index] = round(current_actual, 2)

    last_index = len(values) - 1
    remaining_points = last_index - current_index

    if remaining_points <= 0:
        return projected

    step = (projected_month_end_bcm - current_actual) / remaining_points

    for idx in range(current_index + 1, len(values)):
        projected[idx] = round(current_actual + (step * (idx - current_index)), 2)

    return projected


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