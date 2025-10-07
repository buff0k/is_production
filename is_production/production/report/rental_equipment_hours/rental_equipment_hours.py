import frappe
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        return [], []

    # --- Report Columns ---
    columns = [
        {"label": "Asset", "fieldname": "asset_name", "fieldtype": "Data", "width": 220},
        {"label": "Category", "fieldname": "asset_category", "fieldtype": "Data", "width": 150},
        {"label": "Working Hours", "fieldname": "working_hours", "fieldtype": "Float", "width": 140},
    ]

    # --- Query Conditions ---
    conditions = [
        "ph.shift_date BETWEEN %(start_date)s AND %(end_date)s",
        "ph.location = %(site)s",
        "pa.asset_category NOT IN ('Dozer','ADT','Excavator')"  # 🚫 exclude these
    ]
    if filters.get("shift"):
        conditions.append("ph.shift = %(shift)s")

    where_clause = " AND ".join(conditions)

    # --- Fetch cumulative working hours ---
    data = frappe.db.sql(
        f"""
        SELECT
            pa.asset_name,
            pa.asset_category,
            SUM(pa.working_hours) as working_hours
        FROM `tabPre-Use Hours` ph
        JOIN `tabPre-use Assets` pa ON pa.parent = ph.name
        WHERE {where_clause}
        GROUP BY pa.asset_name, pa.asset_category
        ORDER BY pa.asset_category, pa.asset_name
        """,
        filters,
        as_dict=True
    )

    # --- Add Grand Total Row ---
    if data:
        total_hours = sum(flt(d.working_hours) for d in data)
        data.append({
            "asset_name": "🔢 Grand Total",
            "asset_category": "",
            "working_hours": total_hours
        })

    return columns, data



