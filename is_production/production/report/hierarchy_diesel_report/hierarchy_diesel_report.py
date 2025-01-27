# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

# File: hierarchy_diesel_report.py
import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"fieldname": "account_name", "label": _("Account/Equipment"), "fieldtype": "Data", "width": 300},
        {"fieldname": "litres_issued", "label": _("Litres Issued"), "fieldtype": "Float", "width": 150},
        {"fieldname": "open_reading", "label": _("Opening Reading"), "fieldtype": "Float", "width": 150},
        {"fieldname": "close_reading", "label": _("Closing Reading"), "fieldtype": "Float", "width": 150},
        {"fieldname": "hours_km", "label": _("Hours/Km"), "fieldtype": "Data", "width": 100},
    ]

def get_data(filters):
    data = []

    # Fetch all parent records (Daily Diesel Sheets)
    parent_records = frappe.get_all(
        "Daily Diesel Sheet",
        fields=["name", "location", "asset_name", "daily_sheet_date", "shift", "litres_issued_equipment"],
        filters=filters,
    )

    for parent in parent_records:
        # Add parent record to data
        data.append({
            "account_name": f"{parent.location} - {parent.asset_name} ({parent.shift})",
            "litres_issued": parent.litres_issued_equipment,
            "indent": 0,
        })

        # Fetch child records (Daily Diesel Entries) for this parent
        child_records = frappe.get_all(
            "Daily Diesel Entries",
            fields=["asset_name", "litres_issued", "open_reading", "close_reading", "hours_km"],
            filters={"parent": parent.name},
        )

        for child in child_records:
            # Add child record to data
            data.append({
                "account_name": f"  {child.asset_name}",
                "litres_issued": child.litres_issued,
                "open_reading": child.open_reading,
                "close_reading": child.close_reading,
                "hours_km": child.hours_km,
                "indent": 1,  # Child level
            })

    return data
