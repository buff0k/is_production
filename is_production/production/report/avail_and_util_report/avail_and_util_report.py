import frappe

def execute(filters=None):
    """
    Main function executed when running the report.
    Returns columns and data.
    """
    columns = get_columns()
    data = get_grouped_data(filters)
    return columns, data


# ---------------------------------------------------
# Define Report Columns
# ---------------------------------------------------
def get_columns():
    return [
        {"label": "Asset Category", "fieldname": "asset_category", "fieldtype": "Data", "width": 110},
        {"label": "Shift Date", "fieldname": "shift_date", "fieldtype": "Date", "width": 95},
        {"label": "Asset Name", "fieldname": "asset_name", "fieldtype": "Link", "options": "Asset", "width": 100},
        {"label": "Shift", "fieldname": "shift", "fieldtype": "Data", "width": 70},
        {"label": "Location", "fieldname": "location", "fieldtype": "Link", "options": "Location", "width": 100},
        {"label": "Req Hrs", "fieldname": "shift_required_hours", "fieldtype": "Float", "width": 75, "precision": 1},
        {"label": "Work Hrs", "fieldname": "shift_working_hours", "fieldtype": "Float", "width": 75, "precision": 1},
        {"label": "Brkdwn Hrs", "fieldname": "shift_breakdown_hours", "fieldtype": "Float", "width": 75, "precision": 1},
        {"label": "Avail Hrs", "fieldname": "shift_available_hours", "fieldtype": "Float", "width": 75, "precision": 1},
        {"label": "Other Lost Hrs", "fieldname": "shift_other_lost_hours", "fieldtype": "Float", "width": 90, "precision": 1},
        {"label": "Avail (%)", "fieldname": "plant_shift_availability", "fieldtype": "Percent", "width": 75, "precision": 1},
        {"label": "Util (%)", "fieldname": "plant_shift_utilisation", "fieldtype": "Percent", "width": 75, "precision": 1}
    ]


# ---------------------------------------------------
# Fetch Data and Build Hierarchical Structure
# ---------------------------------------------------
def get_grouped_data(filters):
    conditions = []

    # --- Apply filters dynamically ---
    if filters.get("start_date") and filters.get("end_date"):
        conditions.append(f"shift_date BETWEEN '{filters.get('start_date')}' AND '{filters.get('end_date')}'")
    elif filters.get("start_date"):
        conditions.append(f"shift_date >= '{filters.get('start_date')}'")
    elif filters.get("end_date"):
        conditions.append(f"shift_date <= '{filters.get('end_date')}'")

    if filters.get("location"):
        conditions.append(f"location = '{filters.get('location')}'")

    condition_str = " AND ".join(conditions)
    if condition_str:
        condition_str = "WHERE " + condition_str

    # --- Query the Availability and Utilisation doctype ---
    records = frappe.db.sql(f"""
        SELECT
            asset_category,
            shift_date,
            asset_name,
            shift,
            location,
            shift_required_hours,
            shift_working_hours,
            shift_breakdown_hours,
            shift_available_hours,
            shift_other_lost_hours,
            plant_shift_availability,
            plant_shift_utilisation
        FROM `tabAvailability and Utilisation`
        {condition_str}
        ORDER BY asset_category ASC, shift_date ASC, asset_name ASC, shift ASC
    """, as_dict=True)

    if not records:
        frappe.msgprint("No records found for the selected filters.")
        return []

    def r1(val):
        """Round safely to one decimal place."""
        return round(val or 0, 1)

    # --- Build dictionary structure: Category → Date → Asset → Shifts ---
    grouped = {}
    for row in records:
        cat = row["asset_category"] or "Uncategorised"
        date = str(row["shift_date"])
        asset = row["asset_name"]

        grouped.setdefault(cat, {})
        grouped[cat].setdefault(date, {})
        grouped[cat][date].setdefault(asset, [])
        grouped[cat][date][asset].append(row)

    data = []

    # --- Build hierarchy ---
    for category, date_groups in grouped.items():
        # Level 0: Category summary (averages)
        cat_rows = [r for d in date_groups.values() for a in d.values() for r in a]
        data.append(summary_row(cat_rows, indent=0, asset_category=category, sum_hours=False))

        for date, assets in date_groups.items():
            # Level 1: Date summary (sum hours + average percentages)
            date_rows = [r for a in assets.values() for r in a]
            data.append(summary_row(date_rows, indent=1, shift_date=date, sum_hours=True))

            for asset, rows in assets.items():
                # Combine Day/Night for asset-level summary
                combined = combine_shifts(rows)
                data.append(summary_row([combined], indent=2, asset_name=asset))

                # Level 3: Shift details (actual Day/Night entries)
                for row in rows:
                    row["indent"] = 3
                    row["asset_category"] = ""
                    row["shift_date"] = ""
                    row["asset_name"] = ""
                    # Force one-decimal precision for numeric fields
                    for f in [
                        "shift_required_hours", "shift_working_hours",
                        "shift_breakdown_hours", "shift_available_hours",
                        "shift_other_lost_hours", "plant_shift_availability",
                        "plant_shift_utilisation"
                    ]:
                        row[f] = r1(row.get(f))
                    data.append(row)

    return data


# ---------------------------------------------------
# Combine Shifts for Asset-Level Summary
# ---------------------------------------------------
def combine_shifts(rows):
    """
    Combine all shifts (Day/Night/etc) for one asset on one date.
    Sum hours, average percentage fields.
    """
    total = {}
    count = len(rows)
    # Sum hour-type fields
    for key in [
        "shift_required_hours", "shift_working_hours", "shift_breakdown_hours",
        "shift_available_hours", "shift_other_lost_hours"
    ]:
        total[key] = sum((r.get(key) or 0) for r in rows)

    # Average percentage fields
    total["plant_shift_availability"] = (
        sum((r.get("plant_shift_availability") or 0) for r in rows) / count if count else 0
    )
    total["plant_shift_utilisation"] = (
        sum((r.get("plant_shift_utilisation") or 0) for r in rows) / count if count else 0
    )

    return total


# ---------------------------------------------------
# Summary Row Generator (Category, Date, Asset levels)
# ---------------------------------------------------
def summary_row(rows, indent, sum_hours=False, **extra_fields):
    """
    Creates a summary row:
      - If sum_hours=True, sums hour fields and averages % fields (used for date-level)
      - If sum_hours=False, averages all fields (used for category-level)
    """
    def r1(v): return round(v or 0, 1)
    count = len(rows)
    if count == 0:
        return {**extra_fields, "indent": indent}

    def avg(field):
        return sum((r.get(field) or 0) for r in rows) / count if count else 0

    def total(field):
        return sum((r.get(field) or 0) for r in rows)

    # For category-level we average hours, for date-level we sum them
    h_fn = total if sum_hours else avg

    return {
        **extra_fields,
        "shift_required_hours": r1(h_fn("shift_required_hours")),
        "shift_working_hours": r1(h_fn("shift_working_hours")),
        "shift_breakdown_hours": r1(h_fn("shift_breakdown_hours")),
        "shift_available_hours": r1(h_fn("shift_available_hours")),
        "shift_other_lost_hours": r1(h_fn("shift_other_lost_hours")),
        "plant_shift_availability": r1(avg("plant_shift_availability")),
        "plant_shift_utilisation": r1(avg("plant_shift_utilisation")),
        "indent": indent
    }