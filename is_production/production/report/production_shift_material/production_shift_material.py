import frappe
from frappe import _

def execute(filters=None):
    if not filters.get("start_date") or not filters.get("end_date") or not filters.get("site"):
        frappe.throw(_("Filters (Start Date, End Date, Site) are required"))

    columns = get_columns()
    data, grand_total_bcm, grand_total_tons = get_data(filters)
    return columns, data, None, None, get_report_summary(grand_total_bcm, grand_total_tons)

def get_columns():
    return [
        {"label": _("Material Category"), "fieldname": "mat_type", "fieldtype": "Data", "width": 180, "group": 1},
        {"label": _("Geo / Material Layer"), "fieldname": "geo_ref_description", "fieldtype": "Data", "width": 250},
        {"label": _("Total BCMs"), "fieldname": "total_bcm", "fieldtype": "Float", "width": 120},
        {"label": _("Coal Tons"), "fieldname": "coal_tons", "fieldtype": "Float", "width": 120},
    ]

def get_shift_field(table_name: str):
    cols = frappe.db.get_table_columns(table_name)
    if "shift" in cols:
        return "shift"
    if "shift_type" in cols:
        return "shift_type"
    return None

def get_data(filters):
    hp_shift_col = get_shift_field("Hourly Production")
    shift_condition = f" AND hp.{hp_shift_col} = %(shift)s" if filters.get("shift") and hp_shift_col else ""

    truck_totals = frappe.db.sql(f"""
        SELECT
            tl.mat_type,
            tl.geo_mat_layer_truck AS geo_ref_description,
            SUM(tl.bcms) AS total_bcm
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.location = %(site)s
          {shift_condition}
        GROUP BY tl.mat_type, tl.geo_mat_layer_truck
    """, filters, as_dict=True)

    dozer_totals = frappe.db.sql(f"""
        SELECT
            dp.dozer_geo_mat_layer AS geo_ref_description,
            dp.dozer_geo_mat_layer AS mat_type,
            SUM(dp.bcm_hour) AS total_bcm
        FROM `tabHourly Production` hp
        JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.location = %(site)s
          {shift_condition}
        GROUP BY dp.dozer_geo_mat_layer
    """, filters, as_dict=True)

    combined = truck_totals + dozer_totals

    def classify(mat_type):
        if not mat_type:
            return "Unassigned"
        mt = mat_type.lower()
        if "coal" in mt:
            return "Coal"
        elif "hard" in mt:
            return "Hards"
        elif "soft" in mt:
            return "Softs"
        return "Other"

    grouped_results = {}
    grand_total_bcm = 0
    grand_total_tons = 0

    for r in combined:
        category = classify(r["mat_type"])
        bcm_val = r["total_bcm"] or 0
        geo_desc = r["geo_ref_description"] or "Unassigned"

        coal_tons = bcm_val * 1.5 if category == "Coal" else None

        if category not in grouped_results:
            grouped_results[category] = {"total": 0, "total_tons": 0, "children": []}

        grouped_results[category]["total"] += bcm_val
        grouped_results[category]["total_tons"] += coal_tons or 0
        grouped_results[category]["children"].append({
            "mat_type": None,
            "geo_ref_description": geo_desc,
            "total_bcm": bcm_val,
            "coal_tons": coal_tons,
            "indent": 1
        })

        grand_total_bcm += bcm_val
        grand_total_tons += coal_tons or 0

    results = []
    for category in ["Coal", "Hards", "Softs", "Other", "Unassigned"]:
        if category in grouped_results:
            results.append({
                "mat_type": category,
                "geo_ref_description": None,
                "total_bcm": grouped_results[category]["total"],
                "coal_tons": grouped_results[category]["total_tons"] if category == "Coal" else None,
                "indent": 0
            })
            results.extend(sorted(
                grouped_results[category]["children"],
                key=lambda x: str(x.get("geo_ref_description") or "")
            ))

    return results, grand_total_bcm, grand_total_tons

def get_report_summary(grand_total_bcm, grand_total_tons):
    summary = [
        {
            "label": _("Grand Total BCMs"),
            "value": f"{grand_total_bcm:,.0f}",
            "indicator": "Blue"
        },
    ]
    if grand_total_tons:
        summary.append({
            "label": _("Grand Total Coal Tons"),
            "value": f"{grand_total_tons:,.0f}",
            "indicator": "Green"
        })
    return summary







































