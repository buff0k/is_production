import frappe

def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data, grand_total = get_data(filters)
    return columns, data, None, None, get_report_summary(grand_total)

def get_columns():
    return [
        {"label": "Mining Area", "fieldname": "label", "fieldtype": "Data", "width": 250},
        {"label": "Truck + Shovel BCM", "fieldname": "ts_bcm", "fieldtype": "Float", "width": 150},
        {"label": "Dozing BCM", "fieldname": "dozer_bcm", "fieldtype": "Float", "width": 150},
        {"label": "Total BCM", "fieldname": "total_bcm", "fieldtype": "Float", "width": 150},
    ]

def get_data(filters):
    if not (filters.start_date and filters.end_date and filters.site):
        return [], 0

    shift_condition = ""
    if filters.shift:
        shift_condition = " AND hp.shift = %(shift)s"

    truck_rows = frappe.db.sql(f"""
        SELECT tl.mining_areas_trucks AS mining_area,
               SUM(tl.bcms) AS ts_bcm
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.location = %(site)s
          AND hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.docstatus < 2
          AND tl.mining_areas_trucks IS NOT NULL
          {shift_condition}
        GROUP BY tl.mining_areas_trucks
    """, filters, as_dict=True)

    dozer_rows = frappe.db.sql(f"""
        SELECT dp.mining_areas_dozer_child AS mining_area,
               SUM(dp.bcm_hour) AS dozer_bcm
        FROM `tabHourly Production` hp
        JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.location = %(site)s
          AND hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.docstatus < 2
          AND dp.mining_areas_dozer_child IS NOT NULL
          {shift_condition}
        GROUP BY dp.mining_areas_dozer_child
    """, filters, as_dict=True)

    combined, grand_total = {}, 0
    for r in truck_rows:
        combined.setdefault(r.mining_area, {"ts": 0, "dozer": 0})
        combined[r.mining_area]["ts"] += r.ts_bcm or 0
    for r in dozer_rows:
        combined.setdefault(r.mining_area, {"ts": 0, "dozer": 0})
        combined[r.mining_area]["dozer"] += r.dozer_bcm or 0

    results = []
    for area in sorted(combined.keys()):
        total = (combined[area]["ts"] or 0) + (combined[area]["dozer"] or 0)
        grand_total += total
        results.append({
            "label": area,
            "ts_bcm": None,
            "dozer_bcm": None,
            "total_bcm": total,
            "indent": 0
        })
        results.append({
            "label": "",
            "ts_bcm": combined[area]["ts"],
            "dozer_bcm": combined[area]["dozer"],
            "total_bcm": total,
            "indent": 1
        })
    return results, grand_total

def get_report_summary(grand_total):
    # ✅ Add comma as thousand separator for display
    formatted_total = f"{grand_total:,.0f}"
    return [{
        "label": "Grand Total BCMs",
        "value": formatted_total,
        "indicator": "Blue"
    }]








