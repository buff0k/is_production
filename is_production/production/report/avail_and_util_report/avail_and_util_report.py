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
        {"label": "Util (%)", "fieldname": "plant_shift_utilisation", "fieldtype": "Percent", "width": 75, "precision": 1},
        {"label": "Breakdown Reason", "fieldname": "breakdown_reason", "fieldtype": "Data", "width": 200},
        {"label": "Other Delay Reason", "fieldname": "other_delay_reason", "fieldtype": "Data", "width": 220}
    ]


# ---------------------------------------------------
# Fetch and Group Data
# ---------------------------------------------------
def get_grouped_data(filters):
    conditions = []
    args = []

    # Dynamic filters
    if filters.get("start_date"):
        conditions.append("shift_date >= %s")
        args.append(filters["start_date"])
    if filters.get("end_date"):
        conditions.append("shift_date <= %s")
        args.append(filters["end_date"])
    if filters.get("location"):
        conditions.append("location = %s")
        args.append(filters["location"])

    condition_str = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Query main Availability and Utilisation data
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
        ORDER BY asset_category, shift_date, asset_name, shift
    """, tuple(args), as_dict=True)

    if not records:
        frappe.msgprint("No records found for the selected filters.")
        return []

    def r1(v): return round(v or 0, 1)

    # Grouping: Category → Date → Asset → Shifts
    grouped = {}
    for r in records:
        cat = r["asset_category"] or "Uncategorised"
        date = str(r["shift_date"])
        asset = r["asset_name"]
        grouped.setdefault(cat, {}).setdefault(date, {}).setdefault(asset, []).append(r)

    data = []
    for cat, date_groups in grouped.items():
        cat_rows = [r for d in date_groups.values() for a in d.values() for r in a]
        data.append(summary_row(cat_rows, indent=0, asset_category=cat, sum_hours=False))

        for date, assets in date_groups.items():
            date_rows = [r for a in assets.values() for r in a]
            data.append(summary_row(date_rows, indent=1, shift_date=date, sum_hours=True))

            for asset, rows in assets.items():
                combined = combine_shifts(rows)
                data.append(summary_row([combined], indent=2, asset_name=asset))

                for row in rows:
                    row["indent"] = 3
                    # Keep shift_date and asset_name for lookups
                    for f in [
                        "shift_required_hours", "shift_working_hours",
                        "shift_breakdown_hours", "shift_available_hours",
                        "shift_other_lost_hours", "plant_shift_availability",
                        "plant_shift_utilisation"
                    ]:
                        row[f] = r1(row.get(f))
                    data.append(row)

    # Attach breakdown and delay reasons
    attach_reasons(data, filters)
    return data


# ---------------------------------------------------
# Combine Multiple Shifts (Day/Night)
# ---------------------------------------------------
def combine_shifts(rows):
    total = {}
    count = len(rows)
    for key in [
        "shift_required_hours", "shift_working_hours",
        "shift_breakdown_hours", "shift_available_hours", "shift_other_lost_hours"
    ]:
        total[key] = sum((r.get(key) or 0) for r in rows)

    total["plant_shift_availability"] = (
        sum((r.get("plant_shift_availability") or 0) for r in rows) / count if count else 0
    )
    total["plant_shift_utilisation"] = (
        sum((r.get("plant_shift_utilisation") or 0) for r in rows) / count if count else 0
    )

    return total


# ---------------------------------------------------
# Summary Row Generator
# ---------------------------------------------------
def summary_row(rows, indent, sum_hours=False, **extra_fields):
    def r1(v): return round(v or 0, 1)
    count = len(rows)
    if count == 0:
        return {**extra_fields, "indent": indent}

    def avg(field): return sum((r.get(field) or 0) for r in rows) / count if count else 0
    def total(field): return sum((r.get(field) or 0) for r in rows)
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


# ---------------------------------------------------
# Attach Breakdown & Delay Reasons
# ---------------------------------------------------
def attach_reasons(data, filters):
    """
    Fetch breakdown_reason (per asset/day) and other_delay_reason
    (shared site/day comment from Daily Lost Hours Recon)
    """
    key_map = {(d.get("asset_name"), str(d.get("shift_date")), d.get("location"))
               for d in data if d.get("asset_name") and d.get("shift_date")}
    if not key_map:
        return

    asset_names = list({a for a, _, _ in key_map})
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    location = filters.get("location")

    # --- Breakdown Reason from Breakdown History ---
    breakdown_rows = frappe.db.sql("""
        SELECT
            bh.asset_name,
            DATE(bh.update_date_time) AS shift_date,
            bh.location,
            bh.breakdown_reason_updates
        FROM `tabBreakdown History` bh
        WHERE bh.asset_name IN %(assets)s
          AND DATE(bh.update_date_time) BETWEEN %(start)s AND %(end)s
    """, {"assets": tuple(asset_names), "start": start_date, "end": end_date}, as_dict=True)

    breakdown_map = {}
    for r in breakdown_rows:
        k = (r.asset_name, str(r.shift_date), r.location)
        breakdown_map.setdefault(k, []).append(r.breakdown_reason_updates)

    # --- Other Delay Reason (shared site/day comment) ---
    delay_rows = frappe.db.sql("""
        SELECT location, shift_date, gen_lost_hours_comments
        FROM `tabDaily Lost Hours Recon`
        WHERE shift_date BETWEEN %(start)s AND %(end)s
          {loc_filter}
    """.format(loc_filter="AND location = %(loc)s" if location else ""),
        {"start": start_date, "end": end_date, "loc": location}, as_dict=True)

    delay_map = {(r.location, str(r.shift_date)): r.gen_lost_hours_comments for r in delay_rows}

    # --- Attach to rows ---
    for row in data:
        if not row.get("asset_name") or not row.get("shift_date"):
            continue
        k1 = (row["asset_name"], str(row["shift_date"]), row.get("location"))
        k2 = (row.get("location"), str(row["shift_date"]))
        row["breakdown_reason"] = "; ".join(breakdown_map.get(k1, [])) if k1 in breakdown_map else ""
        row["other_delay_reason"] = delay_map.get(k2, "")

    # Optional debug (can be commented out)
    frappe.log_error(
        f"Avail & Util Detailed fetched {len(breakdown_rows)} breakdowns and {len(delay_rows)} daily comments",
        "Avail Util Debug"
    )
