# Copyright (c) 2025, Isambane Mining (Pty) Ltd
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns, data, grand_totals = get_columns(), *get_data(filters)
    return columns, data, None, None, get_report_summary(grand_totals)

def get_columns():
    return [
        {"label": _("Label"), "fieldname": "label", "fieldtype": "Data", "width": 220, "group": 1},
        {"label": _("Working Hours"), "fieldname": "working_hours", "fieldtype": "Float", "width": 120},
        {"label": _("Output"), "fieldname": "output", "fieldtype": "Data", "width": 150},
        {"label": _("Productivity (Output/Hr)"), "fieldname": "productivity", "fieldtype": "Float", "width": 160},
    ]

def normalize_category(cat: str) -> str:
    if not cat:
        return ""
    cat = cat.strip().lower()
    if "excavator" in cat:
        return "Excavator"
    if "dozer" in cat or "bulldozer" in cat:
        return "Dozer"
    if "adt" in cat or "truck" in cat or "rigid" in cat:
        return "ADT"
    return cat.title()

def get_shift_field(table_name: str):
    """Check if shift column exists in a table"""
    cols = frappe.db.get_table_columns(table_name)
    if "shift" in cols:
        return "shift"
    if "shift_type" in cols:
        return "shift_type"
    return None

def get_data(filters):
    if not (filters.start_date and filters.end_date and filters.site):
        return [], {"hours": 0, "output": 0}

    values = {
        "start_date": filters["start_date"],
        "end_date": filters["end_date"],
        "site": filters["site"],
        "machine_type": filters.get("machine_type"),
        "shift": filters.get("shift"),
    }

    # Detect which shift column is available
    hp_shift_col = get_shift_field("Hourly Production")
    pu_shift_col = get_shift_field("Pre-Use Hours")

    shift_condition_hp = f" AND hp.{hp_shift_col} = %(shift)s" if filters.get("shift") and hp_shift_col else ""
    shift_condition_pu = f" AND pu.{pu_shift_col} = %(shift)s" if filters.get("shift") and pu_shift_col else ""
    machine_condition = " AND pa.asset_category = %(machine_type)s" if filters.get("machine_type") else ""

    # 🚛 Truck Loads (ADT + Excavator)
    truck_rows = frappe.db.sql(f"""
        SELECT
            tl.asset_name_shoval AS excavator,
            tl.asset_name_truck AS adt,
            SUM(tl.bcms) AS bcm_output,
            tl.mat_type
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.location = %(site)s
          {shift_condition_hp}
        GROUP BY tl.asset_name_shoval, tl.asset_name_truck, tl.mat_type
    """, values, as_dict=True)

    # 🛠️ Dozer Production
    dozer_rows = frappe.db.sql(f"""
        SELECT
            dp.asset_name AS dozer,
            SUM(dp.bcm_hour) AS bcm_output,
            dp.dozer_geo_mat_layer AS mat_type
        FROM `tabHourly Production` hp
        JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.location = %(site)s
          {shift_condition_hp}
        GROUP BY dp.asset_name, dp.dozer_geo_mat_layer
    """, values, as_dict=True)

    # ⏱️ Pre-Use Hours
    preuse_rows = frappe.db.sql(f"""
        SELECT
            pa.asset_name,
            pa.asset_category,
            SUM(pa.working_hours) AS working_hours
        FROM `tabPre-Use Hours` pu
        JOIN `tabPre-use Assets` pa ON pa.parent = pu.name
        WHERE pu.shift_date BETWEEN %(start_date)s AND %(end_date)s
          AND pu.location = %(site)s
          {shift_condition_pu}
          {machine_condition}
        GROUP BY pa.asset_name, pa.asset_category
    """, values, as_dict=True)

    # 🔄 Normalize Pre-Use Hours
    hours_map = {}
    for r in preuse_rows:
        cat = normalize_category(r.asset_category)
        hours_map[(cat, (r.asset_name or "").strip())] = r.working_hours or 0

    grouped = {"Excavator": {}, "Dozer": {}, "ADT": {}}

    # ➕ Process Trucks
    for r in truck_rows:
        output_val = r.bcm_output or 0
        if r.mat_type and "coal" in (r.mat_type or "").lower():
            output_val *= 1.5
        if r.adt:
            adt_name = r.adt.strip()
            grouped["ADT"].setdefault(adt_name, {"hours": 0, "output": 0})
            grouped["ADT"][adt_name]["hours"] = hours_map.get(("ADT", adt_name), grouped["ADT"][adt_name]["hours"])
            grouped["ADT"][adt_name]["output"] += output_val
        if r.excavator:
            exc_name = r.excavator.strip()
            grouped["Excavator"].setdefault(exc_name, {"hours": 0, "output": 0})
            grouped["Excavator"][exc_name]["hours"] = hours_map.get(("Excavator", exc_name), grouped["Excavator"][exc_name]["hours"])
            grouped["Excavator"][exc_name]["output"] += output_val

    # ➕ Process Dozers
    for r in dozer_rows:
        output_val = r.bcm_output or 0
        if r.mat_type and "coal" in (r.mat_type or "").lower():
            output_val *= 1.5
        if r.dozer:
            dz_name = r.dozer.strip()
            grouped["Dozer"].setdefault(dz_name, {"hours": 0, "output": 0})
            grouped["Dozer"][dz_name]["hours"] = hours_map.get(("Dozer", dz_name), grouped["Dozer"][dz_name]["hours"])
            grouped["Dozer"][dz_name]["output"] += output_val

    # Ensure Pre-Use-only machines appear
    for (cat, machine), hrs in hours_map.items():
        if cat in grouped:
            grouped[cat].setdefault(machine, {"hours": hrs, "output": 0})
            if grouped[cat][machine]["hours"] == 0:
                grouped[cat][machine]["hours"] = hrs

    # 📊 Build results
    results = []
    ts_hours = ts_output = 0
    dozer_hours = dozer_output = 0

    for cat in ["Excavator", "ADT", "Dozer"]:
        total_hours = sum(m["hours"] for m in grouped[cat].values())
        total_output = sum(m["output"] for m in grouped[cat].values())
        if cat == "Excavator":
            ts_hours += total_hours
            ts_output += total_output
        elif cat == "Dozer":
            dozer_hours += total_hours
            dozer_output += total_output

        results.append({
            "label": cat,
            "working_hours": total_hours,
            "output": f"{total_output:,.0f}",
            "productivity": round(total_output / total_hours, 2) if total_hours else 0,
            "indent": 0
        })
        for machine, info in grouped[cat].items():
            results.append({
                "label": machine,
                "working_hours": info["hours"],
                "output": f"{info['output']:,.0f}",
                "productivity": round(info["output"] / info["hours"], 2) if info["hours"] else 0,
                "indent": 1
            })

    grand_total = {
        "ts_hours": ts_hours,
        "ts_output": ts_output,
        "dozer_hours": dozer_hours,
        "dozer_output": dozer_output,
    }
    return results, grand_total

def get_report_summary(grand_total):
    ts_prod = round(grand_total["ts_output"] / grand_total["ts_hours"], 2) if grand_total["ts_hours"] else 0
    dozer_prod = round(grand_total["dozer_output"] / grand_total["dozer_hours"], 2) if grand_total["dozer_hours"] else 0
    return [
        {"label": _("Truck + Shovel Productivity"), "value": f"{ts_prod}", "indicator": "Blue"},
        {"label": _("Dozing Productivity"), "value": f"{dozer_prod}", "indicator": "Green"},
    ]



