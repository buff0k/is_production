import frappe
from frappe import _

def execute(filters=None):
    if not filters.get("start_date") or not filters.get("end_date") or not filters.get("site"):
        frappe.throw(_("All filters are required"))

    columns = [
        {"label": _("Asset"), "fieldname": "asset", "fieldtype": "Link", "options": "Asset", "width": 200},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": _("Total BCMs"), "fieldname": "total_bcm", "fieldtype": "Float", "width": 150}
    ]

    data = []

    # trucks
    trucks = frappe.db.sql("""
        SELECT
            tl.asset_name_truck AS asset,
            tl.item_name AS item_name,
            SUM(tl.bcms) AS total_bcm
        FROM `tabHourly Production` hp
        INNER JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.location = %(site)s
        GROUP BY tl.asset_name_truck, tl.item_name
    """, filters, as_dict=True)

    # dozers
    dozers = frappe.db.sql("""
        SELECT
            dp.asset_name AS asset,
            dp.item_name AS item_name,
            SUM(dp.bcm_hour) AS total_bcm
        FROM `tabHourly Production` hp
        INNER JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.location = %(site)s
        GROUP BY dp.asset_name, dp.item_name
    """, filters, as_dict=True)

    data = trucks + dozers

    return columns, data
