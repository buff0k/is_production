# Copyright (c) 2025, Isambane Mining (Pty) Ltd
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate
from datetime import datetime


# -------------------------------------------------------------
# Main Execute Function
# -------------------------------------------------------------
def execute(filters=None):
    if not filters.get("start_date") or not filters.get("end_date") or not filters.get("site"):
        frappe.throw(_("Filters (Start Date, End Date, Site) are required"))

    columns = get_columns()
    data, grand_total_bcm, grand_total_tons = get_data(filters)

    # ✅ MTD Actual BCM from Survey + Hourly Production logic
    mtd_actual_bcms = get_mtd_actual_bcms(filters.site, filters.end_date)

    # ✅ MTD Tallies BCM = same as grand_total_bcm
    mtd_tallies_bcm = grand_total_bcm

    # ---------------------------------------------------------
    # Append MTD rows at the bottom
    # ---------------------------------------------------------
    data.append({
        "mat_type": "MTD Actual BCM",
        "geo_ref_description": None,
        "total_bcm": mtd_actual_bcms,
        "coal_tons": None,
        "indent": 0
    })
    data.append({
        "mat_type": "MTD Tallies BCM",
        "geo_ref_description": None,
        "total_bcm": mtd_tallies_bcm,
        "coal_tons": None,
        "indent": 0
    })

    return columns, data, None, None, get_report_summary(grand_total_bcm, grand_total_tons, mtd_actual_bcms, mtd_tallies_bcm)


# -------------------------------------------------------------
# Columns
# -------------------------------------------------------------
def get_columns():
    return [
        {"label": _("Material Category"), "fieldname": "mat_type", "fieldtype": "Data", "width": 180, "group": 1},
        {"label": _("Geo / Material Layer"), "fieldname": "geo_ref_description", "fieldtype": "Data", "width": 250},
        {"label": _("Total BCMs"), "fieldname": "total_bcm", "fieldtype": "Float", "width": 120},
        {"label": _("Coal Tons"), "fieldname": "coal_tons", "fieldtype": "Float", "width": 120},
    ]


# -------------------------------------------------------------
# Helper: Detect Shift Column
# -------------------------------------------------------------
def get_shift_field(table_name: str):
    cols = frappe.db.get_table_columns(table_name)
    if "shift" in cols:
        return "shift"
    if "shift_type" in cols:
        return "shift_type"
    return None


# -------------------------------------------------------------
# ✅ Monthly Plan Lookup
# -------------------------------------------------------------
def get_monthly_plan(site, date):
    """Fetch the active Monthly Production Planning doc for this site/date."""
    if not site or not date:
        return None
    plan_name = frappe.db.get_value(
        "Monthly Production Planning",
        {"location": site, "prod_month_start_date": ["<=", date], "prod_month_end_date": [">=", date]},
        "name",
    )
    return frappe.get_doc("Monthly Production Planning", plan_name) if plan_name else None


# -------------------------------------------------------------
# ✅ MTD Actual BCM Calculation (same as Production Shift Teams)
# -------------------------------------------------------------
def get_mtd_actual_bcms(site, end_date):
    """
    Calculate MTD Actual BCM exactly like Weekly Report's 'MTD Prog Actual BCMs'.
    Uses Survey cumulative totals + Hourly Production after survey.
    Falls back to Hourly Production full range if no survey exists.
    """
    if not site or not end_date:
        return 0

    # --- Get current month start from MPP ---
    mpp = get_monthly_plan(site, end_date)
    if not mpp:
        return 0

    month_start = getdate(mpp.prod_month_start_date)
    end_date = getdate(end_date)

    # --- Get latest Survey record for site up to end_date ---
    survey_doc = frappe.get_all(
        "Survey",
        filters={
            "location": site,
            "last_production_shift_start_date": ["<=", f"{end_date} 23:59:59"],
        },
        fields=["last_production_shift_start_date", "total_ts_bcm", "total_dozing_bcm"],
        order_by="last_production_shift_start_date desc",
        limit_page_length=1
    )

    ts_actual_bcm = 0
    dozing_actual_bcm = 0

    if survey_doc:
        survey = survey_doc[0]
        survey_date = survey.get("last_production_shift_start_date")
        if isinstance(survey_date, datetime):
            survey_date = survey_date.date()

        # ✅ Survey inside current month window
        if survey_date and month_start <= survey_date <= end_date:
            ts_actual_bcm = survey.get("total_ts_bcm") or 0
            dozing_actual_bcm = survey.get("total_dozing_bcm") or 0

            # Add Truck Loads BCMs after survey
            ts_after = frappe.db.sql("""
                SELECT COALESCE(SUM(tl.bcms), 0)
                FROM `tabHourly Production` hp
                JOIN `tabTruck Loads` tl ON tl.parent = hp.name
                WHERE hp.prod_date > %s AND hp.prod_date <= %s
                  AND hp.location = %s
            """, (survey_date, end_date, site))[0][0]

            # Add Dozer Production BCMs after survey
            dozing_after = frappe.db.sql("""
                SELECT COALESCE(SUM(dp.bcm_hour), 0)
                FROM `tabHourly Production` hp
                JOIN `tabDozer Production` dp ON dp.parent = hp.name
                WHERE hp.prod_date > %s AND hp.prod_date <= %s
                  AND hp.location = %s
            """, (survey_date, end_date, site))[0][0]

            ts_actual_bcm += ts_after or 0
            dozing_actual_bcm += dozing_after or 0

        else:
            # ✅ Survey exists but outside current month → fallback
            ts_actual_bcm, dozing_actual_bcm = get_hourly_bcms(month_start, end_date, site)

    else:
        # ✅ No Survey found → fallback
        ts_actual_bcm, dozing_actual_bcm = get_hourly_bcms(month_start, end_date, site)

    return (ts_actual_bcm or 0) + (dozing_actual_bcm or 0)


def get_hourly_bcms(start_date, end_date, site):
    """Fallback calculation: directly sum truck + dozer BCMs from Hourly Production."""
    ts = frappe.db.sql("""
        SELECT COALESCE(SUM(tl.bcms), 0)
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
    """, (start_date, end_date, site))[0][0]

    dozing = frappe.db.sql("""
        SELECT COALESCE(SUM(dp.bcm_hour), 0)
        FROM `tabHourly Production` hp
        JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.prod_date BETWEEN %s AND %s
          AND hp.location = %s
    """, (start_date, end_date, site))[0][0]

    return ts or 0, dozing or 0


# -------------------------------------------------------------
# Main Data Query
# -------------------------------------------------------------
def get_data(filters):
    hp_shift_col = get_shift_field("Hourly Production")
    shift_condition = f" AND hp.{hp_shift_col} = %(shift)s" if filters.get("shift") and hp_shift_col else ""

    truck_totals = frappe.db.sql(f"""
        SELECT
            tl.mat_type,
            tl.geo_mat_layer_truck AS geo_ref_description,
            SUM(tl.bcms) AS total_bcm
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.location = %(site)s
          {shift_condition}
        GROUP BY tl.mat_type, tl.geo_mat_layer_truck
    """, filters, as_dict=True)

    dozer_totals = frappe.db.sql(f"""
        SELECT
            dp.dozer_geo_mat_layer AS geo_ref_description,
            dp.dozer_geo_mat_layer AS mat_type,
            SUM(dp.bcm_hour) AS total_bcm
        FROM `tabHourly Production` hp
        JOIN `tabDozer Production` dp ON dp.parent = hp.name
        WHERE hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.location = %(site)s
          {shift_condition}
        GROUP BY dp.dozer_geo_mat_layer
    """, filters, as_dict=True)

    combined = truck_totals + dozer_totals

    def classify(mat_type):
        if not mat_type:
            return "Unassigned"
        mt = mat_type.lower()
        if "coal" in mt:
            return "Coal"
        elif "hard" in mt:
            return "Hards"
        elif "soft" in mt:
            return "Softs"
        return "Other"

    grouped_results = {}
    grand_total_bcm = 0
    grand_total_tons = 0

    for r in combined:
        category = classify(r["mat_type"])
        bcm_val = r["total_bcm"] or 0
        geo_desc = r["geo_ref_description"] or "Unassigned"
        coal_tons = bcm_val * 1.5 if category == "Coal" else None

        if category not in grouped_results:
            grouped_results[category] = {"total": 0, "total_tons": 0, "children": []}

        grouped_results[category]["total"] += bcm_val
        grouped_results[category]["total_tons"] += coal_tons or 0
        grouped_results[category]["children"].append({
            "mat_type": None,
            "geo_ref_description": geo_desc,
            "total_bcm": bcm_val,
            "coal_tons": coal_tons,
            "indent": 1
        })

        grand_total_bcm += bcm_val
        grand_total_tons += coal_tons or 0

    results = []
    for category in ["Coal", "Hards", "Softs", "Other", "Unassigned"]:
        if category in grouped_results:
            results.append({
                "mat_type": category,
                "geo_ref_description": None,
                "total_bcm": grouped_results[category]["total"],
                "coal_tons": grouped_results[category]["total_tons"] if category == "Coal" else None,
                "indent": 0
            })
            results.extend(sorted(
                grouped_results[category]["children"],
                key=lambda x: str(x.get("geo_ref_description") or "")
            ))

    return results, grand_total_bcm, grand_total_tons


# -------------------------------------------------------------
# Report Summary
# -------------------------------------------------------------
def get_report_summary(grand_total_bcm, grand_total_tons, mtd_actual_bcms, mtd_tallies_bcm):
    summary = [
        {
            "label": _("Grand Total BCMs"),
            "value": f"{grand_total_bcm:,.0f}",
            "indicator": "Blue"
        },
        {
            "label": _("MTD Actual BCM"),
            "value": f"{mtd_actual_bcms:,.0f}",
            "indicator": "Orange"
        },
        {
            "label": _("MTD Tallies BCM"),
            "value": f"{mtd_tallies_bcm:,.0f}",
            "indicator": "Purple"
        },
    ]
    if grand_total_tons:
        summary.append({
            "label": _("Grand Total Coal Tons"),
            "value": f"{grand_total_tons:,.0f}",
            "indicator": "Green"
        })
    return summary
