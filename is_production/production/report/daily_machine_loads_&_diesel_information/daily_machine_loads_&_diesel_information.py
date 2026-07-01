# Copyright (c) 2026, Isambane
# For license information, please see license.txt

import frappe
from frappe.utils import flt, getdate


ALLOWED_ASSET_CATEGORIES = [
    "ADT",
    "Excavator",
    "Dozer",
    "Grader",
    "Water Bowser",
    "Service Truck",
]


def execute(filters=None):
    filters = frappe._dict(filters or {})

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 105},
        {"label": "Site", "fieldname": "site", "fieldtype": "Link", "options": "Location", "width": 140},
        {"label": "Shift", "fieldname": "shift", "fieldtype": "Data", "width": 85},

        {"label": "Fleet Nr", "fieldname": "fleet_nr", "fieldtype": "Data", "width": 100},
        {"label": "Machine", "fieldname": "machine", "fieldtype": "Link", "options": "Asset", "width": 180},
        {"label": "At EXC", "fieldname": "at_exc", "fieldtype": "Data", "width": 100},

        {"label": "Start of Shift", "fieldname": "start_of_shift", "fieldtype": "Data", "width": 110},
        {"label": "End of Shift Time", "fieldname": "end_of_shift_time", "fieldtype": "Data", "width": 125},

        {"label": "Machine Opening Hours", "fieldname": "machine_opening_hours", "fieldtype": "Data", "width": 155},
        {"label": "Machine Closing Hours", "fieldname": "machine_closing_hours", "fieldtype": "Data", "width": 155},
        {"label": "Total Operating Hours", "fieldname": "total_operating_hours", "fieldtype": "Data", "width": 145},

        {"label": "Material Type", "fieldname": "material_type", "fieldtype": "Data", "width": 115},
        {"label": "Total Loads", "fieldname": "total_loads", "fieldtype": "Data", "width": 105},
        {"label": "BCMs", "fieldname": "bcms", "fieldtype": "Data", "width": 105},

        {"label": "Diesel Poured", "fieldname": "diesel_poured", "fieldtype": "Data", "width": 120},
        {"label": "Machine Hours When Poured", "fieldname": "machine_hours_when_poured", "fieldtype": "Data", "width": 180},
        {"label": "Diesel Bowser", "fieldname": "diesel_bowser", "fieldtype": "Data", "width": 130},
        {"label": "Diesel Sheet Ref", "fieldname": "diesel_sheet_ref", "fieldtype": "Data", "width": 140},
        {"label": "Diesel Operator", "fieldname": "diesel_operator", "fieldtype": "Data", "width": 165},

        {"label": "Remarks", "fieldname": "remarks", "fieldtype": "Data", "width": 240},
    ]

def get_data(filters):
    asset_rows = get_asset_rows(filters)
    production_rows = get_production_rows(filters)
    engine_hours = get_engine_hours(filters)
    diesel_rows = get_diesel_rows(filters)

    data = []

    for asset in asset_rows:
        key = make_key(asset.date, asset.site, asset.shift, asset.machine)

        production = production_rows.get(key, frappe._dict())
        engine = engine_hours.get(key, frappe._dict())
        diesel = diesel_rows.get(key, frappe._dict())

        data.append({
            "date": asset.date,
            "site": asset.site,
            "shift": asset.shift,

            "fleet_nr": asset.fleet_nr or asset.machine,
            "machine": asset.machine,
            "at_exc": production.get("at_exc") or "N/A",

            "start_of_shift": get_shift_start(asset.shift),
            "end_of_shift_time": get_shift_end(asset.shift),

            "machine_opening_hours": engine.get("eng_hrs_start") if engine.get("eng_hrs_start") is not None else "N/A",
            "machine_closing_hours": engine.get("eng_hrs_end") if engine.get("eng_hrs_end") is not None else "N/A",
            "total_operating_hours": engine.get("working_hours") if engine.get("working_hours") is not None else "N/A",

            "material_type": production.get("material_type") or "N/A",
            "total_loads": flt(production.get("total_loads")) if production.get("total_loads") is not None else "N/A",
            "bcms": flt(production.get("bcms")) if production.get("bcms") is not None else "N/A",

            "diesel_poured": flt(diesel.get("diesel_poured")) if diesel.get("diesel_poured") is not None else "N/A",
            "machine_hours_when_poured": diesel.get("machine_hours_when_poured") if diesel.get("machine_hours_when_poured") is not None else "N/A",
            "diesel_bowser": diesel.get("diesel_bowser") or "N/A",
            "diesel_sheet_ref": diesel.get("diesel_sheet_ref") or "N/A",
            "diesel_operator": diesel.get("diesel_operator") or "N/A",

            "remarks": build_remarks(engine, diesel),
        })

    return data


def get_asset_rows(filters):
    conditions = ""
    values = {
        "categories": tuple(ALLOWED_ASSET_CATEGORIES),
        "from_date": filters.from_date,
        "to_date": filters.to_date,
    }

    if filters.get("location"):
        conditions += " AND a.location = %(location)s"
        values["location"] = filters.location

    if filters.get("asset"):
        conditions += " AND a.name = %(asset)s"
        values["asset"] = filters.asset

    shift_filter = ""
    if filters.get("shift"):
        shift_filter = " AND shifts.shift = %(shift)s"
        values["shift"] = filters.shift

    return frappe.db.sql(f"""
        SELECT
            dates.date AS date,
            a.location AS site,
            shifts.shift AS shift,
            a.name AS machine,
            a.asset_name AS fleet_nr,
            a.asset_category
        FROM `tabAsset` a
        CROSS JOIN (
            SELECT DISTINCT hp.prod_date AS date
            FROM `tabHourly Production` hp
            WHERE hp.docstatus < 2
              AND hp.prod_date >= %(from_date)s
              AND hp.prod_date <= %(to_date)s

            UNION

            SELECT DISTINCT puh.shift_date AS date
            FROM `tabPre-Use Hours` puh
            WHERE puh.docstatus < 2
              AND puh.shift_date >= %(from_date)s
              AND puh.shift_date <= %(to_date)s

            UNION

            SELECT DISTINCT dds.daily_sheet_date AS date
            FROM `tabDaily Diesel Sheet` dds
            WHERE dds.docstatus < 2
              AND dds.daily_sheet_date >= %(from_date)s
              AND dds.daily_sheet_date <= %(to_date)s
        ) dates
        CROSS JOIN (
            SELECT 'Day' AS shift
            UNION SELECT 'Night'
            UNION SELECT 'Morning'
            UNION SELECT 'Afternoon'
        ) shifts
        WHERE a.docstatus = 1
          AND a.asset_category IN %(categories)s
          {conditions}
          {shift_filter}
        ORDER BY
            dates.date ASC,
            a.location ASC,
            shifts.shift ASC,
            a.asset_category ASC,
            a.asset_name ASC
    """, values, as_dict=True)

def get_production_rows(filters):
    conditions, values = get_hp_conditions(filters)

    if filters.get("asset"):
        conditions += " AND tl.asset_name_truck = %(asset)s"
        values["asset"] = filters.asset

    if filters.get("material_type"):
        conditions += " AND tl.mat_type = %(material_type)s"
        values["material_type"] = filters.material_type

    rows = frappe.db.sql(f"""
        SELECT
            hp.prod_date AS date,
            hp.location AS site,
            hp.shift AS shift,

            tl.asset_name_truck AS machine,
            truck.asset_name AS fleet_nr,

            tl.asset_name_shoval AS excavator_asset,
            exc.asset_name AS at_exc,

            tl.mat_type AS material_type,

            SUM(COALESCE(tl.loads, 0)) AS total_loads,
            SUM(COALESCE(tl.bcms, 0)) AS bcms

        FROM `tabHourly Production` hp
        INNER JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        LEFT JOIN `tabAsset` truck ON truck.name = tl.asset_name_truck
        LEFT JOIN `tabAsset` exc ON exc.name = tl.asset_name_shoval

        WHERE hp.docstatus < 2
          AND COALESCE(tl.loads, 0) > 0
          {conditions}

        GROUP BY
            hp.prod_date,
            hp.location,
            hp.shift,
            tl.asset_name_truck,
            truck.asset_name,
            tl.asset_name_shoval,
            exc.asset_name,
            tl.mat_type

        ORDER BY
            hp.prod_date ASC,
            hp.location ASC,
            hp.shift ASC,
            truck.asset_name ASC,
            exc.asset_name ASC,
            tl.mat_type ASC
    """, values, as_dict=True)

    out = {}
    for row in rows:
        out[make_key(row.date, row.site, row.shift, row.machine)] = row

    return out

def get_engine_hours(filters):
    conditions, values = get_preuse_conditions(filters)

    if filters.get("asset"):
        conditions += " AND pa.asset_name = %(asset)s"
        values["asset"] = filters.asset

    rows = frappe.db.sql(f"""
        SELECT
            puh.shift_date AS date,
            puh.location AS site,
            puh.shift AS shift,
            pa.asset_name AS machine,
            pa.eng_hrs_start,
            pa.eng_hrs_end,
            pa.working_hours
        FROM `tabPre-Use Hours` puh
        INNER JOIN `tabPre-use Assets` pa ON pa.parent = puh.name
        WHERE puh.docstatus < 2
          {conditions}
    """, values, as_dict=True)

    out = {}
    for row in rows:
        out[make_key(row.date, row.site, row.shift, row.machine)] = row

    return out


def get_diesel_rows(filters):
    conditions, values = get_diesel_conditions(filters)

    if filters.get("asset"):
        conditions += " AND dde.asset_name = %(asset)s"
        values["asset"] = filters.asset

    rows = frappe.db.sql(f"""
        SELECT
            dds.daily_sheet_date AS date,
            dds.location AS site,
            dds.shift AS shift,
            dde.asset_name AS machine,

            SUM(COALESCE(dde.litres_issued, 0)) AS diesel_poured,
            MAX(dde.hours_km) AS machine_hours_when_poured,

            bowser.asset_name AS diesel_bowser,
            dds.daily_diesel_sheet_ref AS diesel_sheet_ref,
            dds.operator_name AS diesel_operator

        FROM `tabDaily Diesel Sheet` dds
        INNER JOIN `tabDaily Diesel Entries` dde ON dde.parent = dds.name
        LEFT JOIN `tabAsset` bowser ON bowser.name = dds.asset_name

        WHERE dds.docstatus < 2
          {conditions}

        GROUP BY
            dds.daily_sheet_date,
            dds.location,
            dds.shift,
            dde.asset_name,
            bowser.asset_name,
            dds.daily_diesel_sheet_ref,
            dds.operator_name
    """, values, as_dict=True)

    out = {}
    for row in rows:
        out[make_key(row.date, row.site, row.shift, row.machine)] = row

    return out


def get_hp_conditions(filters):
    conditions = ""
    values = {}

    if filters.get("from_date"):
        conditions += " AND hp.prod_date >= %(from_date)s"
        values["from_date"] = filters.from_date

    if filters.get("to_date"):
        conditions += " AND hp.prod_date <= %(to_date)s"
        values["to_date"] = filters.to_date

    if filters.get("location"):
        conditions += " AND hp.location = %(location)s"
        values["location"] = filters.location

    if filters.get("shift"):
        conditions += " AND hp.shift = %(shift)s"
        values["shift"] = filters.shift

    return conditions, values


def get_preuse_conditions(filters):
    conditions = ""
    values = {}

    if filters.get("from_date"):
        conditions += " AND puh.shift_date >= %(from_date)s"
        values["from_date"] = filters.from_date

    if filters.get("to_date"):
        conditions += " AND puh.shift_date <= %(to_date)s"
        values["to_date"] = filters.to_date

    if filters.get("location"):
        conditions += " AND puh.location = %(location)s"
        values["location"] = filters.location

    if filters.get("shift"):
        conditions += " AND puh.shift = %(shift)s"
        values["shift"] = filters.shift

    return conditions, values


def get_diesel_conditions(filters):
    conditions = ""
    values = {}

    if filters.get("from_date"):
        conditions += " AND dds.daily_sheet_date >= %(from_date)s"
        values["from_date"] = filters.from_date

    if filters.get("to_date"):
        conditions += " AND dds.daily_sheet_date <= %(to_date)s"
        values["to_date"] = filters.to_date

    if filters.get("location"):
        conditions += " AND dds.location = %(location)s"
        values["location"] = filters.location

    if filters.get("shift"):
        conditions += " AND dds.shift = %(shift)s"
        values["shift"] = filters.shift

    return conditions, values


def make_key(date_value, site, shift, machine):
    return f"{getdate(date_value)}|{site or ''}|{shift or ''}|{machine or ''}"


def get_shift_start(shift):
    if shift in ("Day", "Morning"):
        return "06:00"
    if shift == "Afternoon":
        return "14:00"
    if shift == "Night":
        return "18:00"
    return ""


def get_shift_end(shift):
    if shift in ("Day", "Morning"):
        return "18:00"
    if shift == "Afternoon":
        return "22:00"
    if shift == "Night":
        return "06:00"
    return ""


def build_remarks(engine, diesel):
    remarks = []

    if not engine:
        remarks.append("No Pre-Use hours found")

    if not diesel:
        remarks.append("No diesel entry found")

    return "; ".join(remarks)