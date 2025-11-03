import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_collapsed_summary(filters)
    if not data:
        frappe.msgprint("⚠️ No records found for the selected filters or date range.")
    return columns, data


# -------------------------------------------------------
# Columns — compact, fits entire report on one screen
# -------------------------------------------------------
def get_columns():
    return [
        {"label": "Category", "fieldname": "asset_category", "fieldtype": "Data", "width": 95},
        {"label": "Asset", "fieldname": "asset_name", "fieldtype": "Link", "options": "Asset", "width": 90},
        {"label": "Site", "fieldname": "location", "fieldtype": "Link", "options": "Location", "width": 90},
        {"label": "Req Hrs", "fieldname": "shift_required_hours", "fieldtype": "Float", "width": 65, "precision": 1},
        {"label": "Work Hrs", "fieldname": "shift_working_hours", "fieldtype": "Float", "width": 65, "precision": 1},
        {"label": "Brkdwn", "fieldname": "shift_breakdown_hours", "fieldtype": "Float", "width": 65, "precision": 1},
        {"label": "Avail Hrs", "fieldname": "shift_available_hours", "fieldtype": "Float", "width": 70, "precision": 1},
        {"label": "Lost Hrs", "fieldname": "shift_other_lost_hours", "fieldtype": "Float", "width": 65, "precision": 1},
        {"label": "Avail %", "fieldname": "plant_shift_availability", "fieldtype": "Percent", "width": 65, "precision": 1},
        {"label": "Util %", "fieldname": "plant_shift_utilisation", "fieldtype": "Percent", "width": 65, "precision": 1},
        {"label": "Breakdown Reason", "fieldname": "breakdown_reason", "fieldtype": "Data", "width": 100},
        {"label": "Delay Reason", "fieldname": "delay_reason", "fieldtype": "Data", "width": 100},
        {"label": "Planned Maint. Reason", "fieldname": "planned_maintenance_reason", "fieldtype": "Data", "width": 110}
    ]


# -------------------------------------------------------
# Data Logic — grouped and collapsible by Asset Category
# -------------------------------------------------------
def get_collapsed_summary(filters):
    conditions = build_conditions(filters)

    # Fetch grouped numeric data (no reason fields yet)
    records = frappe.db.sql(f"""
        SELECT
            COALESCE(asset_category, 'Uncategorised') AS asset_category,
            asset_name,
            location,
            SUM(shift_required_hours) AS shift_required_hours,
            SUM(shift_working_hours) AS shift_working_hours,
            SUM(shift_breakdown_hours) AS shift_breakdown_hours,
            SUM(shift_available_hours) AS shift_available_hours,
            SUM(shift_other_lost_hours) AS shift_other_lost_hours,
            AVG(plant_shift_availability) AS plant_shift_availability,
            AVG(plant_shift_utilisation) AS plant_shift_utilisation
        FROM `tabAvailability and Utilisation`
        {conditions}
        GROUP BY COALESCE(asset_category, 'Uncategorised'), asset_name, location
        ORDER BY asset_category, asset_name
    """, as_dict=True)

    if not records:
        return []

    grouped = {}
    for row in records:
        category = row["asset_category"]
        grouped.setdefault(category, []).append(row)

    data = []

    for category, rows in grouped.items():
        # Category header (collapsible)
        cat_row = summary_row(rows, asset_category=category)
        cat_row.update({
            "asset_name": "",
            "location": "",
            "breakdown_reason": "",
            "delay_reason": "",
            "planned_maintenance_reason": "",
            "indent": 0
        })
        data.append(cat_row)

        # Asset-level rows
        for r in rows:
            round_row(r)
            r["asset_category"] = ""
            r["indent"] = 1
            # Placeholder empty values for now
            r["breakdown_reason"] = ""
            r["delay_reason"] = ""
            r["planned_maintenance_reason"] = ""
            data.append(r)

    # Add grand total
    total_row = summary_row(records, asset_category="GRAND TOTAL")
    total_row.update({
        "asset_name": "",
        "location": "",
        "breakdown_reason": "",
        "delay_reason": "",
        "planned_maintenance_reason": "",
        "indent": 0
    })
    data.append(total_row)

    return data


# -------------------------------------------------------
# Helpers
# -------------------------------------------------------
def summary_row(rows, **extra_fields):
    """Compute subtotal/average for a group of rows"""
    def r1(v): return round(v or 0, 1)
    count = len(rows)
    def avg(field): return sum((r.get(field) or 0) for r in rows) / count if count else 0
    def total(field): return sum((r.get(field) or 0) for r in rows)

    return {
        **extra_fields,
        "shift_required_hours": r1(total("shift_required_hours")),
        "shift_working_hours": r1(total("shift_working_hours")),
        "shift_breakdown_hours": r1(total("shift_breakdown_hours")),
        "shift_available_hours": r1(total("shift_available_hours")),
        "shift_other_lost_hours": r1(total("shift_other_lost_hours")),
        "plant_shift_availability": r1(avg("plant_shift_availability")),
        "plant_shift_utilisation": r1(avg("plant_shift_utilisation")),
    }


def round_row(row):
    """Round numeric fields"""
    for f in [
        "shift_required_hours", "shift_working_hours", "shift_breakdown_hours",
        "shift_available_hours", "shift_other_lost_hours",
        "plant_shift_availability", "plant_shift_utilisation"
    ]:
        row[f] = round(row.get(f) or 0, 1)


def build_conditions(filters):
    """Flexible WHERE clause for any date range + optional site"""
    conditions = []
    if filters.get("start_date") and filters.get("end_date"):
        conditions.append(f"shift_date BETWEEN '{filters.get('start_date')}' AND '{filters.get('end_date')}'")
    elif filters.get("start_date"):
        conditions.append(f"shift_date >= '{filters.get('start_date')}'")
    elif filters.get("end_date"):
        conditions.append(f"shift_date <= '{filters.get('end_date')}'")

    if filters.get("site"):
        conditions.append(f"location = '{filters.get('site')}'")

    return "WHERE " + " AND ".join(conditions) if conditions else ""
