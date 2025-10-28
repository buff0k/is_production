# ===========================================================
# Diesel Reconciliation Backend Logic (Full Extended Version)
# -----------------------------------------------------------
# Author: Isambane Mining (Pty) Ltd
# Year: 2025
# ===========================================================

import frappe
from frappe.model.document import Document


class DieselReconciliation(Document):
    pass


# -----------------------------------------------------------
# Helper Function for Safe SQL Totals
# -----------------------------------------------------------
def get_total(sql_query, params):
    """Run a safe SQL query and return numeric total."""
    try:
        result = frappe.db.sql(sql_query, params)
        return result[0][0] or 0 if result and result[0][0] is not None else 0
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Diesel Reconciliation Query Error")
        return 0


# -----------------------------------------------------------
# Main Whitelisted Method for Auto-Fill
# -----------------------------------------------------------
@frappe.whitelist()
def auto_fill_all_diesel_data(site, start_date, end_date):
    """
    Automatically fetches litres received and issued for all
    Diesel Bowsers and Diesel Bulk Tanks based on selected site and date range.
    """
    data = {"bowsers": [], "tanks": []}

    # ------------------------------------------------------
    # DIESEL BOWSERS
    # ------------------------------------------------------
    bowser_assets = frappe.get_all(
        "Asset",
        filters={"asset_category": "Diesel Bowsers", "location": site},
        pluck="name"
    )

    for asset in bowser_assets:
        receipts = get_total(
            """
            SELECT SUM(litres_dispensed)
            FROM `tabDiesel Receipt`
            WHERE asset_name = %s
              AND date_time_diesel_receipt BETWEEN %s AND %s
              AND docstatus = 1
            """,
            (asset, start_date, end_date)
        )

        issues = get_total(
            """
            SELECT SUM(litres_issued_equipment)
            FROM `tabDaily Diesel Sheet`
            WHERE asset_name = %s
              AND daily_sheet_date BETWEEN %s AND %s
              AND docstatus = 1
            """,
            (asset, start_date, end_date)
        )

        data["bowsers"].append({
            "asset": asset,
            "receipt_total": receipts,
            "issue_total": issues
        })

    # ------------------------------------------------------
    # DIESEL BULK TANKS
    # ------------------------------------------------------
    tank_assets = frappe.get_all(
        "Asset",
        filters={"asset_category": "Diesel Bulk", "location": site},
        pluck="name"
    )

    for asset in tank_assets:
        receipts = get_total(
            """
            SELECT SUM(litres_dispensed)
            FROM `tabDiesel Receipt`
            WHERE asset_name = %s
              AND date_time_diesel_receipt BETWEEN %s AND %s
              AND docstatus = 1
            """,
            (asset, start_date, end_date)
        )

        issues = get_total(
            """
            SELECT SUM(litres_issued_equipment)
            FROM `tabDaily Diesel Sheet`
            WHERE asset_name = %s
              AND daily_sheet_date BETWEEN %s AND %s
              AND docstatus = 1
            """,
            (asset, start_date, end_date)
        )

        data["tanks"].append({
            "asset": asset,
            "receipt_total": receipts,
            "issue_total": issues
        })

    return data


# -----------------------------------------------------------
# Row-Based Fetch Method (for JS trigger)
# -----------------------------------------------------------
@frappe.whitelist()
def get_machine_diesel_totals(site, start_date, end_date, asset_name):
    """
    Returns diesel_issued and diesel_received for a specific machine/bowser
    within the selected site and date range.
    """
    if not (asset_name and start_date and end_date):
        return {"diesel_issued": 0, "diesel_received": 0}

    diesel_issued = get_total(
        """
        SELECT SUM(litres_issued_equipment)
        FROM `tabDaily Diesel Sheet`
        WHERE asset_name = %s
          AND daily_sheet_date BETWEEN %s AND %s
          AND docstatus = 1
        """,
        (asset_name, start_date, end_date)
    )

    diesel_received = get_total(
        """
        SELECT SUM(litres_dispensed)
        FROM `tabDiesel Receipt`
        WHERE asset_name = %s
          AND date_time_diesel_receipt BETWEEN %s AND %s
          AND docstatus = 1
        """,
        (asset_name, start_date, end_date)
    )

    return {
        "diesel_issued": diesel_issued,
        "diesel_received": diesel_received
    }


# -----------------------------------------------------------
# Calculate Diesel Totals per Asset Category (Extended)
# -----------------------------------------------------------
@frappe.whitelist()
def calculate_equipment_totals_by_site(site, start_date, end_date):
    """
    Cross-checks Daily Diesel Entries with the Asset master to find
    total diesel issued per Asset Category (e.g. ADT, Dozer, Excavator, etc.)
    across the selected date range.
    """
    tracked_categories = [
    "ADT", "Dozer", "Excavator", "Service Truck", "Grader", "TLB",
    "Diesel Bowsers", "Water Bowser", "Drills", "Lightning Plant",
    "LDV", "Generator", "Water pump", "All items group"
    ]

    totals_by_category = {cat: 0 for cat in tracked_categories}
    totals_by_category["Total"] = 0

    diesel_entries = frappe.db.sql("""
        SELECT e.asset_name, e.litres_issued
        FROM `tabDaily Diesel Entries` e
        JOIN `tabDaily Diesel Sheet` s ON e.parent = s.name
        WHERE s.location = %s
          AND s.daily_sheet_date BETWEEN %s AND %s
          AND s.docstatus = 1
          AND e.asset_name IS NOT NULL
    """, (site, start_date, end_date), as_dict=True)

    if not diesel_entries:
        return totals_by_category

    asset_names = [d["asset_name"].strip() for d in diesel_entries if d.get("asset_name")]
    assets_info = frappe.get_all(
        "Asset",
        filters={"name": ["in", asset_names]},
        fields=["name", "asset_category"]
    )

    asset_category_map = {
        a["name"].strip().upper(): a.get("asset_category", "").strip().title()
        for a in assets_info
    }

    for entry in diesel_entries:
        asset_name = entry.get("asset_name", "").strip().upper()
        litres = float(entry.get("litres_issued") or 0)
        category = asset_category_map.get(asset_name, "Unknown")

        match = next((c for c in tracked_categories if c.lower() in category.lower()), None)
        if match:
            totals_by_category[match] += litres
            totals_by_category["Total"] += litres

    return totals_by_category
