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
        {"label": "Mechanical Downtime", "fieldname": "shift_breakdown_hours", "fieldtype": "Float", "width": 125, "precision": 1},
        {"label": "Planned Downtime", "fieldname": "planned_downtime", "fieldtype": "Float", "width": 115, "precision": 1},
        {"label": "Actual Hours", "fieldname": "actual_hours", "fieldtype": "Float", "width": 100, "precision": 1},
        {"label": "Actual Service Time", "fieldname": "actual_service_time", "fieldtype": "Float", "width": 130, "precision": 1},
        {"label": "Actual Breakdown Time", "fieldname": "actual_breakdown_time", "fieldtype": "Float", "width": 145, "precision": 1},
        {"label": "Actual Planned Maintenance Time", "fieldname": "actual_planned_maintenance_time", "fieldtype": "Float", "width": 190, "precision": 1},
        {"label": "Actual Inspection Time", "fieldname": "actual_inspection_time", "fieldtype": "Float", "width": 140, "precision": 1},
        {"label": "Avail Hrs", "fieldname": "shift_available_hours", "fieldtype": "Float", "width": 75, "precision": 1},
        {"label": "Other Lost Hrs", "fieldname": "shift_other_lost_hours", "fieldtype": "Float", "width": 90, "precision": 1},
        {"label": "General & Specific Other Lost Hours", "fieldname": "captured_other_lost_hours", "fieldtype": "Float", "width": 180, "precision": 1},
        {"label": "Other Lost Hours Variance", "fieldname": "other_lost_hours_variance", "fieldtype": "Float", "width": 150, "precision": 1},
        {"label": "Avail (%)", "fieldname": "plant_shift_availability", "fieldtype": "Percent", "width": 75, "precision": 1},
        {"label": "Util (%)", "fieldname": "plant_shift_utilisation", "fieldtype": "Percent", "width": 75, "precision": 1},
        {"label": "Breakdown Reason", "fieldname": "breakdown_reason", "fieldtype": "Data", "width": 200},
        {"label": "Other Delay Reason", "fieldname": "other_delay_reason", "fieldtype": "Data", "width": 220}
    ]




MSR_TIME_FIELDS = [
    "actual_service_time",
    "actual_breakdown_time",
    "actual_planned_maintenance_time",
    "actual_inspection_time",
]

SUM_FIELDS = [
    "shift_required_hours",
    "shift_working_hours",
    "shift_breakdown_hours",
    "planned_downtime",
    "actual_hours",
    "actual_service_time",
    "actual_breakdown_time",
    "actual_planned_maintenance_time",
    "actual_inspection_time",
    "shift_available_hours",
    "shift_other_lost_hours",
    "captured_other_lost_hours",
    "other_lost_hours_variance",
]

AVG_FIELDS = [
    "plant_shift_availability",
    "plant_shift_utilisation",
]


def r1(v):
    return round(v or 0, 1)


def get_shift_window(shift, shift_date):
    shift_date = str(shift_date)

    if shift == "Day":
        return (
            frappe.utils.get_datetime(f"{shift_date} 06:00:00"),
            frappe.utils.get_datetime(f"{shift_date} 18:00:00"),
        )

    if shift == "Night":
        start = frappe.utils.get_datetime(f"{shift_date} 18:00:00")
        end = frappe.utils.add_to_date(start, days=1, as_datetime=True, hours=12)
        return start, end

    if shift == "Morning":
        return (
            frappe.utils.get_datetime(f"{shift_date} 06:00:00"),
            frappe.utils.get_datetime(f"{shift_date} 14:00:00"),
        )

    if shift == "Afternoon":
        return (
            frappe.utils.get_datetime(f"{shift_date} 14:00:00"),
            frappe.utils.get_datetime(f"{shift_date} 22:00:00"),
        )

    start = frappe.utils.get_datetime(f"{shift_date} 00:00:00")
    end = frappe.utils.add_to_date(start, days=1, as_datetime=True)
    return start, end


def get_overlap_hours(start1, end1, start2, end2):
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)

    if overlap_end <= overlap_start:
        return 0.0

    return (overlap_end - overlap_start).total_seconds() / 3600.0




def get_planned_downtime_value(location, shift_date, indent):
    site = (location or "").strip().lower()
    day_of_week = frappe.utils.getdate(shift_date).weekday()  # Mon=0 ... Sun=6

    saturday_special_sites = {"koppie", "uitgevallen", "bankfontein", "kriel"}

    if day_of_week == 6:  # Sunday
        return 0.0

    if day_of_week == 5:  # Saturday
        if site in saturday_special_sites:
            return 4.0 if indent in (0, 1, 2) else 2.0
        return 6.0 if indent in (0, 1, 2) else 3.0

    # Weekdays
    return 6.0 if indent in (0, 1, 2) else 3.0


def get_actual_hours_value(location, shift_date, indent):
    site = (location or "").strip().lower()
    day_of_week = frappe.utils.getdate(shift_date).weekday()  # Mon=0 ... Sun=6

    saturday_special_sites = {"koppie", "uitgevallen", "bankfontein", "kriel"}

    if day_of_week == 6:  # Sunday
        return 0.0

    if day_of_week == 5:  # Saturday
        if site in saturday_special_sites:
            return 18.0 if indent in (0, 1, 2) else 9.0
        return 24.0 if indent in (0, 1, 2) else 12.0

    # Weekdays
    return 24.0 if indent in (0, 1, 2) else 12.0


def attach_planned_and_actual_hours(data):
    for row in data:
        if not row.get("shift_date"):
            row["planned_downtime"] = 0.0
            row["actual_hours"] = 0.0
            continue

        row["planned_downtime"] = r1(
            get_planned_downtime_value(row.get("location"), row.get("shift_date"), row.get("indent"))
        )
        row["actual_hours"] = r1(
            get_actual_hours_value(row.get("location"), row.get("shift_date"), row.get("indent"))
        )





def get_msr_time_map(filters):
    conditions = ["msr.service_date >= %(start_date)s", "msr.service_date <= %(end_date)s"]
    args = {
        "start_date": filters.get("start_date"),
        "end_date": filters.get("end_date"),
    }

    if filters.get("location"):
        conditions.append("msr.site = %(location)s")
        args["location"] = filters.get("location")

    msr_rows = frappe.db.sql(f"""
        SELECT
            msr.site AS location,
            msr.service_date,
            asset.asset_name AS asset_name,
            msr.start_time,
            msr.end_time,
            msr.total_time,
            msr.total_time_unavailable,
            msr.service_breakdown
        FROM `tabMechanical Service Report` msr
        LEFT JOIN `tabAsset` asset
            ON asset.name = msr.asset
        WHERE {' AND '.join(conditions)}
    """, args, as_dict=True)

    time_map = {}

    for row in msr_rows:
        if not row.get("location") or not row.get("service_date") or not row.get("asset_name"):
            continue
        if not row.get("start_time") or not row.get("end_time"):
            continue

        start_dt = frappe.utils.get_datetime(row.start_time)
        end_dt = frappe.utils.get_datetime(row.end_time)

        if end_dt <= start_dt:
            continue

        total_hours = (row.get("total_time") or 0) / 3600.0
        unavailable_hours = (row.get("total_time_unavailable") or 0) / 3600.0

        for shift in ("Day", "Night", "Morning", "Afternoon"):
            shift_start, shift_end = get_shift_window(shift, row.service_date)
            overlap_hours = get_overlap_hours(start_dt, end_dt, shift_start, shift_end)

            if overlap_hours <= 0:
                continue

            key = (row.location, str(row.service_date), row.asset_name, shift)
            bucket = time_map.setdefault(key, {field: 0.0 for field in MSR_TIME_FIELDS})

            if row.service_breakdown == "Service":
                bucket["actual_service_time"] += overlap_hours
            elif row.service_breakdown == "Breakdown":
                bucket["actual_breakdown_time"] += overlap_hours
            elif row.service_breakdown == "Planned Maintenance":
                bucket["actual_planned_maintenance_time"] += overlap_hours
            elif row.service_breakdown == "Inspection":
                bucket["actual_inspection_time"] += overlap_hours

    return time_map


def attach_msr_actuals(data, filters):
    time_map = get_msr_time_map(filters)

    for row in data:
        for field in MSR_TIME_FIELDS:
            row[field] = 0.0

        if row.get("indent") != 3:
            continue

        key = (
            row.get("location"),
            str(row.get("shift_date")),
            row.get("asset_name"),
            row.get("shift"),
        )
        values = time_map.get(key, {})

        for field in MSR_TIME_FIELDS:
            row[field] = r1(values.get(field, 0))


def recalculate_summary_rows(data):
    # indent 2 = asset totals from indent 3
    asset_map = {}
    for row in data:
        if row.get("indent") == 3:
            key = (
                row.get("asset_category"),
                str(row.get("shift_date")),
                row.get("location"),
                row.get("asset_name"),
            )
            asset_map.setdefault(key, []).append(row)

    for row in data:
        if row.get("indent") == 2:
            key = (
                row.get("asset_category"),
                str(row.get("shift_date")),
                row.get("location"),
                row.get("asset_name"),
            )
            children = asset_map.get(key, [])
            if not children:
                continue

            for field in SUM_FIELDS:
                row[field] = r1(sum((child.get(field) or 0) for child in children))

            for field in AVG_FIELDS:
                row[field] = r1(sum((child.get(field) or 0) for child in children) / len(children))

    # indent 1 = date totals from indent 2
    date_map = {}
    for row in data:
        if row.get("indent") == 2:
            key = (
                row.get("asset_category"),
                str(row.get("shift_date")),
                row.get("location"),
            )
            date_map.setdefault(key, []).append(row)

    for row in data:
        if row.get("indent") == 1:
            key = (
                row.get("asset_category"),
                str(row.get("shift_date")),
                row.get("location"),
            )
            children = date_map.get(key, [])
            if not children:
                continue

            for field in SUM_FIELDS:
                row[field] = r1(sum((child.get(field) or 0) for child in children))

            for field in AVG_FIELDS:
                row[field] = r1(sum((child.get(field) or 0) for child in children) / len(children))

    # indent 0 = category totals from indent 1
    category_map = {}
    for row in data:
        if row.get("indent") == 1:
            key = row.get("asset_category")
            category_map.setdefault(key, []).append(row)

    for row in data:
        if row.get("indent") == 0:
            children = category_map.get(row.get("asset_category"), [])
            if not children:
                continue

            for field in SUM_FIELDS:
                row[field] = r1(sum((child.get(field) or 0) for child in children))

            for field in AVG_FIELDS:
                row[field] = r1(sum((child.get(field) or 0) for child in children) / len(children))




# ---------------------------------------------------
# Fetch and Group Data
# ---------------------------------------------------


def get_grouped_data(filters):
    filters = filters or {}
    conditions = []
    args = []

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

    grouped = {}
    for record in records:
        cat = record["asset_category"] or "Uncategorised"
        date = str(record["shift_date"])
        asset = record["asset_name"]
        grouped.setdefault(cat, {}).setdefault(date, {}).setdefault(asset, []).append(record)

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

                    for field in [
                        "shift_required_hours",
                        "shift_working_hours",
                        "shift_breakdown_hours",
                        "planned_downtime",
                        "actual_hours",
                        "actual_service_time",
                        "actual_breakdown_time",
                        "actual_planned_maintenance_time",
                        "actual_inspection_time",
                        "shift_available_hours",
                        "shift_other_lost_hours",
                        "plant_shift_availability",
                        "plant_shift_utilisation",
                    ]:
                        row[field] = r1(row.get(field))

                    data.append(row)

    attach_reasons(data, filters)
    attach_msr_actuals(data, filters)
    attach_planned_and_actual_hours(data)
    recalculate_summary_rows(data)

    return data















# ---------------------------------------------------
# Combine Multiple Shifts (Day/Night)
# ---------------------------------------------------
def combine_shifts(rows):
    total = {}
    count = len(rows)

    # Sum hour fields
    for key in [
        "shift_required_hours",
        "shift_working_hours",
        "shift_breakdown_hours",
        "planned_downtime",
        "actual_hours",
        "actual_service_time",
        "actual_breakdown_time",
        "actual_planned_maintenance_time",
        "actual_inspection_time",
        "shift_available_hours",
        "shift_other_lost_hours",
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
        "planned_downtime": r1(h_fn("planned_downtime")),
        "actual_hours": r1(h_fn("actual_hours")),
        "actual_service_time": r1(h_fn("actual_service_time")),
        "actual_breakdown_time": r1(h_fn("actual_breakdown_time")),
        "actual_planned_maintenance_time": r1(h_fn("actual_planned_maintenance_time")),
        "actual_inspection_time": r1(h_fn("actual_inspection_time")),
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
