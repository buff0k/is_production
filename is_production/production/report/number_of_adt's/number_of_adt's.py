# Copyright (c) 2026, Isambane Mining (Pty) Ltd
# Number of ADT's

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

    used_rows = get_hourly_used_adt_counts(
        start_date=start_date,
        end_date=end_date,
        site=site,
        shift=shift
    )

    avail_rows = get_hourly_available_adt_counts(
        start_date=start_date,
        end_date=end_date,
        site=site,
        shift=shift
    )

    data = build_data(
        start_date=start_date,
        end_date=end_date,
        used_rows=used_rows,
        avail_rows=avail_rows,
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
            "label": _(f"{slot} Used"),
            "fieldname": make_slot_fieldname(slot, "used"),
            "fieldtype": "Int",
            "width": 70
        })

        columns.append({
            "label": _(f"{slot} Avail"),
            "fieldname": make_slot_fieldname(slot, "avail"),
            "fieldtype": "Int",
            "width": 70
        })

    columns.extend([
        {
            "label": _("Avg Used"),
            "fieldname": "avg_used",
            "fieldtype": "Int",
            "width": 90
        },
        {
            "label": _("Avg Avail"),
            "fieldname": "avg_avail",
            "fieldtype": "Int",
            "width": 90
        }
    ])

    return columns


# ---------------------------------------------------------------------
# Used ADTs from Hourly Production
# ---------------------------------------------------------------------
def get_hourly_used_adt_counts(start_date, end_date, site=None, shift=None):
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

    query = f"""
        SELECT
            hp.prod_date AS report_date,
            hp.hour_slot,
            COUNT(DISTINCT CASE
                WHEN COALESCE(tl.loads, 0) > 0 THEN tl.asset_name_truck
                ELSE NULL
            END) AS used_count
        FROM `tabHourly Production` hp
        LEFT JOIN `tabTruck Loads` tl
            ON tl.parent = hp.name
        WHERE {" AND ".join(conditions)}
        GROUP BY hp.prod_date, hp.hour_slot
        ORDER BY hp.prod_date ASC
    """

    return frappe.db.sql(query, params, as_dict=True)


# ---------------------------------------------------------------------
# Available ADTs from Machine Availability Hourly
# ---------------------------------------------------------------------
def get_hourly_available_adt_counts(start_date, end_date, site=None, shift=None):
    conditions = [
        "mah.docstatus < 2",
        "mah.date BETWEEN %(start_date)s AND %(end_date)s"
    ]

    params = {
        "start_date": str(start_date),
        "end_date": str(end_date)
    }

    if site:
        conditions.append("mah.site = %(site)s")
        params["site"] = site

    if shift:
        conditions.append("mah.shift = %(shift)s")
        params["shift"] = shift

    query = f"""
        SELECT
            mah.date AS report_date,
            mah.hour_slot,
            COUNT(CASE
                WHEN mac.asset_categoryda = 'ADT'
                 AND mac.available_or_not = 'Yes'
                THEN 1
                ELSE NULL
            END) AS avail_count
        FROM `tabMachine Availability Hourly` mah
        LEFT JOIN `tabMachine Availability Hourly Child` mac
            ON mac.parent = mah.name
        WHERE {" AND ".join(conditions)}
        GROUP BY mah.date, mah.hour_slot
        ORDER BY mah.date ASC
    """

    return frappe.db.sql(query, params, as_dict=True)


# ---------------------------------------------------------------------
# Build final rows
# ---------------------------------------------------------------------
def build_data(start_date, end_date, used_rows, avail_rows, shift=None):
    used_by_date = build_count_map(
        rows=used_rows,
        count_field="used_count"
    )

    avail_by_date = build_count_map(
        rows=avail_rows,
        count_field="avail_count"
    )

    relevant_slots = get_average_slots(shift)

    data = []
    current = start_date

    while current <= end_date:
        row = {
            "report_date": current.strftime("%Y/%m/%d"),
            "day_name": current.strftime("%A")
        }

        used_slot_map = used_by_date.get(current, {})
        avail_slot_map = avail_by_date.get(current, {})

        used_values = []
        avail_values = []

        for slot in SLOT_LABELS:
            used_value = int(used_slot_map.get(slot, 0))
            avail_value = int(avail_slot_map.get(slot, 0))

            row[make_slot_fieldname(slot, "used")] = used_value
            row[make_slot_fieldname(slot, "avail")] = avail_value

            if slot in relevant_slots:
                used_values.append(used_value)
                avail_values.append(avail_value)

        row["avg_used"] = int(sum(used_values) / len(used_values)) if used_values else 0
        row["avg_avail"] = int(sum(avail_values) / len(avail_values)) if avail_values else 0

        data.append(row)
        current = add_days(current, 1)

    return data


def build_count_map(rows, count_field):
    counts_by_date = {}

    for row in rows:
        report_date = parse_report_date(row.get("report_date"))
        slot_key = normalize_hour_slot(row.get("hour_slot"))

        if not report_date or not slot_key:
            continue

        counts_by_date.setdefault(report_date, {})
        counts_by_date[report_date][slot_key] = (
            counts_by_date[report_date].get(slot_key, 0)
            + int(row.get(count_field) or 0)
        )

    return counts_by_date


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def get_average_slots(shift):
    if shift == "Day":
        return DAY_SHIFT_SLOTS

    if shift == "Night":
        return NIGHT_SHIFT_SLOTS

    return SLOT_LABELS


def make_slot_fieldname(slot_label, suffix):
    return "h_" + slot_label.replace("-", "_") + "_" + suffix


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
    - 06:00-07:00 -> 6-7
    - 23:00-00:00 -> 23-24
    - 00:00-01:00 -> 24-1
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