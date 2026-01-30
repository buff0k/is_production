import frappe
from frappe.utils import flt

def execute(filters=None):
    """
    Generate the Availability and Utilisation summary report,
    grouped by Asset Category and Site, with per-category bar charts.
    """
    columns = get_columns()
    data = get_collapsed_summary(filters)

    if not data:
        frappe.msgprint("⚠️ No records found for the selected filters or date range.")
        return columns, []

    charts = build_charts(data, filters)

    # HTML for multiple charts below the table
    message_html = ""
    for ch in charts:
        message_html += f"""
        <div style='margin-bottom:40px'>
            <h4 style='margin-bottom:10px'>{ch['title']}</h4>
            <div class='frappe-chart' data-chart='{frappe.as_json(ch)}'></div>
        </div>
        """

    # Return the first chart for top display, and embed the rest as HTML
    return columns, data, message_html, charts[0] if charts else None


# -------------------------------------------------------
# Columns
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
        {"label": "Util %", "fieldname": "plant_shift_utilisation", "fieldtype": "Percent", "width": 65, "precision": 1}
    ]


# -------------------------------------------------------
# Data Logic — grouped by Asset Category
# -------------------------------------------------------
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
        cat_row = summary_row(rows, asset_category=category)
        cat_row.update({"asset_name": "", "location": "", "indent": 0})
        data.append(cat_row)

        for r in rows:
            round_row(r)
            r["asset_category"] = ""
            r["indent"] = 1
            data.append(r)

    # Grand total
    total_row = summary_row(records, asset_category="GRAND TOTAL")
    total_row.update({"asset_name": "", "location": "", "indent": 0})
    data.append(total_row)

    return data


# -------------------------------------------------------
# Helpers
# -------------------------------------------------------
def summary_row(rows, **extra_fields):
    def r1(v): return round(v or 0, 1)
    count = len(rows)
    def avg(f): return sum((r.get(f) or 0) for r in rows) / count if count else 0
    def total(f): return sum((r.get(f) or 0) for r in rows)

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
    for f in [
        "shift_required_hours", "shift_working_hours", "shift_breakdown_hours",
        "shift_available_hours", "shift_other_lost_hours",
        "plant_shift_availability", "plant_shift_utilisation"
    ]:
        row[f] = round(row.get(f) or 0, 1)


def build_conditions(filters):
    conditions = []
    if filters.get("start_date") and filters.get("end_date"):
        conditions.append(f"shift_date BETWEEN '{filters.get('start_date')}' AND '{filters.get('end_date')}'")
    elif filters.get("start_date"):
        conditions.append(f"shift_date >= '{filters.get('start_date')}'")
    elif filters.get("end_date"):
        conditions.append(f"shift_date <= '{filters.get('end_date')}'")

    if filters.get("location") or filters.get("site"):
        loc = filters.get("location") or filters.get("site")
        conditions.append(f"location = {frappe.db.escape(loc)}")

    # NEW: Asset filter (filters against Availability and Utilisation.asset_name)
    if filters.get("asset"):
        conditions.append(f"asset_name = {frappe.db.escape(filters.get('asset'))}")

    # NEW: Asset Category filter (All shows everything)
    if filters.get("asset_category") and filters.get("asset_category") != "All":
        cat = filters.get("asset_category")
        if cat == "Uncategorised":
            conditions.append("(asset_category IS NULL OR asset_category = '' OR asset_category = 'Uncategorised')")
        else:
            conditions.append(f"asset_category = '{cat}'")



    return "WHERE " + " AND ".join(conditions) if conditions else ""


# -------------------------------------------------------
# Chart Builder — per category (asset view) OR time-bucket view
# -------------------------------------------------------
def build_charts(data, filters):
    filters = filters or {}

    metric = filters.get("metric") or "All"
    chart_type = (filters.get("chart_type") or "Bar").lower()   # "bar" or "line"
    time_column = filters.get("time_column") or "Month Only"

    # If user selects any "time" mode, switch charts to a time-bucket chart
    if time_column != "Month Only":
        return [build_time_chart(filters, metric, chart_type, time_column)]

    # Otherwise: keep the existing "per category, per asset" charts
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
            "colors": ["#FFC39B", "#7A7A7A"]  # Availability, Utilisation
        }
        charts.append(chart)

    return charts


def build_time_chart(filters, metric, chart_type, time_column):
    """
    Time-bucket chart across selected filters.
    Uses AVG(%) per bucket.
    """
    conditions = build_conditions(filters)
    bucket_expr, bucket_label = get_time_bucket_expr(time_column)

    rows = frappe.db.sql(f"""
        SELECT
            {bucket_expr} AS bucket,
            AVG(plant_shift_availability) AS avail,
            AVG(plant_shift_utilisation) AS util
        FROM `tabAvailability and Utilisation`
        {conditions}
        GROUP BY {bucket_expr}
        ORDER BY MIN(shift_date) ASC
    """, as_dict=True)

    labels = [r.get("bucket") for r in rows]
    avail_vals = [flt(r.get("avail") or 0) for r in rows]
    util_vals = [flt(r.get("util") or 0) for r in rows]

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
        "colors": ["#FFC39B", "#7A7A7A"]  # Availability, Utilisation
    }


def get_time_bucket_expr(time_column):
    """
    Returns (SQL expr, label) for MariaDB/MySQL.
    """
    # NOTE: tabAvailability and Utilisation.shift_date is assumed to be a DATE/DATETIME.
    if time_column == "Days Only":
        return ("DATE_FORMAT(shift_date, '%Y-%m-%d')", "Day")
    if time_column == "Days and Month":
        return ("DATE_FORMAT(shift_date, '%d %b')", "Day+Month")
    if time_column == "Weeks Only":
        return ("DATE_FORMAT(shift_date, '%x-W%v')", "Week")
    if time_column == "Week and Month":
        return ("CONCAT(DATE_FORMAT(shift_date, '%b'), ' ', DATE_FORMAT(shift_date, '%x-W%v'))", "Week+Month")

    # Month Only (default)
    return ("DATE_FORMAT(shift_date, '%Y-%m')", "Month")
