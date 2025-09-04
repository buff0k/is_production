# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters:
        filters = {}

    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    site = filters.get("site")

    # --- Report Columns ---
    columns = [
        {"label": "Date", "fieldname": "prod_date", "fieldtype": "Date", "width": 100},
        {"label": "Excavator", "fieldname": "excavator", "fieldtype": "Link", "options": "Asset", "width": 200},
        {"label": "Total BCM Moved", "fieldname": "total_bcm", "fieldtype": "Float", "precision": 1, "width": 160},
    ]

    # --- Stop if no filters selected ---
    if not (start_date and end_date and site):
        return columns, []

    # Step 1: Get all excavators assigned to the site
    excavators = frappe.db.sql("""
        SELECT name AS excavator
        FROM `tabAsset`
        WHERE asset_category = 'Excavator'
          AND location = %s
          AND docstatus = 1
    """, (site,), as_dict=True)

    if not excavators:
        return columns, []

    excavator_names = [e["excavator"] for e in excavators]

    # Step 2: Get BCM totals per excavator from Hourly Production + Truck Loads
    bcm_data = frappe.db.sql("""
        SELECT
            hp.prod_date,
            tl.asset_name_shoval AS excavator,
            COALESCE(SUM(tl.bcms), 0) AS total_bcm
        FROM `tabHourly Production` hp
        LEFT JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
          AND hp.docstatus < 2
          AND IFNULL(tl.asset_name_shoval, '') != ''
        GROUP BY hp.prod_date, tl.asset_name_shoval
    """, (start_date, end_date, site), as_dict=True)

    bcm_map = {}
    for row in bcm_data:
        bcm_map[(str(row.prod_date), row.excavator)] = row.total_bcm

    # Step 3: Get all distinct production dates in range
    dates = frappe.get_all(
        "Hourly Production",
        filters={
            "prod_date": ["between", [start_date, end_date]],
            "location": site,
            "docstatus": ["<", 2]
        },
        fields=["distinct prod_date"],
        order_by="prod_date"
    )
    date_list = [d["prod_date"] for d in dates]

    # Step 4: Build final results → ensure ALL excavators show with 0 if no BCM
    results = []
    for prod_date in date_list:
        for excavator in excavator_names:
            results.append({
                "prod_date": prod_date,
                "excavator": excavator,
                "total_bcm": bcm_map.get((str(prod_date), excavator), 0)
            })

    return columns, results




