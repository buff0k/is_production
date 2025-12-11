import frappe
from frappe import _

def execute(filters=None):
    filters = frappe._dict(filters or {})

    # Required fields
    if not (filters.start_date and filters.end_date and filters.site):
        return [], [], None, None, []

    columns = get_columns()
    data, total_bcm = get_data(filters)

    summary = [{
        "label": "Total BCM",
        "value": f"{total_bcm:,.0f}",
        "indicator": "Blue"
    }]

    return columns, data, None, None, summary


# -------------------------------------------------------------
# Columns
# -------------------------------------------------------------
def get_columns():
    return [
        {"label": _("Excavator"), "fieldname": "excavator", "fieldtype": "Data", "width": 150, "group": 1},
        {"label": _("Truck"), "fieldname": "truck", "fieldtype": "Data", "width": 130},
        {"label": _("Mining Area"), "fieldname": "mining_area", "fieldtype": "Data", "width": 150},
        {"label": _("Material Type"), "fieldname": "mat_type", "fieldtype": "Data", "width": 140},
        {"label": _("BCMs"), "fieldname": "bcms", "fieldtype": "Float", "width": 120},
    ]


# -------------------------------------------------------------
# Main Data Logic
# -------------------------------------------------------------
def get_data(filters):
    # Setup query values
    values = {
        "start_date": filters.start_date,
        "end_date": filters.end_date,
        "site": filters.site,
    }

    # ---------------------------------------------------------
    # MACHINE FILTER (OPTIONAL)
    # ---------------------------------------------------------
    excavator_filter = ""
    if filters.get("machine"):
        excavator_filter = "AND tl.asset_name_shoval = %(machine)s"
        values["machine"] = filters.machine

    # ---------------------------------------------------------
    # SHIFT DETECTION (shift or shift_type)
    # ---------------------------------------------------------
    shift_col = None
    try:
        cols = frappe.db.get_table_columns("Hourly Production")
        if "shift" in cols:
            shift_col = "shift"
        elif "shift_type" in cols:
            shift_col = "shift_type"
    except:
        shift_col = None

    shift_condition = ""
    if filters.get("shift") and shift_col:
        shift_condition = f"AND hp.{shift_col} = %(shift)s"
        values["shift"] = filters.shift

    # ---------------------------------------------------------
    # QUERY
    # ---------------------------------------------------------
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
          {excavator_filter}
          {shift_condition}
        GROUP BY 
            tl.asset_name_shoval, 
            tl.asset_name_truck, 
            tl.mining_areas_trucks, 
            tl.mat_type
        ORDER BY 
            tl.asset_name_shoval, 
            tl.asset_name_truck, 
            tl.mining_areas_trucks
    """, values, as_dict=True)

    # ---------------------------------------------------------
    # BUILD HIERARCHY (Excavator → Truck → Material)
    # ---------------------------------------------------------
    grouped = {}
    total_bcm = 0

    for r in rows:
        excavator = r["excavator"] or "Unassigned"
        truck = r["truck"] or "Unassigned"

        grouped.setdefault(excavator, {"total": 0, "children": {}})

        grouped[excavator]["total"] += r["bcms"] or 0
        grouped[excavator]["children"].setdefault(truck, {"total": 0, "details": []})

        grouped[excavator]["children"][truck]["total"] += r["bcms"] or 0
        grouped[excavator]["children"][truck]["details"].append(r)

        total_bcm += r["bcms"] or 0

    # ---------------------------------------------------------
    # FLATTEN INTO INDENTED REPORT OUTPUT
    # ---------------------------------------------------------
    output = []

    for excavator in sorted(grouped.keys()):
        # Level 0: Excavator
        output.append({
            "excavator": excavator,
            "truck": None,
            "mining_area": None,
            "mat_type": None,
            "bcms": grouped[excavator]["total"],
            "indent": 0
        })

        for truck in sorted(grouped[excavator]["children"].keys()):
            truck_node = grouped[excavator]["children"][truck]

            # Level 1: Truck
            output.append({
                "excavator": None,
                "truck": truck,
                "mining_area": None,
                "mat_type": None,
                "bcms": truck_node["total"],
                "indent": 1
            })

            # Level 2: Material rows
            for d in truck_node["details"]:
                output.append({
                    "excavator": None,
                    "truck": None,
                    "mining_area": d["mining_area"],
                    "mat_type": d["mat_type"],
                    "bcms": d["bcms"],
                    "indent": 2
                })

    return output, total_bcm
