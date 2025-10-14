# Copyright (c) 2025, Isambane Mining (Pty) Ltd
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate
from datetime import datetime

def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns, data, grand_total = get_columns(), *get_data(filters)
    return columns, data, None, None, get_report_summary(grand_total)

# -------------------------------------------------------------
# Columns
# -------------------------------------------------------------
def get_columns():
    return [
        {"label": _("Excavator"), "fieldname": "excavator", "fieldtype": "Data", "width": 160, "group": 1},
        {"label": _("Truck"), "fieldname": "truck", "fieldtype": "Data", "width": 140, "group": 1},
        {"label": _("Mining Area"), "fieldname": "mining_area", "fieldtype": "Data", "width": 160},
        {"label": _("Material Type"), "fieldname": "mat_type", "fieldtype": "Data", "width": 140},
        {"label": _("BCMs"), "fieldname": "bcms", "fieldtype": "Float", "width": 100},
    ]

# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------
def get_shift_field(table_name: str):
    """Detect correct shift column name dynamically."""
    try:
        cols = frappe.db.get_table_columns(table_name)
    except Exception:
        return None
    if "shift" in cols:
        return "shift"
    if "shift_type" in cols:
        return "shift_type"
    return None


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
# ✅ MTD Actual BCMs (Weekly Report Logic)
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
    if not (filters.start_date and filters.end_date and filters.site):
        return [], 0

    hp_shift_col = get_shift_field("Hourly Production")
    shift_condition = f" AND hp.{hp_shift_col} = %(shift)s" if filters.get("shift") and hp_shift_col else ""

    values = {
        "start_date": filters["start_date"],
        "end_date": filters["end_date"],
        "site": filters["site"],
        "shift": filters.get("shift"),
    }

    # --- Truck Load detail data for hierarchy ---
    rows = frappe.db.sql(f"""
        SELECT
            tl.asset_name_shoval AS excavator,
            tl.asset_name_truck AS truck,
            tl.mining_areas_trucks AS mining_area,
            tl.mat_type AS mat_type,
            SUM(tl.bcms) AS bcms
        FROM `tabHourly Production` hp
        JOIN `tabTruck Loads` tl ON tl.parent = hp.name
        WHERE hp.prod_date BETWEEN %(start_date)s AND %(end_date)s
          AND hp.location = %(site)s
          {shift_condition}
        GROUP BY tl.asset_name_shoval, tl.asset_name_truck, tl.mining_areas_trucks, tl.mat_type
        ORDER BY tl.asset_name_shoval, tl.asset_name_truck
    """, values, as_dict=True)

    grouped, grand_total = {}, 0
    for r in rows:
        excavator = r["excavator"] or "Unassigned"
        truck = r["truck"] or "Unassigned"
        grouped.setdefault(excavator, {"total": 0, "children": {}})
        grouped[excavator]["total"] += r["bcms"] or 0
        grouped[excavator]["children"].setdefault(truck, {"total": 0, "details": []})
        grouped[excavator]["children"][truck]["total"] += r["bcms"] or 0
        grouped[excavator]["children"][truck]["details"].append(r)
        grand_total += r["bcms"] or 0

    results = []
    for excavator in sorted(grouped.keys()):
        results.append({
            "excavator": excavator,
            "truck": None,
            "mining_area": None,
            "mat_type": None,
            "bcms": grouped[excavator]["total"],
            "indent": 0
        })
        for truck in sorted(grouped[excavator]["children"].keys()):
            truck_info = grouped[excavator]["children"][truck]
            results.append({
                "excavator": None,
                "truck": truck,
                "mining_area": None,
                "mat_type": None,
                "bcms": truck_info["total"],
                "indent": 1
            })
            for d in truck_info["details"]:
                results.append({
                    "excavator": None,
                    "truck": None,
                    "mining_area": d["mining_area"],
                    "mat_type": d["mat_type"],
                    "bcms": d["bcms"],
                    "indent": 2
                })

    # -----------------------------------------------------
    # ✅ Add MTD Actual BCM row using Weekly Report logic
    # -----------------------------------------------------
    mtd_actual_bcms = get_mtd_actual_bcms(filters.site, filters.end_date)

    results.append({
        "excavator": "MTD Actual BCM",
        "truck": None,
        "mining_area": None,
        "mat_type": None,
        "bcms": mtd_actual_bcms,
        "indent": 0
    })

    return results, mtd_actual_bcms


# -------------------------------------------------------------
# Report Summary
# -------------------------------------------------------------
def get_report_summary(grand_total):
    formatted_total = f"{grand_total:,.0f}"
    return [{
        "label": _("MTD Actual BCM"),
        "value": formatted_total,
        "indicator": "Blue"
    }]
