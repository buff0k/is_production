## production_report.py
# Production Report for Hourly Production data
# Updated to support different time dimensions in table and chart.
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate
import datetime

### ---------------- Time Columns Helpers ----------------

def get_time_columns(production_entries, filters):
    """
    Build column definitions based on the user-selected time dimension.
    Options:
      - "Month Only": return monthly columns (e.g. "Feb 2025")
      - "Days and Month": return one column per day + one extra Month Total column
      - "Week and Month": return one column per ISO week + one extra Month Total column
    """
    time_column = filters.get("time_column", "Month Only")
    if time_column == "Month Only":
        return get_month_columns(production_entries)
    elif time_column == "Days and Month":
        return get_day_columns(production_entries)
    elif time_column == "Week and Month":
        return get_week_columns(production_entries)
    else:
        return get_month_columns(production_entries)

def get_month_columns(production_entries):
    """
    Return sorted monthly column definitions.
    Each column is a dict with:
      - key: a lowercase month-year string (e.g., "feb_2025")
      - label: e.g. "Feb 2025"
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
    columns = [{"key": k, "label": month_set[k]} for k in sorted_keys]
    return columns

def get_day_columns(production_entries):
    """
    Return sorted day-level columns plus one extra column for the monthly total.
    The day key is in the format "YYYY-MM-DD" and label is "DD MMM".
    The extra column uses key "month_total".
    """
    day_set = {}
    day_dates = {}
    for entry in production_entries:
        if entry.get("prod_date"):
            d = getdate(entry.get("prod_date"))
            key = d.strftime("%Y-%m-%d")
            label = d.strftime("%d %b")
            day_set[key] = label
            if key not in day_dates or d < day_dates[key]:
                day_dates[key] = d
    sorted_keys = sorted(day_dates, key=lambda k: day_dates[k])
    columns = [{"key": k, "label": day_set[k]} for k in sorted_keys]
    # Append an extra column for the monthly total:
    columns.append({"key": "month_total", "label": _("Month Total")})
    return columns

def get_week_columns(production_entries):
    """
    Return sorted week-level columns plus one extra column for the monthly total.
    The week key is in the format "YYYY-W##" and label is "W## (YYYY)".
    """
    week_set = {}
    week_dates = {}
    for entry in production_entries:
        if entry.get("prod_date"):
            d = getdate(entry.get("prod_date"))
            # Using ISO week number; include year for uniqueness
            iso_week = d.isocalendar()[1]
            key = f"{d.year}-W{iso_week:02d}"
            label = f"W{iso_week:02d} ({d.year})"
            week_set[key] = label
            # Use the first day of the week as sort key:
            if key not in week_dates or d < week_dates[key]:
                week_dates[key] = d
    sorted_keys = sorted(week_dates, key=lambda k: week_dates[k])
    columns = [{"key": k, "label": week_set[k]} for k in sorted_keys]
    # Append an extra column for the monthly total:
    columns.append({"key": "month_total", "label": _("Month Total")})
    return columns

### ---------------- Aggregation ----------------

def compute_time_sum(entries, field, columns, filters):
    """
    Compute sums per time column based on the provided column definitions and filter.
    For each entry, determine the appropriate key based on the filter:
      - Month Only: key is month (e.g., "feb_2025")
      - Days and Month: key is day ("YYYY-MM-DD")
      - Week and Month: key is "YYYY-W##"
    Additionally, if a "month_total" column is present, add all values there.
    """
    time_column = filters.get("time_column", "Month Only")
    sums = {col['key']: 0 for col in columns}
    for entry in entries:
        if entry.get("prod_date"):
            d = getdate(entry.get("prod_date"))
            if time_column == "Month Only":
                key = d.strftime("%b_%Y").lower()
            elif time_column == "Days and Month":
                key = d.strftime("%Y-%m-%d")
            elif time_column == "Week and Month":
                key = f"{d.year}-W{d.isocalendar()[1]:02d}"
            else:
                key = d.strftime("%b_%Y").lower()
            if key in sums:
                sums[key] += flt(entry.get(field, 0))
            # Also add to month_total if that column exists:
            if "month_total" in sums:
                sums["month_total"] += flt(entry.get(field, 0))
    for k in sums:
        sums[k] = int(round(sums[k]))
    return sums

### ---------------- Production Data Functions ----------------

def build_production_report_data(production_entries, columns, filters):
    """
    Build a hierarchical (flattened) list of rows from Hourly Production records.
    
    Hierarchy:
      Level 0 (indent: 0): "Total BCMs" – sum of hour_total_bcm per time interval
      Level 1 (indent: 1): Site (grouped by "location")
      Level 2 (indent: 2): Shift (grouped by "shift")
      Level 3 (indent: 3): Production Type breakdown:
                              • "Truck and Shoval BCM" (sum of total_ts_bcm)
                              • "Dozing BCM" (sum of total_dozing_bcm)
    """
    data = []
    # Level 0: Root "Total BCMs"
    root_sums = compute_time_sum(production_entries, "hour_total_bcm", columns, filters)
    root_row = {"label": "Total BCMs", "indent": 0, "is_group": True, "time_sums": root_sums}
    data.append(root_row)

    # Group by Site (location)
    sites = {}
    for entry in production_entries:
        site = entry.get("location")
        if site:
            sites.setdefault(site, []).append(entry)
    for site, site_entries in sorted(sites.items()):
        site_sums = compute_time_sum(site_entries, "hour_total_bcm", columns, filters)
        site_row = {"label": site, "indent": 1, "is_group": True, "time_sums": site_sums}
        data.append(site_row)

        # Group by Shift (removed day grouping)
        shifts = {}
        for entry in site_entries:
            shift = entry.get("shift")
            if shift:
                shifts.setdefault(shift, []).append(entry)
        for shift, shift_entries in sorted(shifts.items()):
            shift_sums = compute_time_sum(shift_entries, "hour_total_bcm", columns, filters)
            shift_row = {"label": shift, "indent": 2, "is_group": True, "time_sums": shift_sums}
            data.append(shift_row)

            # Level 3: Production Type breakdown
            ts_sums = compute_time_sum(shift_entries, "total_ts_bcm", columns, filters)
            dozing_sums = compute_time_sum(shift_entries, "total_dozing_bcm", columns, filters)
            ts_row = {"label": "Truck and Shoval BCM", "indent": 3, "is_group": False, "time_sums": ts_sums}
            dozing_row = {"label": "Dozing BCM", "indent": 3, "is_group": False, "time_sums": dozing_sums}
            data.append(ts_row)
            data.append(dozing_row)

    # Flatten the time_sums into each row dictionary so that the table can directly use the keys
    for row in data:
        if "time_sums" in row:
            row.update(row["time_sums"])
    return data

def get_columns(columns):
    """
    Build column definitions for the primary table.
    The first column is always the row label.
    """
    table_columns = [{
        "fieldname": "label",
        "label": _("Group"),
        "fieldtype": "Data",
        "width": 300
    }]
    for col in columns:
        table_columns.append({
            "fieldname": col["key"],
            "label": col["label"],
            "fieldtype": "Float",
            "width": 150,
            "precision": 0
        })
    return table_columns

def get_chart_data(columns, production_entries, filters):
    """
    Build a chart configuration showing production data at site level,
    using the same time dimension as the table.
    """
    time_column = filters.get("time_column", "Month Only")
    site_chart = {}
    for entry in production_entries:
        site = entry.get("location")
        if not site:
            continue
        d = getdate(entry.get("prod_date"))
        if time_column == "Month Only":
            key = d.strftime("%b_%Y").lower()
        elif time_column == "Days and Month":
            key = d.strftime("%Y-%m-%d")
        elif time_column == "Week and Month":
            key = f"{d.year}-W{d.isocalendar()[1]:02d}"
        else:
            key = d.strftime("%b_%Y").lower()
        if site not in site_chart:
            site_chart[site] = {col['key']: 0 for col in columns}
        if key in site_chart[site]:
            site_chart[site][key] += flt(entry.get("hour_total_bcm", 0))
        # Also add to month_total if that column exists:
        if "month_total" in site_chart[site]:
            site_chart[site]["month_total"] += flt(entry.get("hour_total_bcm", 0))
    for site in site_chart:
        for key in site_chart[site]:
            site_chart[site][key] = int(round(site_chart[site][key]))
    datasets = []
    for site, time_data in sorted(site_chart.items()):
        values = [time_data[col['key']] for col in columns]
        datasets.append({"name": site, "values": values})
    labels = [col['label'] for col in columns]
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
    prod_conditions = "WHERE 1=1"
    prod_params = {}
    if filters.get("from_date") and filters.get("to_date"):
        prod_conditions += " AND prod_date BETWEEN %(from_date)s AND %(to_date)s"
        prod_params["from_date"] = filters.get("from_date")
        prod_params["to_date"] = filters.get("to_date")
    if filters.get("site"):
        prod_conditions += " AND location = %(site)s"
        prod_params["site"] = filters.get("site")
        
    production_entries = frappe.db.sql(f"""
        SELECT location, prod_date, day_number, shift,
               hour_total_bcm, total_ts_bcm, total_dozing_bcm
        FROM `tabHourly Production`
        {prod_conditions}
        ORDER BY location, prod_date, shift
    """, prod_params, as_dict=1)

    # Determine the time columns based on the new filter.
    time_columns = get_time_columns(production_entries, filters)
    primary_data = build_production_report_data(production_entries, time_columns, filters)
    primary_columns = get_columns(time_columns)
    primary_chart = get_chart_data(time_columns, production_entries, filters)
    
    report_summary = []
    primitive_summary = None  # Not used in this report
    
    return primary_columns, primary_data, None, primary_chart, report_summary, primitive_summary
