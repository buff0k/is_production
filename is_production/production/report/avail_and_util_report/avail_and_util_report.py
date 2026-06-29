import frappe
import datetime
from frappe.utils import now_datetime


EXCLUDED_ASSET_CATEGORIES = {
    "Grader",
    "Service Truck",
    "TLB",
    "Water Bowser",
    "Diesel Bowsers",
    "Drills",
    "Loader",
}



SPARE_SWING_PURPLE = "#e6d6ff"
SPARE_SWING_TEXT = "#4b0082"


def add_asset_identifiers(asset_set, asset_name):
    """Add both Asset.name and Asset.asset_name where possible, so matching works
    whether Availability and Utilisation stores the asset ID or display name.
    """
    if not asset_name:
        return

    value = str(asset_name).strip()
    if not value:
        return

    asset_set.add(value)

    try:
        asset_doc = frappe.db.get_value("Asset", value, ["name", "asset_name"], as_dict=True)
        if asset_doc:
            if asset_doc.get("name"):
                asset_set.add(str(asset_doc.get("name")).strip())
            if asset_doc.get("asset_name"):
                asset_set.add(str(asset_doc.get("asset_name")).strip())
    except Exception:
        pass


def get_spare_swing_asset_map(filters):
    """Find Spare/Swing machines from saved Monthly Production Planning data."""
    filters = filters or {}
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")

    if not start_date or not end_date:
        return {}

    args = {
        "start_date": start_date,
        "end_date": end_date,
    }

    conditions = [
        "mpp.docstatus < 2",
        "mpp.prod_month_start_date <= %(end_date)s",
        "mpp.prod_month_end_date >= %(start_date)s",
    ]

    if filters.get("location"):
        conditions.append("mpp.location = %(location)s")
        args["location"] = filters.get("location")

    condition_sql = " AND ".join(conditions)
    spare_map = {}

    def add_reason(asset_name, reason):
        identifiers = set()
        add_asset_identifiers(identifiers, asset_name)

        for identifier in identifiers:
            spare_map.setdefault(identifier, set()).add(reason)

    try:
        truck_rows = frappe.db.sql(f"""
            SELECT DISTINCT etl.truck AS asset_name
            FROM `tabMonthly Production Planning` mpp
            INNER JOIN `tabExcavator Truck Link` etl
                ON etl.parent = mpp.name
               AND etl.parenttype = 'Monthly Production Planning'
            WHERE {condition_sql}
              AND IFNULL(etl.truck, '') != ''
              AND IFNULL(etl.excavator, '') = ''
        """, args, as_dict=True)

        for row in truck_rows:
            add_reason(row.get("asset_name"), "Spare/Swing unit Truck")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Avail and Util Spare/Swing Trucks")
        frappe.clear_messages()

    try:
        excavator_rows = frappe.db.sql(f"""
            SELECT DISTINCT etl.excavator AS asset_name
            FROM `tabMonthly Production Planning` mpp
            INNER JOIN `tabExcavator Truck Link` etl
                ON etl.parent = mpp.name
               AND etl.parenttype = 'Monthly Production Planning'
            WHERE {condition_sql}
              AND IFNULL(etl.excavator, '') != ''
              AND IFNULL(etl.truck, '') = ''
              AND NOT EXISTS (
                  SELECT 1
                  FROM `tabExcavator Truck Link` assigned_etl
                  WHERE assigned_etl.parent = etl.parent
                    AND assigned_etl.parenttype = etl.parenttype
                    AND assigned_etl.excavator = etl.excavator
                    AND IFNULL(assigned_etl.truck, '') != ''
              )
        """, args, as_dict=True)

        for row in excavator_rows:
            add_reason(row.get("asset_name"), "Spare/Swing unit Excavator")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Avail and Util Spare/Swing Excavators")
        frappe.clear_messages()

    try:
        dozer_rows = frappe.db.sql(f"""
            SELECT DISTINCT dp.asset_name AS asset_name
            FROM `tabMonthly Production Planning` mpp
            INNER JOIN `tabDozers Planned` dp
                ON dp.parent = mpp.name
               AND dp.parenttype = 'Monthly Production Planning'
            WHERE {condition_sql}
              AND IFNULL(dp.asset_name, '') != ''
              AND IFNULL(dp.dozing_type, '') = ''
        """, args, as_dict=True)

        for row in dozer_rows:
            add_reason(row.get("asset_name"), "Spare/Swing unit Dozer")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Avail and Util Spare/Swing Dozers")
        frappe.clear_messages()

    return {
        asset_name: ", ".join(sorted(reasons))
        for asset_name, reasons in spare_map.items()
    }


def is_spare_swing_asset(asset_name, spare_swing_asset_map):
    if not asset_name or not spare_swing_asset_map:
        return False

    value = str(asset_name).strip()
    if value in spare_swing_asset_map:
        return True

    identifiers = set()
    add_asset_identifiers(identifiers, value)
    return any(identifier in spare_swing_asset_map for identifier in identifiers)


def get_spare_swing_reason(asset_name, spare_swing_asset_map):
    if not asset_name or not spare_swing_asset_map:
        return ""

    value = str(asset_name).strip()
    if value in spare_swing_asset_map:
        return spare_swing_asset_map.get(value) or ""

    identifiers = set()
    add_asset_identifiers(identifiers, value)
    for identifier in identifiers:
        if identifier in spare_swing_asset_map:
            return spare_swing_asset_map.get(identifier) or ""

    return ""


def apply_machine_scope_filter(records, filters, spare_swing_asset_map):
    """Filter detail records before grouping so summary totals and averages follow the filter."""
    filters = filters or {}
    machine_scope = filters.get("machine_scope") or "Include Swing/Spare"

    if machine_scope == "Include Swing/Spare":
        return records

    filtered_records = []

    for record in records:
        is_spare = is_spare_swing_asset(record.get("asset_name"), spare_swing_asset_map)

        if machine_scope == "Production Machines" and not is_spare:
            filtered_records.append(record)
        elif machine_scope == "Swing/Spare Machines" and is_spare:
            filtered_records.append(record)

    return filtered_records


def apply_spare_swing_flags(data, spare_swing_asset_map):
    if not spare_swing_asset_map:
        return data

    for row in data:
        asset_name = row.get("asset_name")
        reason = get_spare_swing_reason(asset_name, spare_swing_asset_map)

        if reason:
            row["is_spare_swing_unit"] = 1
            row["spare_swing_reason"] = reason
            row["spare_swing_background"] = SPARE_SWING_PURPLE
            row["spare_swing_text_colour"] = SPARE_SWING_TEXT

    return data


def execute(filters=None):
    columns = get_columns()
    data = get_grouped_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Asset Category", "fieldname": "asset_category", "fieldtype": "Data", "width": 140},
        {"label": "Shift Date", "fieldname": "shift_date", "fieldtype": "Date", "width": 95},
        {"label": "Asset Name", "fieldname": "asset_name", "fieldtype": "Link", "options": "Asset", "width": 120},
        {"label": "Shift", "fieldname": "shift", "fieldtype": "Data", "width": 70},
        {"label": "Location", "fieldname": "location", "fieldtype": "Link", "options": "Location", "width": 110},
        {"label": "Actual Hours", "fieldname": "actual_hours", "fieldtype": "Float", "width": 105, "precision": 1},
        {"label": "Planned Downtime", "fieldname": "planned_downtime", "fieldtype": "Float", "width": 130, "precision": 1},
        {"label": "Req Hrs", "fieldname": "shift_required_hours", "fieldtype": "Float", "width": 80, "precision": 1},
        {"label": "Work Hrs", "fieldname": "shift_working_hours", "fieldtype": "Float", "width": 85, "precision": 1},
        {"label": "Avail Hrs", "fieldname": "shift_available_hours", "fieldtype": "Float", "width": 85, "precision": 1},
        {"label": "Mechanical Downtime", "fieldname": "shift_breakdown_hours", "fieldtype": "Float", "width": 155, "precision": 1},
        {"label": "Actual Breakdown Time", "fieldname": "actual_breakdown_time", "fieldtype": "Float", "width": 165, "precision": 1},
        {"label": "Actual Planned Maintenance Time", "fieldname": "actual_planned_maintenance_time", "fieldtype": "Float", "width": 210, "precision": 1},
        {"label": "Actual Inspection Time", "fieldname": "actual_inspection_time", "fieldtype": "Float", "width": 160, "precision": 1},
        {"label": "Actual Service Time", "fieldname": "actual_service_time", "fieldtype": "Float", "width": 150, "precision": 1},
        {"label": "Actual Unplanned Maintenance Time", "fieldname": "actual_unplanned_maintenance_time", "fieldtype": "Float", "width": 220, "precision": 1},
        {"label": "Mechanical Outsourced Work", "fieldname": "mechanical_outsourced_work", "fieldtype": "Float", "width": 200, "precision": 1},
        {"label": "Other Lost Hrs", "fieldname": "shift_other_lost_hours", "fieldtype": "Float", "width": 110, "precision": 1},        
        {"label": "General & Specific Other Lost Hours", "fieldname": "captured_other_lost_hours", "fieldtype": "Float", "width": 235, "precision": 1},
        {"label": "Other Lost Hours Variance", "fieldname": "other_lost_hours_variance", "fieldtype": "Float", "width": 190, "precision": 1},
        {"label": "Avail (%)", "fieldname": "plant_shift_availability", "fieldtype": "Percent", "width": 85, "precision": 1},
        {"label": "Avail Target %", "fieldname": "avail_target_percent", "fieldtype": "Percent", "width": 115, "precision": 1},
        {"label": "Util (%)", "fieldname": "plant_shift_utilisation", "fieldtype": "Percent", "width": 85, "precision": 1},
        {"label": "Util Target %", "fieldname": "util_target_percent", "fieldtype": "Percent", "width": 110, "precision": 1},
        {"label": "Emp Avail (%)", "fieldname": "employee_availability", "fieldtype": "Percent", "width": 100, "precision": 1},
        {"label": "Breakdown Reason", "fieldname": "breakdown_reason", "fieldtype": "Data", "width": 170},
        {"label": "Other Delay Reason", "fieldname": "other_delay_reason", "fieldtype": "Data", "width": 170},
    ]


MSR_TIME_FIELDS = [
    "actual_service_time",
    "actual_breakdown_time",
    "actual_planned_maintenance_time",
    "actual_inspection_time",
    "actual_unplanned_maintenance_time",
    "mechanical_outsourced_work",
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
    "actual_unplanned_maintenance_time",
    "mechanical_outsourced_work",
    "shift_available_hours",
    "shift_other_lost_hours",
    "captured_other_lost_hours",
    "other_lost_hours_variance",
]


def r1(v):
    return round(v or 0, 1)


def clamp_percentage(value):
    value = float(value or 0)
    return max(0.0, min(100.0, value))


def calc_availability(req_hrs, avail_hrs):
    req_hrs = float(req_hrs or 0)
    avail_hrs = float(avail_hrs or 0)
    if req_hrs <= 0:
        return 0.0
    return r1(clamp_percentage((avail_hrs / req_hrs) * 100))


def calc_utilisation(work_hrs, avail_hrs):
    work_hrs = float(work_hrs or 0)
    avail_hrs = float(avail_hrs or 0)
    if avail_hrs <= 0:
        return 0.0
    return r1(clamp_percentage((work_hrs / avail_hrs) * 100))


def calc_employee_availability(req_hrs, other_lost_hrs):
    req_hrs = float(req_hrs or 0)
    other_lost_hrs = float(other_lost_hrs or 0)
    if req_hrs <= 0:
        return 0.0
    return r1(clamp_percentage(((req_hrs - other_lost_hrs) / req_hrs) * 100))


def apply_formula_fields(row):
    row["plant_shift_availability"] = calc_availability(
        row.get("shift_required_hours"),
        row.get("shift_available_hours"),
    )
    row["plant_shift_utilisation"] = calc_utilisation(
        row.get("shift_working_hours"),
        row.get("shift_available_hours"),
    )
    row["employee_availability"] = calc_employee_availability(
        row.get("shift_required_hours"),
        row.get("shift_other_lost_hours"),
    )

    row["avail_target_percent"] = r1((row.get("plant_shift_availability") or 0) * 0.85)
    row["util_target_percent"] = r1((row.get("plant_shift_utilisation") or 0) * 0.85)

    return row


def get_shift_window(shift, shift_date):
    shift_date = str(shift_date)

    if shift == "Day":
        return (
            frappe.utils.get_datetime(f"{shift_date} 06:00:00"),
            frappe.utils.get_datetime(f"{shift_date} 18:00:00"),
        )

    if shift == "Night":
        start = frappe.utils.get_datetime(f"{shift_date} 18:00:00")
        end = frappe.utils.add_to_date(start, hours=12, as_datetime=True)
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
    if not location or not shift_date:
        return 0

    if not location or not shift_date:
        return 0

    site = (location or "").strip().lower()
    day_of_week = frappe.utils.getdate(shift_date).weekday()
    saturday_special_sites = {"koppie", "uitgevallen", "bankfontein", "kriel"}

    if day_of_week == 6:
        return 0.0

    if day_of_week == 5:
        if site in saturday_special_sites:
            return 4.0 if indent in (0, 1, 2) else 2.0
        return 6.0 if indent in (0, 1, 2) else 3.0

    return 6.0 if indent in (0, 1, 2) else 3.0


def get_actual_hours_value(location, shift_date, indent):
    if not location or not shift_date:
        return 0

    site = (location or "").strip().lower()
    day_of_week = frappe.utils.getdate(shift_date).weekday()
    saturday_special_sites = {"koppie", "uitgevallen", "bankfontein", "kriel"}

    if day_of_week == 6:
        return 0.0

    if day_of_week == 5:
        if site in saturday_special_sites:
            return 18.0 if indent in (0, 1, 2) else 9.0
        return 24.0 if indent in (0, 1, 2) else 12.0

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


def safe_msr_datetime(value, service_date=None):
    if value in (None, ""):
        return None

    value_text = str(value).strip()
    if not value_text:
        return None

    service_date_text = str(service_date).strip() if service_date else None

    if "0000-00-00" in value_text or "-00-" in value_text:
        if service_date_text and " " in value_text:
            time_text = value_text.split()[-1].split(".")[0]
            try:
                return frappe.utils.get_datetime(f"{service_date_text} {time_text}")
            except Exception:
                return None
        return None

    try:
        return frappe.utils.get_datetime(value)
    except Exception:
        if service_date_text and ":" in value_text:
            time_text = value_text.split()[-1].split(".")[0]
            try:
                return frappe.utils.get_datetime(f"{service_date_text} {time_text}")
            except Exception:
                return None
        return None


def get_msr_time_map(filters):
    report_start = frappe.utils.get_datetime(f"{filters.get('start_date')} 00:00:00")
    report_end = frappe.utils.get_datetime(f"{filters.get('end_date')} 23:59:59")

    conditions = [
        "msr.start_time <= %(report_end)s",
        "(msr.end_time >= %(report_start)s OR IFNULL(msr.end_time, '') = '')",
    ]

    args = {
        "report_start": report_start,
        "report_end": report_end,
    }

    if filters.get("location"):
        conditions.append("msr.site = %(location)s")
        args["location"] = filters.get("location")

    msr_rows = frappe.db.sql(f"""
        SELECT
            msr.site AS location,
            msr.service_date,
            asset.asset_name AS asset_name,
            CAST(msr.start_time AS CHAR) AS start_time,
            CAST(msr.end_time AS CHAR) AS end_time,
            msr.total_time,
            msr.total_time AS total_time_unavailable,
            msr.service_breakdown,
            msr.outsourced
        FROM `tabMechanical Service Report` msr
        LEFT JOIN `tabAsset` asset
            ON asset.name = msr.asset
        WHERE {' AND '.join(conditions)}
    """, args, as_dict=True)

    time_map = {}

    for row in msr_rows:
        if not row.get("location") or not row.get("service_date") or not row.get("asset_name"):
            continue

        if not row.get("start_time"):
            continue

        start_dt = safe_msr_datetime(row.start_time, row.service_date)
        end_dt = safe_msr_datetime(row.end_time, row.service_date) if row.get("end_time") else now_datetime()

        if not start_dt or not end_dt:
            continue

        if end_dt <= start_dt:
            end_dt = frappe.utils.add_to_date(end_dt, days=1, as_datetime=True)

        effective_start = max(start_dt, report_start)
        effective_end = min(end_dt, report_end)

        if effective_end <= effective_start:
            continue

        loop_date = frappe.utils.getdate(effective_start)

        while loop_date <= frappe.utils.getdate(effective_end):
            for shift in ("Day", "Night", "Morning", "Afternoon"):
                shift_start, shift_end = get_shift_window(shift, loop_date)
                overlap_hours = get_overlap_hours(effective_start, effective_end, shift_start, shift_end)

                if overlap_hours <= 0:
                    continue

                key = (row.location, str(loop_date), row.asset_name, shift)
                bucket = time_map.setdefault(key, {field: 0.0 for field in MSR_TIME_FIELDS})

                if row.outsourced == "Yes":
                    bucket["mechanical_outsourced_work"] += overlap_hours
                elif row.service_breakdown == "Service":
                    bucket["actual_service_time"] += overlap_hours
                elif row.service_breakdown == "Breakdown":
                    bucket["actual_breakdown_time"] += overlap_hours
                elif row.service_breakdown == "Planned Maintenance":
                    bucket["actual_planned_maintenance_time"] += overlap_hours
                elif row.service_breakdown == "Inspection":
                    bucket["actual_inspection_time"] += overlap_hours
                elif row.service_breakdown == "Unplanned Maintenance":
                    bucket["actual_unplanned_maintenance_time"] += overlap_hours

            loop_date = frappe.utils.add_days(loop_date, 1)

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

            apply_formula_fields(row)

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

            apply_formula_fields(row)

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

            apply_formula_fields(row)


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

    records = [
        record for record in records
        if (record.get("asset_category") or "") not in EXCLUDED_ASSET_CATEGORIES
    ]

    spare_swing_asset_map = get_spare_swing_asset_map(filters)
    records = apply_machine_scope_filter(records, filters, spare_swing_asset_map)

    if not records:
        frappe.msgprint("No records found for the selected filters.")
        return []

    grouped = {}
    for record in records:
        cat = record["asset_category"] or "Uncategorised"
        date = str(record["shift_date"])
        asset = record["asset_name"]

        record["plant_shift_availability"] = r1(record.get("plant_shift_availability"))
        record["plant_shift_utilisation"] = r1(record.get("plant_shift_utilisation"))
        record["employee_availability"] = calc_employee_availability(
            record.get("shift_required_hours"),
            record.get("shift_other_lost_hours"),
        )

        grouped.setdefault(cat, {}).setdefault(date, {}).setdefault(asset, []).append(record)

    data = []

    for cat, date_groups in grouped.items():
        cat_rows = [r for d in date_groups.values() for a in d.values() for r in a]
        data.append(summary_row(
            cat_rows,
            indent=0,
            asset_category=cat,
            location=(filters.get("location") or None),
        ))

        for date, assets in date_groups.items():
            date_rows = [r for a in assets.values() for r in a]
            data.append(summary_row(
                date_rows,
                indent=1,
                asset_category=cat,
                shift_date=date,
                location=(filters.get("location") or None),
            ))

            for asset, rows in assets.items():
                data.append(summary_row(
                    rows,
                    indent=2,
                    asset_category=cat,
                    asset_name=asset,
                    shift_date=date,
                    location=(rows[0].get("location") if rows else None),
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
                        "actual_unplanned_maintenance_time",
                        "mechanical_outsourced_work",
                        "shift_available_hours",
                        "shift_other_lost_hours",
                        "captured_other_lost_hours",
                        "other_lost_hours_variance",
                    ]:
                        row[field] = r1(row.get(field))

                    row["plant_shift_availability"] = r1(row.get("plant_shift_availability"))
                    row["plant_shift_utilisation"] = r1(row.get("plant_shift_utilisation"))
                    row["employee_availability"] = calc_employee_availability(
                        row.get("shift_required_hours"),
                        row.get("shift_other_lost_hours"),
                    )

                    data.append(row)

    attach_reasons(data, filters)
    attach_msr_actuals(data, filters)
    attach_planned_and_actual_hours(data)
    recalculate_summary_rows(data)
    apply_spare_swing_flags(data, spare_swing_asset_map)

    return data


def combine_shifts(rows):
    total = {}

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
        "actual_unplanned_maintenance_time",
        "mechanical_outsourced_work",
        "shift_available_hours",
        "shift_other_lost_hours",
    ]:
        total[key] = sum((r.get(key) or 0) for r in rows)

    count = len(rows)
    total["captured_other_lost_hours"] = (
        sum((r.get("captured_other_lost_hours") or 0) for r in rows) / count if count else 0
    )
    total["other_lost_hours_variance"] = (
        (total.get("shift_other_lost_hours") or 0) - (total.get("captured_other_lost_hours") or 0)
    )

    apply_formula_fields(total)
    return total


def summary_row(rows, indent, **extra_fields):
    if not rows:
        return {**extra_fields, "indent": indent}

    combined = combine_shifts(rows)

    return {
        **extra_fields,
        "shift_required_hours": r1(combined.get("shift_required_hours")),
        "shift_working_hours": r1(combined.get("shift_working_hours")),
        "shift_breakdown_hours": r1(combined.get("shift_breakdown_hours")),
        "planned_downtime": r1(combined.get("planned_downtime")),
        "actual_hours": r1(combined.get("actual_hours")),
        "actual_service_time": r1(combined.get("actual_service_time")),
        "actual_breakdown_time": r1(combined.get("actual_breakdown_time")),
        "actual_planned_maintenance_time": r1(combined.get("actual_planned_maintenance_time")),
        "actual_inspection_time": r1(combined.get("actual_inspection_time")),
        "actual_unplanned_maintenance_time": r1(combined.get("actual_unplanned_maintenance_time")),
        "mechanical_outsourced_work": r1(combined.get("mechanical_outsourced_work")),
        "shift_available_hours": r1(combined.get("shift_available_hours")),
        "shift_other_lost_hours": r1(combined.get("shift_other_lost_hours")),
        "captured_other_lost_hours": r1(combined.get("captured_other_lost_hours")),
        "other_lost_hours_variance": r1(combined.get("other_lost_hours_variance")),
        "plant_shift_availability": r1(combined.get("plant_shift_availability")),
        "avail_target_percent": r1((combined.get("plant_shift_availability") or 0) * 0.85),
        "plant_shift_utilisation": r1(combined.get("plant_shift_utilisation")),
        "util_target_percent": r1((combined.get("plant_shift_utilisation") or 0) * 0.85),
        "employee_availability": r1(combined.get("employee_availability")),
        "indent": indent,
    }


def attach_reasons(data, filters):
    key_map = {(d.get("asset_name"), str(d.get("shift_date")), d.get("location"))
               for d in data if d.get("asset_name") and d.get("shift_date")}
    if not key_map:
        return

    asset_names = list({a for a, _, _ in key_map})
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    location = filters.get("location")

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

    delay_map = {(r.location, str(r.shift_date)): (r.gen_lost_hours_comments or "") for r in delay_rows}

    captured_general_map = {
        (r.location, str(r.shift_date), (r.shift or "")): (r.total_general_lost_hours or 0)
        for r in delay_rows
    }

    captured_plant_map = {}
    for r in plant_rows:
        k = (r.location, str(r.shift_date), (r.shift or ""), r.asset_name)
        captured_plant_map[k] = (captured_plant_map.get(k, 0) + (r.total_plant_specific_lost_hours or 0))

    for row in data:
        if not row.get("shift_date"):
            continue

        if row.get("indent") == 1:
            continue

        k2 = (row.get("location"), str(row["shift_date"]))
        shift = (row.get("shift") or "")
        asset = row.get("asset_name")

        def captured_for(s):
            general = captured_general_map.get((k2[0], k2[1], s), 0)
            plant = captured_plant_map.get((k2[0], k2[1], s, asset), 0) if asset else 0
            return general + plant

        if shift in ("Day", "Night"):
            captured = captured_for(shift)
        else:
            captured = captured_for("Day") + captured_for("Night")

        row["captured_other_lost_hours"] = round(captured or 0, 1)
        row["other_lost_hours_variance"] = round(
            (row.get("shift_other_lost_hours") or 0) - (row.get("captured_other_lost_hours") or 0),
            1
        )

        if row.get("asset_name"):
            k1 = (row["asset_name"], str(row["shift_date"]), row.get("location"))
            row["breakdown_reason"] = "; ".join(breakdown_map.get(k1, [])) if k1 in breakdown_map else ""

        row["other_delay_reason"] = delay_map.get(k2, "")

        apply_formula_fields(row)

    frappe.log_error(
        f"Avail & Util Detailed fetched {len(breakdown_rows)} breakdowns and {len(delay_rows)} daily comments",
        "Avail Util Debug"
    )