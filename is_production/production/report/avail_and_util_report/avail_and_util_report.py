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
        {"label": "General & Specific Other Lost Hours", "fieldname": "captured_other_lost_hours", "fieldtype": "Float", "width": 180, "precision": 1},
        {"label": "Other Lost Hours Variance", "fieldname": "other_lost_hours_variance", "fieldtype": "Float", "width": 150, "precision": 1},
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
            data.append(summary_row(
                date_rows,
                indent=1,
                asset_category=cat,
                shift_date=date,
                location=(filters.get("location") or None),
                sum_hours=True
            ))


            for asset, rows in assets.items():
                combined = combine_shifts(rows)

                # give summary row keys so attach_reasons can map (location, shift_date)
                data.append(summary_row(
                    [combined],
                    indent=2,
                    asset_category=cat,
                    asset_name=asset,
                    shift_date=date,
                    location=(rows[0].get("location") if rows else None)
                ))


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

    # Recalc DATE totals (indent=1) from ASSET totals (indent=2)
    def r1(v): return round(v or 0, 1)

    date_totals_map = {}
    for row in data:
        if row.get("indent") == 2 and row.get("shift_date") and row.get("asset_category"):
            k = (row.get("asset_category"), str(row.get("shift_date")), row.get("location"))
            date_totals_map.setdefault(k, []).append(row)

    for row in data:
        if row.get("indent") == 1 and row.get("shift_date") and row.get("asset_category"):
            k = (row.get("asset_category"), str(row.get("shift_date")), row.get("location"))
            children = date_totals_map.get(k, [])
            if not children:
                continue

            def s(field): return sum((c.get(field) or 0) for c in children)

            for f in [
                "shift_required_hours", "shift_working_hours",
                "shift_breakdown_hours", "shift_available_hours",
                "shift_other_lost_hours",
                "captured_other_lost_hours",
                "other_lost_hours_variance",
            ]:
                row[f] = r1(s(f))

            # keep % as average across asset totals for that date
            count = len(children)
            row["plant_shift_availability"] = r1(
                sum((c.get("plant_shift_availability") or 0) for c in children) / count if count else 0
            )
            row["plant_shift_utilisation"] = r1(
                sum((c.get("plant_shift_utilisation") or 0) for c in children) / count if count else 0
            )



    # Recalc category totals (indent=0) from date totals (indent=1)
    def r1(v): return round(v or 0, 1)

    date_totals_by_cat = {}
    for row in data:
        if row.get("indent") == 1 and row.get("asset_category") and row.get("shift_date"):
            date_totals_by_cat.setdefault(row["asset_category"], []).append(row)

    for row in data:
        if row.get("indent") == 0 and row.get("asset_category") in date_totals_by_cat:
            rows = date_totals_by_cat[row["asset_category"]]

            def s(field): return sum((r.get(field) or 0) for r in rows)
            count = len(rows)

            # sum these across ALL dates
            for f in [
                "shift_required_hours", "shift_working_hours",
                "shift_breakdown_hours", "shift_available_hours",
                "shift_other_lost_hours",
                "captured_other_lost_hours",
                "other_lost_hours_variance",
            ]:
                row[f] = r1(s(f))

            # keep % as average across dates
            row["plant_shift_availability"] = r1(
                sum((r.get("plant_shift_availability") or 0) for r in rows) / count if count else 0
            )
            row["plant_shift_utilisation"] = r1(
                sum((r.get("plant_shift_utilisation") or 0) for r in rows) / count if count else 0
            )

    return data



# ---------------------------------------------------
# Combine Multiple Shifts (Day/Night)
# ---------------------------------------------------
def combine_shifts(rows):
    total = {}
    count = len(rows)

    # Sum hour fields
    for key in [
        "shift_required_hours", "shift_working_hours",
        "shift_breakdown_hours", "shift_available_hours", "shift_other_lost_hours"
    ]:
        total[key] = sum((r.get(key) or 0) for r in rows)

    # Captured other lost hours comes from Daily Lost Hours Recon (site/day),
    # so it will usually be the same for all shifts. Keep it as an average.
    total["captured_other_lost_hours"] = (
        sum((r.get("captured_other_lost_hours") or 0) for r in rows) / count if count else 0
    )

    # Percent fields = average
    total["plant_shift_availability"] = (
        sum((r.get("plant_shift_availability") or 0) for r in rows) / count if count else 0
    )
    total["plant_shift_utilisation"] = (
        sum((r.get("plant_shift_utilisation") or 0) for r in rows) / count if count else 0
    )

    # Variance = Other Lost Hrs - Captured Other Lost Hours
    total["other_lost_hours_variance"] = (
        (total.get("shift_other_lost_hours") or 0) - (total.get("captured_other_lost_hours") or 0)
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
        "captured_other_lost_hours": r1(h_fn("captured_other_lost_hours")),
        "other_lost_hours_variance": r1(h_fn("other_lost_hours_variance")),
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

    # --- Other Delay Reason (shared site/day comment) + Captured Other Lost Hours (by shift) ---
    # --- General captured (site/day/shift) ---
    delay_rows = frappe.db.sql("""
        SELECT
            location,
            shift_date,
            shift,
            gen_lost_hours_comments,
            total_general_lost_hours
        FROM `tabDaily Lost Hours Recon`
        WHERE shift_date BETWEEN %(start)s AND %(end)s
          {loc_filter}
    """.format(loc_filter="AND location = %(loc)s" if location else ""),
        {"start": start_date, "end": end_date, "loc": location}, as_dict=True)

    # --- Plant-specific captured (site/day/shift/asset) from child table ---
    plant_rows = frappe.db.sql("""
        SELECT
            r.location,
            r.shift_date,
            r.shift,
            a.asset_name,
            a.total_plant_specific_lost_hours
        FROM `tabDaily Lost Hours Recon` r
        INNER JOIN `tabDaily Lost Hours Assets` a
            ON a.parent = r.name
        WHERE r.shift_date BETWEEN %(start)s AND %(end)s
          {loc_filter}
          AND IFNULL(a.total_plant_specific_lost_hours, 0) != 0
    """.format(loc_filter="AND r.location = %(loc)s" if location else ""),
        {"start": start_date, "end": end_date, "loc": location}, as_dict=True)


    # comments stay site/day-level
    delay_map = {(r.location, str(r.shift_date)): (r.gen_lost_hours_comments or "") for r in delay_rows}

    # general captured is per site/day/shift
    captured_general_map = {
        (r.location, str(r.shift_date), (r.shift or "")): (r.total_general_lost_hours or 0)
        for r in delay_rows
    }

    # plant-specific captured is per site/day/shift/asset
    captured_plant_map = {}
    for r in plant_rows:
        k = (r.location, str(r.shift_date), (r.shift or ""), r.asset_name)
        captured_plant_map[k] = (captured_plant_map.get(k, 0) + (r.total_plant_specific_lost_hours or 0))



    # --- Attach to rows ---
    for row in data:
        if not row.get("shift_date"):
            continue

        # DATE totals must be summed from children (asset totals), not pulled from DLR
        if row.get("indent") == 1:
            continue

        k2 = (row.get("location"), str(row["shift_date"]))
        shift = (row.get("shift") or "")

        # Captured Other Lost Hours + variance
        asset = row.get("asset_name")

        def captured_for(s):
            general = captured_general_map.get((k2[0], k2[1], s), 0)
            plant = captured_plant_map.get((k2[0], k2[1], s, asset), 0) if asset else 0
            return general + plant

        if shift in ("Day", "Night"):
            captured = captured_for(shift)
        else:
            # TOTAL row (asset header): sum Day + Night for THIS asset
            captured = captured_for("Day") + captured_for("Night")

        row["captured_other_lost_hours"] = round(captured or 0, 1)
        row["other_lost_hours_variance"] = round(
            (row.get("shift_other_lost_hours") or 0) - (row.get("captured_other_lost_hours") or 0),
            1
        )


        # Breakdown Reason (per asset/day)
        if row.get("asset_name"):
            k1 = (row["asset_name"], str(row["shift_date"]), row.get("location"))
            row["breakdown_reason"] = "; ".join(breakdown_map.get(k1, [])) if k1 in breakdown_map else ""

        # Other Delay Reason (site/day comment)
        row["other_delay_reason"] = delay_map.get(k2, "")


    # Optional debug (can be commented out)
    frappe.log_error(
        f"Avail & Util Detailed fetched {len(breakdown_rows)} breakdowns and {len(delay_rows)} daily comments",
        "Avail Util Debug"
    )
