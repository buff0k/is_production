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
        return [], {"excavator_prods": [], "dozer_prods": []}

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
    excavator_prods = []
    dozer_prods = []

    for cat in ["Excavator", "ADT", "Dozer"]:
        total_hours = sum(m["hours"] for m in grouped[cat].values())
        total_output = sum(m["output"] for m in grouped[cat].values())

        # Machine rows
        machine_valid_prods = []
        for machine, info in grouped[cat].items():
            productivity = round(info["output"] / info["hours"], 2) if info["hours"] > 0 and info["output"] > 0 else 0
            if productivity > 0:
                machine_valid_prods.append(productivity)
                if cat == "Excavator":
                    excavator_prods.append(productivity)
                elif cat == "Dozer":
                    dozer_prods.append(productivity)

            results.append({
                "label": machine,
                "working_hours": info["hours"],
                "output": f"{info['output']:,.0f}",
                "productivity": productivity,
                "indent": 1,
                # 🔴 Highlight row if invalid
                "style": "background-color:#f8d7da;" if info["hours"] <= 0 or info["output"] == 0 else ""
            })

        # Category row productivity = average of valid machine productivity
        cat_prod = round(sum(machine_valid_prods) / len(machine_valid_prods), 2) if machine_valid_prods else 0

        results.insert(len(results) - len(grouped[cat]), {
            "label": cat,
            "working_hours": total_hours,
            "output": f"{total_output:,.0f}",
            "productivity": cat_prod,
            "indent": 0,
            # 🔴 Highlight if category has 0 hrs or 0 output
            "style": "background-color:#f8d7da;" if total_hours <= 0 or total_output == 0 else ""
        })

    grand_total = {
        "excavator_prods": excavator_prods,
        "dozer_prods": dozer_prods
    }
    return results, grand_total

def get_report_summary(grand_total):
    # Truck + Shovel Productivity (Excavator only)
    excavator_prods = grand_total.get("excavator_prods", [])
    ts_prod = round(sum(excavator_prods) / len(excavator_prods), 2) if excavator_prods else 0

    # Dozing Productivity (Dozer only)
    dozer_prods = grand_total.get("dozer_prods", [])
    dozer_prod = round(sum(dozer_prods) / len(dozer_prods), 2) if dozer_prods else 0

    return [
        {"label": _("Truck + Shovel Productivity"), "value": f"{ts_prod}", "indicator": "Blue"},
        {"label": _("Dozing Productivity"), "value": f"{dozer_prod}", "indicator": "Green"},
    ]







