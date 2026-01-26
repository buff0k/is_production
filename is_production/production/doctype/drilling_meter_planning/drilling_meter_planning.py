import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_days


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

    # ---- daily target ----
    if (doc.planned_drilling_days or 0) > 0:
        doc.daily_target = (doc.monthly_target_meters or 0) / doc.planned_drilling_days
    else:
        doc.daily_target = 0

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

    # ---- hours completed (proxy) ----
    planned_days = doc.planned_drilling_days or 0
    total_hours = doc.total_monthly_drilling_hours or 0
    avg_daily_hours = (total_hours / planned_days) if planned_days > 0 else 0

    doc.monthly_drilling_hours_completed = worked * avg_daily_hours
    doc.monthly_remaining_drilling_hours = clamp_non_negative(
        total_hours - (doc.monthly_drilling_hours_completed or 0)
    )

    # ---- meters ----
    target = doc.monthly_target_meters or 0
    mtd = doc.mtd_drills_meter or 0

    doc.remaining_meter = clamp_non_negative(target - mtd)

    rem_hours = doc.monthly_remaining_drilling_hours or 0
    doc.required_hourly_rate = (doc.remaining_meter / rem_hours) if rem_hours > 0 else 0

    comp_hours = doc.monthly_drilling_hours_completed or 0
    doc.current_rate = (mtd / comp_hours) if comp_hours > 0 else 0

    drills = doc.number_of_drills or 0
    doc.meters_per_drill = (target / drills) if drills > 0 else 0

    doc.drilling_meters_forecast = (
        ((mtd / worked) * planned_days) if worked > 0 and planned_days > 0 else 0
    )


class DrillingMeterPlanning(Document):
    def validate(self):
        apply_calculations(self)
