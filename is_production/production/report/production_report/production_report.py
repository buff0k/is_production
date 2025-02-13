## production_report.py
# Production Report for Hourly Production data
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate
import datetime

### ---------------- Primary Data Functions (Hourly Production) ----------------

def get_months_from_entries(production_entries):
    """
    Build a sorted list of month dictionaries from Hourly Production entries using prod_date.
    Each dictionary has:
      - key: a lowercase month-year string (e.g., "feb_2025")
      - label: a display label (e.g., "Feb 2025")
    """
    month_set = {}
    month_dates = {}
    for entry in production_entries:
        if entry.get("prod_date"):
            d = getdate(entry.get("prod_date"))
            key = d.strftime("%b_%Y").lower()
            label = d.strftime("%b %Y")
            month_set[key] = label
            if key not in month_dates or d < month_dates[key]:
                month_dates[key] = d
    sorted_keys = sorted(month_dates, key=lambda k: month_dates[k])
    months = [{"key": k, "label": month_set[k]} for k in sorted_keys]
    return months

def build_production_report_data(production_entries, months):
    """
    Build a hierarchical (flattened) list of rows from Hourly Production records.
    
    Hierarchy:
      Level 0 (indent: 0): "Total BCMs" – sum of hour_total_bcm per month
      Level 1 (indent: 1): Site (grouped by "location")
      Level 2 (indent: 2): Day (grouped by "day_number", sorted descending)
      Level 3 (indent: 3): Shift (grouped by "shift")
      Level 4 (indent: 4): Production Type breakdown:
                              • "Truck and Shoval BCM" (sum of total_ts_bcm)
                              • "Dozing BCM" (sum of total_dozing_bcm)
    """
    def get_month_key(prod_date):
        d = getdate(prod_date) if not isinstance(prod_date, datetime.date) else prod_date
        return d.strftime("%b_%Y").lower()

    def compute_monthly_sum(entries, field):
        sums = {m['key']: 0 for m in months}
        for entry in entries:
            if entry.get("prod_date"):
                mk = get_month_key(entry.get("prod_date"))
                if mk in sums:
                    sums[mk] += flt(entry.get(field, 0))
        for key in sums:
            sums[key] = int(round(sums[key]))
        return sums

    data = []
    # Level 0: Root "Total BCMs"
    root_sums = compute_monthly_sum(production_entries, "hour_total_bcm")
    root_row = {"label": "Total BCMs", "indent": 0, "is_group": True, "month_sums": root_sums}
    data.append(root_row)

    # Group by Site (location)
    sites = {}
    for entry in production_entries:
        site = entry.get("location")
        if site:
            sites.setdefault(site, []).append(entry)
    for site, site_entries in sorted(sites.items()):
        site_sums = compute_monthly_sum(site_entries, "hour_total_bcm")
        site_row = {"label": site, "indent": 1, "is_group": True, "month_sums": site_sums}
        data.append(site_row)

        # Group by Day (sorted descending)
        days = {}
        for entry in site_entries:
            day = entry.get("day_number")
            if day is not None:
                days.setdefault(day, []).append(entry)
        for day, day_entries in sorted(days.items(), key=lambda x: x[0], reverse=True):
            day_sums = compute_monthly_sum(day_entries, "hour_total_bcm")
            day_row = {"label": f"Day {day}", "indent": 2, "is_group": True, "month_sums": day_sums}
            data.append(day_row)

            # Group by Shift
            shifts = {}
            for entry in day_entries:
                shift = entry.get("shift")
                if shift:
                    shifts.setdefault(shift, []).append(entry)
            for shift, shift_entries in sorted(shifts.items()):
                shift_sums = compute_monthly_sum(shift_entries, "hour_total_bcm")
                shift_row = {"label": shift, "indent": 3, "is_group": True, "month_sums": shift_sums}
                data.append(shift_row)

                # Level 4: Production Type breakdown
                ts_sums = compute_monthly_sum(shift_entries, "total_ts_bcm")
                dozing_sums = compute_monthly_sum(shift_entries, "total_dozing_bcm")
                ts_row = {"label": "Truck and Shoval BCM", "indent": 4, "is_group": False, "month_sums": ts_sums}
                dozing_row = {"label": "Dozing BCM", "indent": 4, "is_group": False, "month_sums": dozing_sums}
                data.append(ts_row)
                data.append(dozing_row)
    for row in data:
        if "month_sums" in row:
            row.update(row["month_sums"])
    return data

def get_columns(months):
    """
    Build column definitions for the primary table.
    """
    columns = [{
        "fieldname": "label",
        "label": _("Group"),
        "fieldtype": "Data",
        "width": 300
    }]
    for m in months:
        columns.append({
            "fieldname": m["key"],
            "label": m["label"],
            "fieldtype": "Float",
            "width": 150,
            "precision": 0
        })
    return columns

def get_chart_data(months, production_entries):
    """
    Build a chart configuration showing monthly BCM values at site level.
    """
    site_chart = {}
    for entry in production_entries:
        site = entry.get("location")
        if not site:
            continue
        d = getdate(entry.get("prod_date"))
        mk = d.strftime("%b_%Y").lower()
        if site not in site_chart:
            site_chart[site] = {m['key']: 0 for m in months}
        if mk in site_chart[site]:
            site_chart[site][mk] += flt(entry.get("hour_total_bcm", 0))
    for site in site_chart:
        for key in site_chart[site]:
            site_chart[site][key] = int(round(site_chart[site][key]))
    datasets = []
    for site, monthly_data in sorted(site_chart.items()):
        values = [monthly_data[m['key']] for m in months]
        datasets.append({"name": site, "values": values})
    labels = [m['label'] for m in months]
    chart = {
        "data": {"labels": labels, "datasets": datasets},
        "type": "line",
        "fieldtype": "Float",
        "options": ""
    }
    return chart

### ---------------- Execute Function ----------------
def execute(filters=None):
    filters = filters or {}
    prod_conditions = ""
    prod_params = {}
    if filters.get("from_date") and filters.get("to_date"):
        prod_conditions = "WHERE prod_date BETWEEN %(from_date)s AND %(to_date)s"
        prod_params["from_date"] = filters.get("from_date")
        prod_params["to_date"] = filters.get("to_date")
    production_entries = frappe.db.sql(f"""
        SELECT location, prod_date, day_number, shift,
               hour_total_bcm, total_ts_bcm, total_dozing_bcm
        FROM `tabHourly Production`
        {prod_conditions}
        ORDER BY location, prod_date, day_number, shift
    """, prod_params, as_dict=1)
    months = get_months_from_entries(production_entries)
    primary_data = build_production_report_data(production_entries, months)
    primary_columns = get_columns(months)
    primary_chart = get_chart_data(months, production_entries)
    
    report_summary = []
    primitive_summary = None  # Not used in this report
    
    return primary_columns, primary_data, None, primary_chart, report_summary, primitive_summary
