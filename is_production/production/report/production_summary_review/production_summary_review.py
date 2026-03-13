import frappe
from frappe import _


REPORT_DOCTYPE = "Production Summary Entry"


def execute(filters=None):
    filters = filters or {}

    columns = get_columns()

    if not frappe.db.exists("DocType", REPORT_DOCTYPE):
        frappe.msgprint(
            _("DocType <b>{0}</b> does not exist yet. Please create it first or change REPORT_DOCTYPE in the report file.").format(REPORT_DOCTYPE),
            title=_("Missing DocType"),
            indicator="red"
        )
        return columns, []

    data = get_data(filters)
    summary = get_report_summary(data)

    return columns, data, None, None, summary


def get_columns():
    return [
        {"label": _("Site"), "fieldname": "site", "fieldtype": "Data", "width": 150},
        {"label": _("Report Date"), "fieldname": "report_date", "fieldtype": "Date", "width": 110},
        {"label": _("Monthly Target BCM"), "fieldname": "monthly_target_bcm", "fieldtype": "Float", "width": 140},
        {"label": _("Forecast BCM"), "fieldname": "forecast_bcm", "fieldtype": "Float", "width": 130},
        {"label": _("Forecast Variance BCM"), "fieldname": "forecast_variance_bcm", "fieldtype": "Float", "width": 150},
        {"label": _("Waste Variance BCM"), "fieldname": "waste_variance_bcm", "fieldtype": "Float", "width": 140},
        {"label": _("Coal Variance Tons"), "fieldname": "coal_variance_tons", "fieldtype": "Float", "width": 140},
        {"label": _("Daily Required BCM"), "fieldname": "daily_required_bcm", "fieldtype": "Float", "width": 140},
        {"label": _("Daily Achieved BCM"), "fieldname": "daily_achieved_bcm", "fieldtype": "Float", "width": 140},
        {"label": _("Days Worked"), "fieldname": "days_worked", "fieldtype": "Int", "width": 100},
        {"label": _("Days Left"), "fieldname": "days_left", "fieldtype": "Int", "width": 100},
        {"label": _("Strip Ratio"), "fieldname": "strip_ratio", "fieldtype": "Float", "width": 100},
        {"label": _("Actual BCM"), "fieldname": "actual_bcm", "fieldtype": "Float", "width": 120},
        {"label": _("Actual Coal Tons"), "fieldname": "actual_coal_tons", "fieldtype": "Float", "width": 130},
    ]


def get_data(filters):
    conditions = []
    values = {}

    if filters.get("report_date"):
        conditions.append("report_date = %(report_date)s")
        values["report_date"] = filters.get("report_date")

    if filters.get("site"):
        conditions.append("site = %(site)s")
        values["site"] = filters.get("site")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            site,
            report_date,
            monthly_target_bcm,
            forecast_bcm,
            (forecast_bcm - monthly_target_bcm) AS forecast_variance_bcm,
            waste_variance_bcm,
            coal_variance_tons,
            daily_required_bcm,
            daily_achieved_bcm,
            days_worked,
            days_left,
            strip_ratio,
            actual_bcm,
            actual_coal_tons
        FROM `tab{REPORT_DOCTYPE}`
        {where_clause}
        ORDER BY site ASC
    """

    return frappe.db.sql(query, values, as_dict=True)


def get_report_summary(data):
    total_target = sum((row.monthly_target_bcm or 0) for row in data)
    total_forecast = sum((row.forecast_bcm or 0) for row in data)
    total_forecast_variance = sum((row.forecast_variance_bcm or 0) for row in data)
    total_waste_variance = sum((row.waste_variance_bcm or 0) for row in data)
    total_coal_variance = sum((row.coal_variance_tons or 0) for row in data)

    return [
        {
            "label": "Total Monthly Target BCM",
            "value": total_target,
            "datatype": "Float"
        },
        {
            "label": "Total Forecast BCM",
            "value": total_forecast,
            "datatype": "Float"
        },
        {
            "label": "Total Forecast Variance BCM",
            "value": total_forecast_variance,
            "datatype": "Float",
            "indicator": "Green" if total_forecast_variance >= 0 else "Red"
        },
        {
            "label": "Total Waste Variance BCM",
            "value": total_waste_variance,
            "datatype": "Float",
            "indicator": "Green" if total_waste_variance >= 0 else "Red"
        },
        {
            "label": "Total Coal Variance Tons",
            "value": total_coal_variance,
            "datatype": "Float",
            "indicator": "Green" if total_coal_variance >= 0 else "Red"
        }
    ]