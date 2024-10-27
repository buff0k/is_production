# Copyright (c) 2024, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
	columns, data = [], []
	return columns, data

@frappe.whitelist()
def fetch_records(location, from_date, to_date):
    records = frappe.get_all(
        "Daily Diesel Sheet",
        filters={
            "location": location,
            "daily_sheet_date": ["between", [from_date, to_date]]
        },
        fields=["name", "location", "daily_sheet_date", "litres_dispensed", "other_fields_you_need"]
    )
    return records
