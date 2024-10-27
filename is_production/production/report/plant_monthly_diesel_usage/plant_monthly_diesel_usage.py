# Copyright (c) 2024, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    if not filters:
        filters = {}

    if not filters.get("location") or not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw("Please select a location and date range to run the report.")

    columns = [
        {"label": "Document ID", "fieldname": "name", "fieldtype": "Link", "options": "Daily Diesel Sheet", "width": 100},
        {"label": "Location", "fieldname": "location", "fieldtype": "Link", "options": "Location", "width": 120},
        {"label": "Date", "fieldname": "daily_sheet_date", "fieldtype": "Date", "width": 100},
        {"label": "Litres Dispensed", "fieldname": "litres_issued_equipment", "fieldtype": "Float", "width": 120},
        # Add other necessary columns here
    ]

    conditions = "WHERE 1=1"
    
    if filters.get("location"):
        conditions += " AND location = %(location)s"
    if filters.get("from_date") and filters.get("to_date"):
        conditions += " AND daily_sheet_date BETWEEN %(from_date)s AND %(to_date)s"

    data = frappe.db.sql(f"""
        SELECT
            name,
            location,
            daily_sheet_date,
            litres_issued_equipment
        FROM `tabDaily Diesel Sheet`
        {conditions}
    """, filters, as_dict=True)

    return columns, data
