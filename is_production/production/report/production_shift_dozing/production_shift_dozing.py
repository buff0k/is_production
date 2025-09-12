import frappe

def execute(filters=None):
    filters = frappe._dict(filters or {})
    data, grand_total = get_data(filters)
    return get_columns(), data, None, None, get_report_summary(grand_total)

def get_columns():
    return [
        {"label": "Dozer / Details", "fieldname": "label", "fieldtype": "Data", "width": 250},
        {"label": "BCM", "fieldname": "bcm_hour", "fieldtype": "Float", "width": 100},
        {"label": "Material Type", "fieldname": "mat_type", "fieldtype": "Data", "width": 150},
        {"label": "Mining Area", "fieldname": "mining_area", "fieldtype": "Data", "width": 150},
    ]

def get_shift_field(table_name: str):
    cols = frappe.db.get_table_columns(table_name)
    if "shift" in cols:
        return "shift"
    if "shift_type" in cols:
        return "shift_type"
    return None

def get_data(filters):
    if not (filters.start_date and filters.end_date and filters.site):
        return [], 0

    hp_shift_col = get_shift_field("Hourly Production")
    shift_condition = f" AND hp.{hp_shift_col} = %(shift)s" if filters.get("shift") and hp_shift_col else ""

    rows = frappe.db.sql(f"""
        SELECT dp.asset_name AS dozer,
               NULLIF(dp.dozer_geo_mat_layer, '') AS mat_type,
               NULLIF(dp.mining_areas_dozer_child, '') AS mining_area,
               SUM(dp.bcm_hour) AS bcm_hour
        FROM `tabHourly Production` hp
        JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.location = %(site)s
          AND hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.docstatus < 2
          {shift_condition}
        GROUP BY dp.asset_name, dp.dozer_geo_mat_layer, dp.mining_areas_dozer_child
        ORDER BY dp.asset_name
    """, filters, as_dict=True)

    grouped, grand_total = {}, 0
    unassigned_rows, unassigned_total = [], 0

    for r in rows:
        grand_total += r.bcm_hour or 0

        # ✅ If missing either mining_area OR material type → go to Unassigned
        if not r.mining_area or not r.mat_type:
            unassigned_total += r.bcm_hour or 0
            r.mining_area = r.mining_area or "Unassigned"
            r.mat_type = r.mat_type or "Unassigned"
            unassigned_rows.append(r)
            continue

        dozer = r.dozer or "Unassigned"
        grouped.setdefault(dozer, {"total": 0, "rows": []})
        grouped[dozer]["total"] += r.bcm_hour or 0
        grouped[dozer]["rows"].append(r)

    results = []
    # Regular dozers first
    for dozer in sorted(grouped.keys()):
        results.append({
            "label": dozer,
            "bcm_hour": grouped[dozer]["total"],
            "mat_type": None,
            "mining_area": None,
            "indent": 0
        })
        for d in grouped[dozer]["rows"]:
            results.append({
                "label": "",
                "bcm_hour": d.bcm_hour,
                "mat_type": d.mat_type,
                "mining_area": d.mining_area,
                "indent": 1
            })

    # Add dedicated Unassigned section at the bottom
    if unassigned_rows:
        results.append({
            "label": "Unassigned",
            "bcm_hour": unassigned_total,
            "mat_type": None,
            "mining_area": None,
            "indent": 0
        })
        for d in unassigned_rows:
            results.append({
                "label": "",
                "bcm_hour": d.bcm_hour,
                "mat_type": d.mat_type,
                "mining_area": d.mining_area,
                "indent": 1
            })

    return results, grand_total

def get_report_summary(grand_total):
    formatted_total = f"{grand_total:,.0f}"
    return [{
        "label": "Grand Total BCMs",
        "value": formatted_total,
        "indicator": "Blue"
    }]





















