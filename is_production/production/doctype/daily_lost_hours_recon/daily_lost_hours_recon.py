# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document


class DailyLostHoursRecon(Document):
	pass


@frappe.whitelist()
def get_monthly_production_planning(location, shift_date):
    """
    Fetch the latest Monthly Production Planning where:
    - The location matches.
    - The shift_date falls between prod_month_start_date and prod_month_end_date.
    - Picks the latest (most recent) Monthly Production Planning if multiple exist.
    """
    monthly_plan = frappe.db.sql("""
        SELECT name
        FROM `tabMonthly Production Planning`
        WHERE location = %s
        AND prod_month_start_date <= %s
        AND prod_month_end_date >= %s
        ORDER BY prod_month_start_date DESC
        LIMIT 1
    """, (location, shift_date, shift_date), as_dict=True)

    return monthly_plan[0]["name"] if monthly_plan else None

@frappe.whitelist()
def get_shift_system(monthly_production_planning):
    """
    Fetch the shift system from the Monthly Production Planning document.
    """
    shift_system = frappe.db.get_value("Monthly Production Planning", monthly_production_planning, "shift_system")
    return shift_system if shift_system else None


@frappe.whitelist()
def get_assets(location):
    """
    Fetch assets that belong to the selected location and have docstatus = 1.
    Populate the child table with asset_name, item_name, and asset_category.
    Sort the results by asset_category.
    """

    # Identify the correct field for location in the Asset Doctype
    asset_location_field = None
    doctype_meta = frappe.get_doc("DocType", "Asset")  # Ensure 'Asset' is the correct Doctype

    for field in doctype_meta.fields:
        if "location" in field.fieldname.lower():  # Find the correct location field
            asset_location_field = field.fieldname
            break

    if not asset_location_field:
        frappe.throw("No location field found in 'Asset'. Please check the Doctype configuration.")

    # Fetch assets that match the location in the parent document and have docstatus = 1
    assets = frappe.db.get_all(
        "Asset",  # Change this if necessary
        filters={asset_location_field: location, "docstatus": 1},
        fields=["name as asset_name", "item_name", "asset_category"],
        order_by="asset_category ASC"  # Sorting by asset_category
    )

    return assets if assets else []