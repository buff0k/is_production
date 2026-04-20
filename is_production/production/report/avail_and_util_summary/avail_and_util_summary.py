import frappe
from frappe.utils import flt


def execute(filters=None):
    """
    Generate the Availability and Utilisation summary report,
    grouped by Asset Category and Site, with per-category bar charts.
    """
    columns = get_columns()
    data = get_collapsed_summary(filters or {})

    if not data:
        frappe.msgprint("⚠️ No records found for the selected filters or date range.")
        return columns, []

    charts = build_charts(data, filters or {})

    message_html = ""
    for ch in charts:
        message_html += f"""
        <div style='margin-bottom:40px'>
            <h4 style='margin-bottom:10px'>{ch['title']}</h4>
            <div class='frappe-chart' data-chart='{frappe.as_json(ch)}'></div>
        </div>
        """

    return columns, data, message_html, charts[0] if charts else None


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
        {"label": "Util %", "fieldname": "plant_shift_utilisation", "fieldtype": "Percent", "width": 65, "precision": 1}
    ]


def r1(v):
    return round(flt(v), 1)


def calc_availability(req_hrs, avail_hrs):
    req_hrs = flt(req_hrs)
    avail_hrs = flt(avail_hrs)

    if req_hrs <= 0:
        return 0.0

    return r1((avail_hrs / req_hrs) * 100)


def calc_utilisation(work_hrs, avail_hrs):
    work_hrs = flt(work_hrs)
    avail_hrs = flt(avail_hrs)

    if avail_hrs <= 0:
        return 0.0

    return r1((work_hrs / avail_hrs) * 100)


def apply_formula_fields(row):
    row["plant_shift_availability"] = calc_availability(
        row.get("shift_required_hours"),
        row.get("shift_available_hours"),
    )
    row["plant_shift_utilisation"] = calc_utilisation(
        row.get("shift_working_hours"),
        row.get("shift_available_hours"),
    )
    return row


def round_row(row):
    for f in [
        "shift_required_hours",
        "shift_working_hours",
        "shift_breakdown_hours",
        "shift_available_hours",
        "shift_other_lost_hours",
        "plant_shift_availability",
        "plant_shift_utilisation",
    ]:
        row[f] = r1(row.get(f))


def build_conditions(filters):
    conditions = []

    if filters.get("start_date") and filters.get("end_date"):
        conditions.append(f"shift_date BETWEEN {frappe.db.escape(filters.get('start_date'))} AND {frappe.db.escape(filters.get('end_date'))}")
    elif filters.get("start_date"):
        conditions.append(f"shift_date >= {frappe.db.escape(filters.get('start_date'))}")
    elif filters.get("end_date"):
        conditions.append(f"shift_date <= {frappe.db.escape(filters.get('end_date'))}")

    if filters.get("location") or filters.get("site"):
        loc = filters.get("location") or filters.get("site")
        conditions.append(f"location = {frappe.db.escape(loc)}")

    if filters.get("asset"):
        conditions.append(f"asset_name = {frappe.db.escape(filters.get('asset'))}")

    if filters.get("asset_category") and filters.get("asset_category") != "All":
        cat = filters.get("asset_category")
        if cat == "Uncategorised":
            conditions.append("(asset_category IS NULL OR asset_category = '' OR asset_category = 'Uncategorised')")
        else:
            conditions.append(f"asset_category = {frappe.db.escape(cat)}")

    return "WHERE " + " AND ".join(conditions) if conditions else ""


def summary_row(rows, **extra_fields):
    if not rows:
        return {**extra_fields}

    req = sum(flt(r.get("shift_required_hours")) for r in rows)
    work = sum(flt(r.get("shift_working_hours")) for r in rows)
    brkdwn = sum(flt(r.get("shift_breakdown_hours")) for r in rows)
    avail = sum(flt(r.get("shift_available_hours")) for r in rows)
    lost = sum(flt(r.get("shift_other_lost_hours")) for r in rows)

    out = {
        **extra_fields,
        "shift_required_hours": r1(req),
        "shift_working_hours": r1(work),
        "shift_breakdown_hours": r1(brkdwn),
        "shift_available_hours": r1(avail),
        "shift_other_lost_hours": r1(lost),
        "plant_shift_availability": calc_availability(req, avail),
        "plant_shift_utilisation": calc_utilisation(work, avail),
    }
    return out


def get_collapsed_summary(filters):
    conditions = build_conditions(filters)

    records = frappe.db.sql(f"""
        SELECT
            COALESCE(asset_category, 'Uncategorised') AS asset_category,
            asset_name,
            location,
            SUM(shift_required_hours) AS shift_required_hours,
            SUM(shift_working_hours) AS shift_working_hours,
            SUM(shift_breakdown_hours) AS shift_breakdown_hours,
            SUM(shift_available_hours) AS shift_available_hours,
            SUM(shift_other_lost_hours) AS shift_other_lost_hours
        FROM `tabAvailability and Utilisation`
        {conditions}
        GROUP BY COALESCE(asset_category, 'Uncategorised'), asset_name, location
        ORDER BY asset_category, asset_name
    """, as_dict=True)

    if not records:
        return []

    for row in records:
        apply_formula_fields(row)
        round_row(row)

    grouped = {}
    for row in records:
        category = row["asset_category"]
        grouped.setdefault(category, []).append(row)

    data = []

    for category, rows in grouped.items():
        cat_row = summary_row(rows, asset_category=category)
        cat_row.update({"asset_name": "", "location": "", "indent": 0})
        data.append(cat_row)

        for r in rows:
            child = dict(r)
            child["asset_category"] = ""
            child["indent"] = 1
            data.append(child)

    total_row = summary_row(records, asset_category="GRAND TOTAL")
    total_row.update({"asset_name": "", "location": "", "indent": 0})
    data.append(total_row)

    return data


def build_charts(data, filters):
    filters = filters or {}

    metric = filters.get("metric") or "All"
    chart_type = (filters.get("chart_type") or "Bar").lower()
    time_column = filters.get("time_column") or "Month Only"

    if time_column != "Month Only":
        return [build_time_chart(filters, metric, chart_type, time_column)]

    cat_map = {}
    for row in data:
        cat = row.get("asset_category") or "Uncategorised"
        if not row.get("asset_name"):
            continue

        cat_map.setdefault(cat, {"avail": [], "util": [], "assets": []})
        cat_map[cat]["assets"].append(row["asset_name"])
        cat_map[cat]["avail"].append(flt(row.get("plant_shift_availability") or 0))
        cat_map[cat]["util"].append(flt(row.get("plant_shift_utilisation") or 0))

    charts = []
    for cat, vals in cat_map.items():
        datasets = []
        if metric in ("All", "Availability %"):
            datasets.append({"name": "Availability %", "values": vals["avail"]})
        if metric in ("All", "Utilisation %"):
            datasets.append({"name": "Utilisation %", "values": vals["util"]})

        chart = {
            "title": f"{cat} — Availability vs Utilisation",
            "data": {"labels": vals["assets"], "datasets": datasets},
            "type": chart_type,
            "height": 250,
            "barOptions": {"spaceRatio": 0.6},
            "colors": ["#FFC39B", "#7A7A7A"]
        }
        charts.append(chart)

    return charts


def build_time_chart(filters, metric, chart_type, time_column):
    conditions = build_conditions(filters)
    bucket_expr, bucket_label = get_time_bucket_expr(time_column)

    rows = frappe.db.sql(f"""
        SELECT
            {bucket_expr} AS bucket,
            SUM(shift_required_hours) AS req,
            SUM(shift_working_hours) AS work,
            SUM(shift_available_hours) AS avail
        FROM `tabAvailability and Utilisation`
        {conditions}
        GROUP BY {bucket_expr}
        ORDER BY MIN(shift_date) ASC
    """, as_dict=True)

    labels = [r.get("bucket") for r in rows]
    avail_vals = [calc_availability(r.get("req"), r.get("avail")) for r in rows]
    util_vals = [calc_utilisation(r.get("work"), r.get("avail")) for r in rows]

    datasets = []
    if metric in ("All", "Availability %"):
        datasets.append({"name": "Availability %", "values": avail_vals})
    if metric in ("All", "Utilisation %"):
        datasets.append({"name": "Utilisation %", "values": util_vals})

    return {
        "title": f"Availability / Utilisation over Time ({bucket_label})",
        "data": {"labels": labels, "datasets": datasets},
        "type": chart_type,
        "height": 280,
        "colors": ["#FFC39B", "#7A7A7A"]
    }


def get_time_bucket_expr(time_column):
    if time_column == "Days Only":
        return ("DATE_FORMAT(shift_date, '%Y-%m-%d')", "Day")
    if time_column == "Days and Month":
        return ("DATE_FORMAT(shift_date, '%d %b')", "Day+Month")
    if time_column == "Weeks Only":
        return ("DATE_FORMAT(shift_date, '%x-W%v')", "Week")
    if time_column == "Week and Month":
        return ("CONCAT(DATE_FORMAT(shift_date, '%b'), ' ', DATE_FORMAT(shift_date, '%x-W%v'))", "Week+Month")

    return ("DATE_FORMAT(shift_date, '%Y-%m')", "Month")