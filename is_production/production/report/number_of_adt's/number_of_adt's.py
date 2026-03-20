# Copyright (c) 2026, Isambane Mining (Pty) Ltd
# Number of ADT's

import frappe
from frappe import _
from frappe.utils import getdate, add_days, today
from datetime import timedelta


# ---------------------------------------------------------------------
# Hour slot order for operational day: 06:00 -> 05:59
# ---------------------------------------------------------------------
SLOT_LABELS = [
    "6-7", "7-8", "8-9", "9-10", "10-11", "11-12",
    "12-13", "13-14", "14-15", "15-16", "16-17", "17-18",
    "18-19", "19-20", "20-21", "21-22", "22-23", "23-24",
    "24-1", "1-2", "2-3", "3-4", "4-5", "5-6"
]

DAY_SHIFT_SLOTS = [
    "6-7", "7-8", "8-9", "9-10", "10-11", "11-12",
    "12-13", "13-14", "14-15", "15-16", "16-17", "17-18"
]

NIGHT_SHIFT_SLOTS = [
    "18-19", "19-20", "20-21", "21-22", "22-23", "23-24",
    "24-1", "1-2", "2-3", "3-4", "4-5", "5-6"
]


def execute(filters=None):
    filters = filters or {}

    start_date, end_date = get_date_range(filters)
    site = filters.get("site")
    shift = filters.get("shift")

    columns = get_columns()
    raw_rows = get_hourly_adt_counts(start_date, end_date, site=site, shift=shift)
    data = build_data(start_date, end_date, raw_rows, shift=shift)

    return columns, data


# ---------------------------------------------------------------------
# Filters / dates
# ---------------------------------------------------------------------
def get_date_range(filters):
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")

    if start_date and not end_date:
        end_date = start_date
    elif end_date and not start_date:
        start_date = end_date
    elif not start_date and not end_date:
        start_date = today()
        end_date = today()

    start_date = getdate(start_date)
    end_date = getdate(end_date)

    if start_date > end_date:
        frappe.throw(_("Start Date cannot be after End Date."))

    return start_date, end_date


# ---------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------
def get_columns():
    columns = [
        {
            "label": _("Date"),
            "fieldname": "report_date",
            "fieldtype": "Data",
            "width": 110
        },
        {
            "label": _("Day"),
            "fieldname": "day_name",
            "fieldtype": "Data",
            "width": 95
        }
    ]

    for slot in SLOT_LABELS:
        columns.append({
            "label": slot,
            "fieldname": make_slot_fieldname(slot),
            "fieldtype": "Int",
            "width": 65
        })

    columns.append({
        "label": _("Average"),
        "fieldname": "avg_adts",
        "fieldtype": "Int",
        "width": 85
    })

    return columns


# ---------------------------------------------------------------------
# Data query
# ---------------------------------------------------------------------
def get_hourly_adt_counts(start_date, end_date, site=None, shift=None):
    conditions = [
        "hp.docstatus < 2",
        "hp.prod_date BETWEEN %(start_date)s AND %(end_date)s"
    ]

    params = {
        "start_date": start_date,
        "end_date": end_date
    }

    if site:
        conditions.append("hp.location = %(site)s")
        params["site"] = site

    if shift:
        conditions.append("hp.shift = %(shift)s")
        params["shift"] = shift

    # We count DISTINCT trucks/ADTs where loads > 0 for each operational hour.
    # The Truck Loads table already represents the truck rows assigned to that hour.
    query = f"""
        SELECT
            hp.prod_date,
            hp.hour_slot,
            COUNT(DISTINCT CASE
                WHEN COALESCE(tl.loads, 0) > 0 THEN tl.asset_name_truck
                ELSE NULL
            END) AS adt_count
        FROM `tabHourly Production` hp
        LEFT JOIN `tabTruck Loads` tl
            ON tl.parent = hp.name
        WHERE {" AND ".join(conditions)}
        GROUP BY hp.prod_date, hp.hour_slot
        ORDER BY hp.prod_date ASC
    """

    return frappe.db.sql(query, params, as_dict=True)


# ---------------------------------------------------------------------
# Build final rows
# ---------------------------------------------------------------------
def build_data(start_date, end_date, raw_rows, shift=None):
    counts_by_date = {}

    for row in raw_rows:
        prod_date = getdate(row.get("prod_date"))
        slot_key = normalize_hour_slot(row.get("hour_slot"))

        if not slot_key:
            continue

        counts_by_date.setdefault(prod_date, {})
        counts_by_date[prod_date][slot_key] = counts_by_date[prod_date].get(slot_key, 0) + int(row.get("adt_count") or 0)

    relevant_slots = get_average_slots(shift)

    data = []
    current = start_date
    while current <= end_date:
        row = {
            "report_date": current.strftime("%Y/%m/%d"),
            "day_name": current.strftime("%A")
        }

        day_slot_values = []
        slot_map = counts_by_date.get(current, {})

        for slot in SLOT_LABELS:
            value = int(slot_map.get(slot, 0))
            row[make_slot_fieldname(slot)] = value

            if slot in relevant_slots:
                day_slot_values.append(value)

        row["avg_adts"] = int(sum(day_slot_values) / len(day_slot_values)) if day_slot_values else 0
        data.append(row)

        current = add_days(current, 1)

    return data


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def get_average_slots(shift):
    if shift == "Day":
        return DAY_SHIFT_SLOTS
    if shift == "Night":
        return NIGHT_SHIFT_SLOTS
    return SLOT_LABELS


def make_slot_fieldname(slot_label):
    return "h_" + slot_label.replace("-", "_")


def normalize_hour_slot(hour_slot):
    """
    Converts stored Hourly Production hour_slot values into report labels.

    Examples:
    - 06:00-07:00 -> 6-7
    - 6:00-7:00   -> 6-7
    - 23:00-0:00  -> 23-24
    - 00:00-01:00 -> 24-1
    - 0:00-1:00   -> 24-1
    """
    if not hour_slot:
        return None

    try:
        raw = str(hour_slot).strip()
        if "-" not in raw:
            return None

        start_part, end_part = raw.split("-", 1)

        start_hour = int(start_part.strip().split(":")[0])
        end_hour = int(end_part.strip().split(":")[0])

        display_start = 24 if start_hour == 0 else start_hour
        display_end = 24 if end_hour == 0 else end_hour

        slot = f"{display_start}-{display_end}"
        return slot if slot in SLOT_LABELS else None

    except Exception:
        return None