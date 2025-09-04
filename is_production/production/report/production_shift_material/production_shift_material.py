# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    if not filters.get("start_date") or not filters.get("end_date") or not filters.get("site"):
        frappe.throw(_("All filters (Start Date, End Date, Site Location) are required"))

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {"label": _("Material Type"), "fieldname": "mat_type", "fieldtype": "Data", "width": 200},
        {"label": _("Total BCMs"), "fieldname": "total_bcm", "fieldtype": "Float", "width": 150}
    ]


def get_data(filters):
    values = {
        "start_date": filters["start_date"],
        "end_date": filters["end_date"],
        "site": filters["site"]
    }

    # Aggregate BCMs by material type (from Truck Loads child table)
    results = frappe.db.sql("""
        SELECT
            tl.mat_type AS mat_type,
            SUM(tl.bcms) AS total_bcm
        FROM `tabHourly Production` hp
        INNER JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.location = %(site)s
        GROUP BY tl.mat_type
        ORDER BY tl.mat_type
    """, values, as_dict=True)

    return results
