import frappe
from frappe import _
from frappe.utils import flt, getdate, date_diff

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data

def get_columns():
    return [
        {"label": _("Date"), "fieldname": "daily_sheet_date", "fieldtype": "Date", "width": 100},
        {"label": _("Location"), "fieldname": "location", "fieldtype": "Link", "options": "Location", "width": 150},
        {"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Link", "options": "Asset", "width": 150},
        {"label": _("Diesel Used (Litres)"), "fieldname": "litres_used", "fieldtype": "Float", "width": 120}
    ]

def get_data(filters):
    conditions = ["dds.docstatus = 1"]  # Ensuring only submitted records are fetched
    
    if filters.get("location"):
        conditions.append("dds.location = %(location)s")
    if filters.get("from_date") and filters.get("to_date"):
        conditions.append("dds.daily_sheet_date BETWEEN %(from_date)s AND %(to_date)s")
    if filters.get("asset_name"):
        conditions.append("dde.asset_name = %(asset_name)s")

    conditions_str = " AND ".join(conditions)
    query = f"""
        SELECT
            dds.daily_sheet_date,
            dds.location,
            dde.asset_name,
            dde.litres_issued as litres_used
        FROM
            `tabDaily Diesel Sheet` dds,
            `tabDaily Diesel Entries` dde
        WHERE
            dde.parent = dds.name
            {"AND " + conditions_str if conditions_str else ""}
        ORDER BY
            dds.daily_sheet_date ASC
    """

    return frappe.db.sql(query, filters, as_dict=1)