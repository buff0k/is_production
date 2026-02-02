# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_days, nowdate


def _date_range(start, end):
    d = start
    while d <= end:
        yield d
        d = add_days(d, 1)


def _counts(start_date, end_date):
    # Mon=0 ... Sun=6
    wd = sat = sun = 0
    for d in _date_range(start_date, end_date):
        w = getdate(d).weekday()
        if w <= 4:
            wd += 1
        elif w == 5:
            sat += 1
        else:
            sun += 1
    return wd, sat, sun


def clamp_non_negative(x):
    return x if x and x > 0 else 0


def _month_start(dt):
    d = getdate(dt)
    return d.replace(day=1)


def _pick_meters_field(child_doctype: str) -> str:
    """
    Try to find the meters field in the hourly entries child table.
    Adjust the candidates if your child fieldname is different.
    """
    meta = frappe.get_meta(child_doctype)
    candidates = [
        "meters",
        "meter",
        "metres",
        "total_meters",
        "drilled_meters",
        "drilling_meters",
    ]
    for f in candidates:
        if meta.has_field(f):
            return f
    return "meters"


def _resolve_hourly_child_doctype() -> str:
    """
    Resolve the child doctype for Hourly Drilling Report's hourly_entries table field
    dynamically from meta (no hardcoding).
    """
    parent_dt = "Hourly Drilling Report"
    table_fieldname = "hourly_entries"

    meta = frappe.get_meta(parent_dt)
    if not meta.has_field(table_fieldname):
        frappe.log_error(
            f"{parent_dt} has no field '{table_fieldname}'",
            "DrillingMeterPlanning: resolve hourly child doctype",
        )
        return ""

    f = meta.get_field(table_fieldname)
    child_dt = (f.options or "").strip() if f else ""
    if not child_dt:
        frappe.log_error(
            f"{parent_dt}.{table_fieldname} has no options (child doctype)",
            "DrillingMeterPlanning: resolve hourly child doctype",
        )
    return child_dt


def get_mtd_drilled_meters(site: str, any_date_in_month, end_date=None) -> float:
    """
    MTD = sum of drilled meters from 1st of the month until today (or end_date if provided),
    filtered by site.
    Reads from Hourly Drilling Report + its real child table (resolved dynamically).
    """
    if not site:
        return 0.0

    # Month window
    start = _month_start(any_date_in_month)
    today = getdate(nowdate())

    # Clamp end
    if end_date:
        end = min(getdate(end_date), today)
    else:
        end = today

    parent_dt = "Hourly Drilling Report"
    parent_date_field = "date"
    parent_site_field = "site"

    # ✅ dynamic child doctype
    child_dt = _resolve_hourly_child_doctype()
    if not child_dt:
        return 0.0

    meters_field = _pick_meters_field(child_dt)

    res = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(c.`{meters_field}`), 0)
        FROM `tab{child_dt}` c
        INNER JOIN `tab{parent_dt}` p ON p.name = c.parent
        WHERE
            c.parenttype = %s
            AND c.parentfield = 'hourly_entries'
            AND p.`{parent_site_field}` = %s
            AND p.`{parent_date_field}` BETWEEN %s AND %s
            AND p.docstatus < 2
        """,
        (parent_dt, site, start, end),
    )

    return float(res[0][0] or 0.0)


def apply_calculations(doc: Document):
    # ---- validations ----
    if doc.start_date and doc.end_date and getdate(doc.end_date) < getdate(doc.start_date):
        frappe.throw("End Date cannot be before Start Date.")

    # ---- drilling month ----
    if doc.start_date:
        sd = getdate(doc.start_date)
        doc.drilling_month = sd.strftime("%b %Y")

    weekday_count = saturday_count = sunday_count = 0

    # ---- planned days ----
    if doc.start_date and doc.end_date:
        sd = getdate(doc.start_date)
        ed = getdate(doc.end_date)
        weekday_count, saturday_count, sunday_count = _counts(sd, ed)

        # Default planned days: Mon–Sat
        doc.planned_drilling_days = weekday_count + saturday_count
    else:
        doc.planned_drilling_days = 0

    # ---- remaining days ----
    worked = doc.worked_days or 0
    doc.remaining_days = clamp_non_negative((doc.planned_drilling_days or 0) - worked)

    # ---- daily target meters ----
    planned_days = doc.planned_drilling_days or 0
    monthly_target = doc.monthly_target_meters or 0

    doc.daily_target_meters = (monthly_target / planned_days) if planned_days > 0 else 0

    # ---- shifts / hours ----
    try:
        shifts = int(doc.no_of_shifts or 0)
    except Exception:
        shifts = 0

    weekday_shift_hours = doc.weekday_shift_hours or 0
    saturday_shift_hours = doc.saturday_shift_hours or 0

    if doc.start_date and doc.end_date and shifts > 0:
        doc.total_monthly_drilling_hours = (
            (weekday_count * weekday_shift_hours) +
            (saturday_count * saturday_shift_hours)
        ) * shifts
    else:
        doc.total_monthly_drilling_hours = 0

    # ---- hours completed (proxy from worked days) ----
    total_hours = doc.total_monthly_drilling_hours or 0
    avg_daily_hours = (total_hours / planned_days) if planned_days > 0 else 0

    doc.monthly_drilling_hours_completed = worked * avg_daily_hours
    doc.monthly_remaining_drilling_hours = clamp_non_negative(
        total_hours - (doc.monthly_drilling_hours_completed or 0)
    )

    # ---- MTD drilled meters: 1st of month -> today ----
    month_anchor = getdate(doc.start_date) if doc.start_date else getdate(nowdate())
    doc.mtd_drilled_meters = get_mtd_drilled_meters(
        site=doc.site,
        any_date_in_month=month_anchor,
        end_date=None,  # keep calendar MTD-to-today behaviour
    )

    mtd = doc.mtd_drilled_meters or 0

    # ---- remaining meters ----
    doc.remaining_meter = clamp_non_negative(monthly_target - mtd)

    # ---- required hourly rate ----
    rem_hours = doc.monthly_remaining_drilling_hours or 0
    doc.required_hourly_rate = (doc.remaining_meter / rem_hours) if rem_hours > 0 else 0

    # ---- current hourly rate ----
    comp_hours = doc.monthly_drilling_hours_completed or 0
    doc.current_hourly_rate = (mtd / comp_hours) if comp_hours > 0 else 0

    # ---- meters per drill ----
    drills = doc.number_of_drills or 0
    doc.meters_per_drill = (monthly_target / drills) if drills > 0 else 0

    # ---- drilling meters forecast ----
    doc.drilling_meters_forecast = (
        ((mtd / worked) * planned_days) if worked > 0 and planned_days > 0 else 0
    )

    # ---- current daily meters (AUTO) ----
    # Your JS + print expects this. If you want it manual, comment this out.
    doc.current_daily_meters = (mtd / worked) if worked > 0 else 0


class DrillingMeterPlanning(Document):
    def validate(self):
        apply_calculations(self)
