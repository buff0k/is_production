# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

# import frappe
# apps/is_production/is_production/production/report/production_shift_adt/production_shift_adt.py

import frappe

def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Shift", "fieldname": "shift", "fieldtype": "Data", "width": 100},
        {"label": "ADT Truck", "fieldname": "truck", "fieldtype": "Data", "width": 180},
        {"label": "Total BCM (Cumulative)", "fieldname": "cumulative_bcm", "fieldtype": "Float", "width": 150},
    ]


def get_data(filters):
    if not (filters.start_date and filters.end_date and filters.site):
        return []

    # Fetch per-truck totals
    rows = frappe.db.sql(
        """
        SELECT hp.prod_date, hp.shift, tl.asset_name_truck AS truck, SUM(tl.bcms) AS bcm_total
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.location = %(site)s
          AND hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.docstatus < 2
        GROUP BY hp.prod_date, hp.shift, tl.asset_name_truck
        ORDER BY hp.prod_date, hp.shift, tl.asset_name_truck
        """,
        {
            "site": filters.site,
            "start_date": filters.start_date,
            "end_date": filters.end_date,
        },
        as_dict=True,
    )

    results = []
    shift_totals = {}

    # Build per-truck rows and accumulate per-shift totals
    for r in rows:
        results.append({
            "shift": r.shift,
            "truck": r.truck,
            "cumulative_bcm": r.bcm_total or 0,
        })

        shift_totals.setdefault(r.shift, 0)
        shift_totals[r.shift] += r.bcm_total or 0

    # Add grand total rows per shift
    for shift, total in shift_totals.items():
        results.append({
            "shift": shift,
            "truck": "TOTAL",
            "cumulative_bcm": total,
        })

    return results
