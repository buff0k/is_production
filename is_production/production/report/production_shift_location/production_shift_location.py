# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

# import frappe
# apps/is_production/is_production/production/report/production_shift_location/production_shift_location.py

import frappe

def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Date", "fieldname": "prod_date", "fieldtype": "Date", "width": 100},
        {"label": "Shift", "fieldname": "shift", "fieldtype": "Data", "width": 100},
        {"label": "Mining Area", "fieldname": "mining_area", "fieldtype": "Data", "width": 180},
        {"label": "Truck + Shovel BCM", "fieldname": "ts_bcm", "fieldtype": "Float", "width": 150},
        {"label": "Dozing BCM", "fieldname": "dozer_bcm", "fieldtype": "Float", "width": 150},
        {"label": "Total BCM", "fieldname": "total_bcm", "fieldtype": "Float", "width": 150},
    ]


def get_data(filters):
    if not (filters.start_date and filters.end_date and filters.site):
        return []

    # --- Truck Loads per mining area ---
    truck_rows = frappe.db.sql(
        """
        SELECT hp.prod_date, hp.shift,
               tl.mining_areas_trucks as mining_area,
               SUM(tl.bcms) as ts_bcm
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.location = %(site)s
          AND hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.docstatus < 2
          AND tl.mining_areas_trucks IS NOT NULL
        GROUP BY hp.prod_date, hp.shift, tl.mining_areas_trucks
        """,
        filters,
        as_dict=True,
    )

    # --- Dozer Production per mining area ---
    dozer_rows = frappe.db.sql(
        """
        SELECT hp.prod_date, hp.shift,
               dp.mining_areas_dozer_child as mining_area,
               SUM(dp.bcm_hour) as dozer_bcm
        FROM `tabHourly Production` hp
        JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.location = %(site)s
          AND hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.docstatus < 2
          AND dp.mining_areas_dozer_child IS NOT NULL
        GROUP BY hp.prod_date, hp.shift, dp.mining_areas_dozer_child
        """,
        filters,
        as_dict=True,
    )

    # --- Merge truck + dozer into one dict ---
    combined = {}

    for r in truck_rows:
        key = (r.prod_date, r.shift, r.mining_area)
        combined[key] = {
            "prod_date": r.prod_date,
            "shift": r.shift,
            "mining_area": r.mining_area,
            "ts_bcm": r.ts_bcm or 0,
            "dozer_bcm": 0,
        }

    for r in dozer_rows:
        key = (r.prod_date, r.shift, r.mining_area)
        if key not in combined:
            combined[key] = {
                "prod_date": r.prod_date,
                "shift": r.shift,
                "mining_area": r.mining_area,
                "ts_bcm": 0,
                "dozer_bcm": r.dozer_bcm or 0,
            }
        else:
            combined[key]["dozer_bcm"] = r.dozer_bcm or 0

    # --- Add totals ---
    results = []
    for row in combined.values():
        row["total_bcm"] = (row["ts_bcm"] or 0) + (row["dozer_bcm"] or 0)
        results.append(row)

    # Sort by date, shift, mining area
    results.sort(key=lambda x: (x["prod_date"], x["shift"], x["mining_area"]))

    return results



