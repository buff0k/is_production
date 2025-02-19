## production_report.py
# Production Report for Hourly Production data (with Diesel and Fuel Cap)
# Supports different time dimensions and separate indent structures for BCMs, Diesel, and Fuel Cap.
# Fuel Cap is calculated as (Diesel Litres) / (BCM).
# Time buckets are generated from the date range filters.
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate
import datetime

### ---------------- Time Columns (Based on Date Range) ----------------

def get_time_columns(filters):
    """
    Build column definitions based on the user-selected time dimension and the date range.
    Options:
      - "Month Only": return monthly columns (e.g. "Feb 2025")
      - "Days and Month": return one column per day plus a separate Month Total column for each month
      - "Week and Month": return one column per ISO week plus a separate Month Total column for each month
      - "Days Only": return one column per day only
      - "Weeks Only": return one column per ISO week only
    """
    time_column = filters.get("time_column", "Month Only")
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    
    if time_column == "Month Only":
        return get_month_columns_from_date_range(from_date, to_date)
    elif time_column == "Days and Month":
        return get_day_columns_from_date_range(from_date, to_date)
    elif time_column == "Weeks and Month":
        return get_week_columns_from_date_range(from_date, to_date)
    elif time_column == "Days Only":
        return get_day_columns_from_date_range_days_only(from_date, to_date)
    elif time_column == "Weeks Only":
        return get_week_columns_from_date_range_weeks_only(from_date, to_date)
    else:
        return get_month_columns_from_date_range(from_date, to_date)

def get_month_columns_from_date_range(from_date, to_date):
    """
    Generate monthly buckets between from_date and to_date.
    """
    columns = []
    current = from_date.replace(day=1)
    while current <= to_date:
        key = current.strftime("%b_%Y").lower()
        label = current.strftime("%b %Y")
        columns.append({"key": key, "label": label})
        # Move to first day of next month:
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return columns

def get_day_columns_from_date_range(from_date, to_date):
    """
    Generate daily buckets between from_date and to_date,
    plus a separate Month Total column for each month present in the date range.
    """
    columns = []
    month_order = []  # keep track of month keys in order of appearance
    current = from_date
    while current <= to_date:
        key = current.strftime("%Y-%m-%d")
        label = current.strftime("%d %b")
        columns.append({"key": key, "label": label})
        # Record month key if not already added
        month_key = current.strftime("%b_%Y").lower()
        if month_key not in month_order:
            month_order.append(month_key)
        current += datetime.timedelta(days=1)
    # Add a Month Total column for each distinct month
    for month_key in month_order:
        columns.append({
            "key": f"month_total_{month_key}",
            "label": _(f"{month_key.split('_')[0]} Total")
        })
    return columns

def get_week_columns_from_date_range(from_date, to_date):
    """
    Generate weekly buckets between from_date and to_date (using ISO weeks),
    plus a separate Month Total column for each month present in the date range.
    """
    weeks = {}
    month_order = []  # keep track of month keys in order of appearance
    current = from_date
    while current <= to_date:
        iso_week = current.isocalendar()[1]
        week_key = f"{current.year}-W{iso_week:02d}"
        if week_key not in weeks:
            weeks[week_key] = f"W{iso_week:02d} ({current.year})"
        # Record month key if not already added
        month_key = current.strftime("%b_%Y").lower()
        if month_key not in month_order:
            month_order.append(month_key)
        current += datetime.timedelta(days=1)
    sorted_week_keys = sorted(weeks.keys())
    columns = [{"key": key, "label": weeks[key]} for key in sorted_week_keys]
    # Append a Month Total column for each distinct month
    for month_key in month_order:
        columns.append({
            "key": f"month_total_{month_key}",
            "label": _(f"{month_key.split('_')[0]} Total")
        })
    return columns

def get_day_columns_from_date_range_days_only(from_date, to_date):
    """
    Generate daily buckets between from_date and to_date without monthly total columns.
    """
    columns = []
    current = from_date
    while current <= to_date:
        key = current.strftime("%Y-%m-%d")
        label = current.strftime("%d %b")
        columns.append({"key": key, "label": label})
        current += datetime.timedelta(days=1)
    return columns

def get_week_columns_from_date_range_weeks_only(from_date, to_date):
    """
    Generate weekly buckets between from_date and to_date (using ISO weeks) without monthly total columns.
    """
    weeks = {}
    current = from_date
    while current <= to_date:
        iso_week = current.isocalendar()[1]
        week_key = f"{current.year}-W{iso_week:02d}"
        if week_key not in weeks:
            weeks[week_key] = f"W{iso_week:02d} ({current.year})"
        current += datetime.timedelta(days=1)
    sorted_week_keys = sorted(weeks.keys())
    columns = [{"key": key, "label": weeks[key]} for key in sorted_week_keys]
    return columns

### ---------------- Aggregation Functions ----------------

def compute_time_sum(entries, field, columns, filters):
    """
    Compute sums per time column for production entries based on the prod_date field.
    Also aggregates separate month totals for "Days and Month" and "Week and Month".
    For "Days Only" and "Weeks Only", only the individual day/week values are calculated.
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
                month_key = f"month_total_{d.strftime('%b_%Y').lower()}"
            elif time_column == "Days Only":
                key = d.strftime("%Y-%m-%d")
            elif time_column == "Week and Month":
                key = f"{d.year}-W{d.isocalendar()[1]:02d}"
                month_key = f"month_total_{d.strftime('%b_%Y').lower()}"
            elif time_column == "Weeks Only":
                key = f"{d.year}-W{d.isocalendar()[1]:02d}"
            else:
                key = d.strftime("%b_%Y").lower()

            if key in sums:
                sums[key] += flt(entry.get(field, 0))
            # For day/week selections with month totals, also add to the corresponding monthly total column
            if time_column in ("Days and Month", "Week and Month") and month_key in sums:
                sums[month_key] += flt(entry.get(field, 0))
    for k in sums:
        sums[k] = int(round(sums[k]))
    return sums

def compute_diesel_sum(entries, columns, filters):
    """
    Compute diesel litres sum for each time column.
    Also aggregates separate month totals for "Days and Month" and "Week and Month".
    Uses the diesel_date field (aliased from daily_sheet_date).
    """
    time_column = filters.get("time_column", "Month Only")
    sums = {col['key']: 0 for col in columns}
    for entry in entries:
        if entry.get("diesel_date"):
            d = getdate(entry.get("diesel_date"))
            if time_column == "Month Only":
                key = d.strftime("%b_%Y").lower()
            elif time_column == "Days and Month":
                key = d.strftime("%Y-%m-%d")
                month_key = f"month_total_{d.strftime('%b_%Y').lower()}"
            elif time_column == "Days Only":
                key = d.strftime("%Y-%m-%d")
            elif time_column == "Week and Month":
                key = f"{d.year}-W{d.isocalendar()[1]:02d}"
                month_key = f"month_total_{d.strftime('%b_%Y').lower()}"
            elif time_column == "Weeks Only":
                key = f"{d.year}-W{d.isocalendar()[1]:02d}"
            else:
                key = d.strftime("%b_%Y").lower()

            if key in sums:
                sums[key] += flt(entry.get("litres", 0))
            if time_column in ("Days and Month", "Week and Month") and month_key in sums:
                sums[month_key] += flt(entry.get("litres", 0))
    for k in sums:
        sums[k] = int(round(sums[k]))
    return sums

def compute_fuelcap(bcm, diesel, columns):
    """
    Compute Fuel Cap as (Diesel Litres) / (BCM) for each time bucket.
    If BCM is zero, Fuel Cap is set to 0.
    Returns a dictionary with the same keys as columns.
    """
    result = {}
    for col in columns:
        key = col['key']
        bcm_val = bcm.get(key, 0)
        diesel_val = diesel.get(key, 0)
        if bcm_val:
            result[key] = round(diesel_val / bcm_val, 2)
        else:
            result[key] = 0
    return result

### ---------------- Report Data Building ----------------

def build_report_with_total_bcm_and_diesel(production_entries, diesel_entries, columns, filters):
    """
    Build a flattened list of rows that includes three sections:

    Production (BCM) Section:
      - Top Level: "BCM Total" (aggregated from production data)
      - Under BCM Total: Group by Site (indent level 1)
          - Under each Site: Two rows (indent level 2) for type breakdown:
            • "Truck and Shoval BCM" (using total_ts_bcm)
            • "Dozing BCM" (using total_dozing_bcm)

    Diesel Section:
      - Top Level: "Diesel Total" (aggregated from diesel data)
      - Under Diesel Total: Group by Site (indent level 1)

    Fuel Cap Section:
      - Top Level: "Fuel Cap Total" (calculated as Diesel/BCM from overall totals)
      - Under Fuel Cap Total: Group by Site (indent level 1)
        (Fuel Cap = Site Diesel / Site BCM)
    """
    data = []
    
    # ---- Production (BCM) Section ----
    bcm_total_sums = compute_time_sum(production_entries, "hour_total_bcm", columns, filters)
    bcm_total_row = {"label": "BCM Total", "indent": 0, "is_group": True, "time_sums": bcm_total_sums}
    data.append(bcm_total_row)
    
    # Group production entries by site
    sites = {}
    for entry in production_entries:
        site = entry.get("location")
        if site:
            sites.setdefault(site, []).append(entry)
    
    # Store site-level production sums for later fuel cap calculations
    site_bcm_totals = {}
    
    for site, site_entries in sorted(sites.items()):
        site_bcm_sums = compute_time_sum(site_entries, "hour_total_bcm", columns, filters)
        site_bcm_totals[site] = site_bcm_sums  # save for fuel cap
        site_row = {"label": site, "indent": 1, "is_group": True, "time_sums": site_bcm_sums}
        data.append(site_row)
        
        # Material type breakdown (indent level 2)
        ts_sums = compute_time_sum(site_entries, "total_ts_bcm", columns, filters)
        ts_row = {"label": "Truck and Shoval BCM", "indent": 2, "is_group": False, "time_sums": ts_sums}
        data.append(ts_row)
        
        dozing_sums = compute_time_sum(site_entries, "total_dozing_bcm", columns, filters)
        dozing_row = {"label": "Dozing BCM", "indent": 2, "is_group": False, "time_sums": dozing_sums}
        data.append(dozing_row)
    
    # ---- Diesel Section ----
    diesel_total_sums = compute_diesel_sum(diesel_entries, columns, filters)
    diesel_total_row = {"label": "Diesel Total", "indent": 0, "is_group": True, "time_sums": diesel_total_sums}
    data.append(diesel_total_row)
    
    # Group diesel entries by site
    diesel_sites = {}
    for d in diesel_entries:
        site = d.get("location")
        if site:
            diesel_sites.setdefault(site, []).append(d)
    
    # Save site-level diesel sums for fuel cap calculations
    site_diesel_totals = {}
    
    for site, site_diesel_entries in sorted(diesel_sites.items()):
        site_diesel_sums = compute_diesel_sum(site_diesel_entries, columns, filters)
        site_diesel_totals[site] = site_diesel_sums
        diesel_site_row = {"label": site, "indent": 1, "is_group": False, "time_sums": site_diesel_sums}
        data.append(diesel_site_row)
    
    # ---- Fuel Cap Section ----
    # Top Level Fuel Cap Total = Diesel Total / BCM Total (per time bucket)
    fuelcap_total = compute_fuelcap(bcm_total_sums, diesel_total_sums, columns)
    fuelcap_total_row = {"label": "Fuel Cap Total", "indent": 0, "is_group": True, "time_sums": fuelcap_total}
    data.append(fuelcap_total_row)
    
    # For each site, calculate Fuel Cap = site diesel / site bcm.
    # We'll take the union of sites present in production or diesel.
    all_sites = set(list(site_bcm_totals.keys()) + list(site_diesel_totals.keys()))
    for site in sorted(all_sites):
        site_bcm = site_bcm_totals.get(site, {col['key']: 0 for col in columns})
        site_diesel = site_diesel_totals.get(site, {col['key']: 0 for col in columns})
        site_fuelcap = compute_fuelcap(site_bcm, site_diesel, columns)
        fuelcap_site_row = {"label": "Fuel Cap - " + site, "indent": 1, "is_group": False, "time_sums": site_fuelcap}
        data.append(fuelcap_site_row)
    
    # Flatten the time_sums into each row dictionary so that the table can directly use the keys.
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
        elif time_column in ("Days and Month", "Days Only"):
            key = d.strftime("%Y-%m-%d")
        elif time_column in ("Week and Month", "Weeks Only"):
            key = f"{d.year}-W{d.isocalendar()[1]:02d}"
        else:
            key = d.strftime("%b_%Y").lower()
        if site not in site_chart:
            site_chart[site] = {col['key']: 0 for col in columns}
        if key in site_chart[site]:
            site_chart[site][key] += flt(entry.get("hour_total_bcm", 0))
        if time_column in ("Days and Month", "Week and Month"):
            month_key = f"month_total_{d.strftime('%b_%Y').lower()}"
            if month_key in site_chart[site]:
                site_chart[site][month_key] += flt(entry.get("hour_total_bcm", 0))
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
    
    # --- Production Data Query ---
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
    
    # --- Diesel Data Query ---
    # Using parent table 'tabDaily Diesel Sheet' (alias p) and child table 'tabDaily Diesel Entries' (alias c)
    diesel_conditions = "WHERE 1=1"
    diesel_params = {}
    if filters.get("from_date") and filters.get("to_date"):
        diesel_conditions += " AND p.daily_sheet_date BETWEEN %(from_date)s AND %(to_date)s"
        diesel_params["from_date"] = filters.get("from_date")
        diesel_params["to_date"] = filters.get("to_date")
    if filters.get("site"):
        diesel_conditions += " AND p.location = %(site)s"
        diesel_params["site"] = filters.get("site")
    if filters.get("exclude_assets"):
        excluded_assets = tuple(filters.get("exclude_assets"))
        diesel_conditions += " AND c.asset_name NOT IN %(excluded_assets)s"
        diesel_params["excluded_assets"] = excluded_assets

    diesel_query = f"""
        SELECT 
            p.location, 
            p.daily_sheet_date as diesel_date, 
            SUM(c.litres_issued) as litres
        FROM `tabDaily Diesel Sheet` p
        JOIN `tabDaily Diesel Entries` c ON c.parent = p.name
        {diesel_conditions}
        GROUP BY p.location, p.daily_sheet_date
        ORDER BY p.location, p.daily_sheet_date
    """
    
    diesel_entries = frappe.db.sql(diesel_query, diesel_params, as_dict=1)
    
    # --- Time Columns & Report Building ---
    time_columns = get_time_columns(filters)
    primary_data = build_report_with_total_bcm_and_diesel(production_entries, diesel_entries, time_columns, filters)
    primary_columns = get_columns(time_columns)
    primary_chart = get_chart_data(time_columns, production_entries, filters)
    
    report_summary = []
    primitive_summary = None
    
    return primary_columns, primary_data, None, primary_chart, report_summary, primitive_summary
