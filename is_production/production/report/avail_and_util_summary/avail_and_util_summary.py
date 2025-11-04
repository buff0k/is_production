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

    charts = build_charts(data)

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
        conditions.append(f"location = '{loc}'")

    return "WHERE " + " AND ".join(conditions) if conditions else ""


# -------------------------------------------------------
# Chart Builder — one chart per category
# -------------------------------------------------------
def build_charts(data):
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
        chart = {
            "title": f"{cat} — Availability vs Utilisation",
            "data": {
                "labels": vals["assets"],
                "datasets": [
                    {"name": "Availability %", "values": vals["avail"]},
                    {"name": "Utilisation %", "values": vals["util"]}
                ]
            },
            "type": "bar",
            "height": 250,
            "barOptions": {"spaceRatio": 0.6},
            "colors": ["#4CAF50", "#2196F3"]
        }
        charts.append(chart)
    return charts
