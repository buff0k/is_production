# Copyright (c) 2026, Isambane Mining (Pty) Ltd
# Excavator Loads Per Hour
#
# IMPORTANT:
# This report does NOT report physical load counts.
# It reports converted truck-and-shovel volume, using Truck Loads.bcms.
#
# Current layout:
# One row per production date.
# Each hour column shows total BCM from all excavators combined for that day/hour.
#
# This follows the Production Efficiency concept:
# Hourly Production -> Truck Loads -> SUM(tl.bcms), grouped by production date and hour.

import frappe
from frappe import _
from frappe.utils import getdate, add_days, today


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

    bcm_rows = get_hourly_bcm_rows(
        start_date=start_date,
        end_date=end_date,
        site=site,
        shift=shift
    )

    data = build_data(
        start_date=start_date,
        end_date=end_date,
        bcm_rows=bcm_rows,
        shift=shift
    )

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
            "label": _(slot),
            "fieldname": make_slot_fieldname(slot),
            "fieldtype": "Int",
            "width": 70
        })

    columns.extend([
        {
            "label": _("Total BCM"),
            "fieldname": "total_bcm",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Avg BCM/Hr"),
            "fieldname": "avg_bcm_per_hour",
            "fieldtype": "Int",
            "width": 110
        }
    ])

    return columns


# ---------------------------------------------------------------------
# Main query
# ---------------------------------------------------------------------
def get_hourly_bcm_rows(start_date, end_date, site=None, shift=None):
    conditions = [
        "hp.docstatus < 2",
        "hp.prod_date BETWEEN %(start_date)s AND %(end_date)s",
        "tl.asset_name_shoval IS NOT NULL",
        "tl.asset_name_shoval != ''",
        "COALESCE(tl.bcms, 0) > 0"
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

    query = f"""
        SELECT
            hp.prod_date AS report_date,
            hp.hour_slot AS hour_slot,
            SUM(COALESCE(tl.bcms, 0)) AS bcm
        FROM `tabHourly Production` hp
        INNER JOIN `tabTruck Loads` tl
            ON tl.parent = hp.name
        WHERE {" AND ".join(conditions)}
        GROUP BY
            hp.prod_date,
            hp.hour_slot
        ORDER BY
            hp.prod_date ASC,
            hp.hour_slot ASC
    """

    return frappe.db.sql(query, params, as_dict=True)


# ---------------------------------------------------------------------
# Build final rows
# ---------------------------------------------------------------------
def build_data(start_date, end_date, bcm_rows, shift=None):
    bcm_by_date = build_bcm_map(bcm_rows)
    relevant_slots = get_average_slots(shift)

    data = []
    current = start_date

    while current <= end_date:
        slot_map = bcm_by_date.get(current, {})

        row = {
            "report_date": current.strftime("%Y/%m/%d"),
            "day_name": current.strftime("%A")
        }

        total_bcm = 0
        avg_values = []

        for slot in SLOT_LABELS:
            value = int(float(slot_map.get(slot, 0) or 0))

            row[make_slot_fieldname(slot)] = value
            total_bcm += value

            if slot in relevant_slots:
                avg_values.append(value)

        row["total_bcm"] = int(total_bcm)
        row["avg_bcm_per_hour"] = (
            int(sum(avg_values) / len(avg_values))
            if avg_values else 0
        )

        data.append(row)
        current = add_days(current, 1)

    return data


def build_bcm_map(rows):
    """
    Output:
    {
        date: {
            slot_label: bcm
        }
    }
    """
    output = {}

    for row in rows:
        report_date = parse_report_date(row.get("report_date"))
        slot_key = normalize_hour_slot(row.get("hour_slot"))

        if not report_date or not slot_key:
            continue

        output.setdefault(report_date, {})

        current_value = output[report_date].get(slot_key, 0)
        new_value = int(float(row.get("bcm") or 0))

        output[report_date][slot_key] = int(current_value + new_value)

    return output


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


def parse_report_date(value):
    if not value:
        return None

    try:
        return getdate(value)
    except Exception:
        pass

    try:
        parts = str(value).split("-")
        if len(parts) == 3 and len(parts[0]) == 2 and len(parts[2]) == 4:
            day, month, year = parts
            return getdate(f"{year}-{month}-{day}")
    except Exception:
        pass

    return None


def normalize_hour_slot(hour_slot):
    """
    Converts stored hour_slot values into report labels.

    Examples:
    - 06:00-07:00 -> 6-7
    - 6:00-7:00 -> 6-7
    - 23:00-0:00 -> 23-24
    - 23:00-00:00 -> 23-24
    - 0:00-1:00 -> 24-1
    - 00:00-01:00 -> 24-1
    """
    if not hour_slot:
        return None

    try:
        raw = str(hour_slot).strip()
        raw = raw.replace(":00:00", ":00")

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