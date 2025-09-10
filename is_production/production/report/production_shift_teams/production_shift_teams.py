import frappe
from frappe import _

def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns, data, grand_total = get_columns(), *get_data(filters)
    return columns, data, None, None, get_report_summary(grand_total)

def get_columns():
    return [
        {"label": _("Excavator"), "fieldname": "excavator", "fieldtype": "Data", "width": 160, "group": 1},
        {"label": _("Truck"), "fieldname": "truck", "fieldtype": "Data", "width": 140, "group": 1},
        {"label": _("Mining Area"), "fieldname": "mining_area", "fieldtype": "Data", "width": 160},
        {"label": _("Material Type"), "fieldname": "mat_type", "fieldtype": "Data", "width": 140},
        {"label": _("BCMs"), "fieldname": "bcms", "fieldtype": "Float", "width": 100},
    ]

def get_data(filters):
    if not (filters.start_date and filters.end_date and filters.site):
        return [], 0

    values = {
        "start_date": filters["start_date"],
        "end_date": filters["end_date"],
        "site": filters["site"],
        "shift": filters.get("shift"),
    }

    shift_condition = ""
    if filters.get("shift"):
        shift_condition = " AND hp.shift = %(shift)s"

    rows = frappe.db.sql(f"""
        SELECT
            tl.asset_name_shoval AS excavator,
            tl.asset_name_truck AS truck,
            tl.mining_areas_trucks AS mining_area,
            tl.mat_type AS mat_type,
            SUM(tl.bcms) AS bcms
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.location = %(site)s
          {shift_condition}
        GROUP BY tl.asset_name_shoval, tl.asset_name_truck, tl.mining_areas_trucks, tl.mat_type
        ORDER BY tl.asset_name_shoval, tl.asset_name_truck
    """, values, as_dict=True)

    grouped = {}
    grand_total = 0
    for r in rows:
        excavator = r["excavator"] or "Unassigned"
        truck = r["truck"] or "Unassigned"
        grouped.setdefault(excavator, {"total": 0, "children": {}})
        grouped[excavator]["total"] += r["bcms"] or 0
        grouped[excavator]["children"].setdefault(truck, {"total": 0, "details": []})
        grouped[excavator]["children"][truck]["total"] += r["bcms"] or 0
        grouped[excavator]["children"][truck]["details"].append(r)
        grand_total += r["bcms"] or 0

    results = []
    for excavator in sorted(grouped.keys()):
        results.append({
            "excavator": excavator,
            "truck": None,
            "mining_area": None,
            "mat_type": None,
            "bcms": grouped[excavator]["total"],
            "indent": 0
        })
        for truck in sorted(grouped[excavator]["children"].keys()):
            truck_info = grouped[excavator]["children"][truck]
            results.append({
                "excavator": None,
                "truck": truck,
                "mining_area": None,
                "mat_type": None,
                "bcms": truck_info["total"],
                "indent": 1
            })
            for d in truck_info["details"]:
                results.append({
                    "excavator": None,
                    "truck": None,
                    "mining_area": d["mining_area"],
                    "mat_type": d["mat_type"],
                    "bcms": d["bcms"],
                    "indent": 2
                })

    return results, grand_total

def get_report_summary(grand_total):
    # ✅ Display grand total with comma as thousands separator
    formatted_total = f"{grand_total:,.0f}"
    return [{
        "label": _("Grand Total BCMs"),
        "value": formatted_total,
        "indicator": "Blue"
    }]

























