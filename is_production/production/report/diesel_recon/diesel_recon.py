import datetime
import frappe
from frappe import _
from frappe.utils import getdate, flt, cint

def str_to_obj(dt_input):
    """
    Convert a datetime string to a Python datetime object.
    If dt_input is already a datetime or date object, return it directly.
    """
    from datetime import datetime, date
    if isinstance(dt_input, (datetime, date)):
        return dt_input
    try:
        return datetime.strptime(dt_input, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.strptime(dt_input, "%Y-%m-%d %H:%M:%S.%f")

def get_month_columns_from_date_range(from_date, to_date):
    """Generate monthly buckets between from_date and to_date."""
    columns = []
    current = from_date.replace(day=1)
    while current <= to_date:
        key = current.strftime("%b_%Y").lower()  # e.g., "feb_2025"
        label = current.strftime("%b %Y")         # e.g., "Feb 2025"
        columns.append({"key": key, "label": label})
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return columns

def get_day_columns_from_date_range(from_date, to_date):
    """Generate daily buckets between from_date and to_date."""
    columns = []
    current = from_date
    while current <= to_date:
        key = current.strftime("%Y-%m-%d")  # e.g., "2025-02-01"
        label = current.strftime("%d %b")    # e.g., "01 Feb"
        columns.append({"key": key, "label": label})
        current += datetime.timedelta(days=1)
    return columns

def get_week_columns_from_date_range(from_date, to_date):
    """
    Generate weekly buckets (using ISO weeks) between from_date and to_date.
    For each week, the label includes two lines:
      - First line: "W08 (2025)"
      - Second line: "WE Sun 23/2"
    """
    weeks = {}
    current = from_date
    while current <= to_date:
        iso_week = current.isocalendar()[1]
        week_key = f"{current.year}-W{iso_week:02d}"  # e.g., "2025-W08"
        if week_key not in weeks:
            year = int(week_key.split("-W")[0])
            week_num = int(week_key.split("-W")[1])
            sunday = datetime.date.fromisocalendar(year, week_num, 7)
            label = f"W{week_num:02d} ({year})\nWE {sunday.strftime('%a')} {sunday.day}/{sunday.month}"
            weeks[week_key] = label
        current += datetime.timedelta(days=1)
    sorted_week_keys = sorted(weeks.keys())
    columns = [{"key": key, "label": weeks[key]} for key in sorted_week_keys]
    return columns

def get_time_columns(filters):
    """
    Generate time bucket columns based on the 'time_bucket' filter.
    
    Options:
      - "Month Only": Monthly columns.
      - "Days Only": Daily columns.
      - "Weeks Only": Weekly columns.
    """
    time_bucket = filters.get("time_bucket", "Month Only")
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    
    if time_bucket == "Month Only":
        return get_month_columns_from_date_range(from_date, to_date)
    elif time_bucket == "Days Only":
        return get_day_columns_from_date_range(from_date, to_date)
    elif time_bucket == "Weeks Only":
        return get_week_columns_from_date_range(from_date, to_date)
    else:
        return get_month_columns_from_date_range(from_date, to_date)

def get_columns(time_columns):
    """
    Build column definitions for the report.
    The first column is for the row label.
    """
    columns = [{
        "fieldname": "label",
        "label": _("Identifier"),
        "fieldtype": "Data",
        "width": 300
    }]
    for col in time_columns:
        columns.append({
            "fieldname": col["key"],
            "label": col["label"],
            "fieldtype": "Float",
            "width": 150,
            "precision": 1
        })
    return columns

def get_time_bucket_key(d, time_bucket):
    """
    Returns a key corresponding to the time bucket for the given date/datetime object 'd'.
    """
    if time_bucket == "Month Only":
        return d.strftime("%b_%Y").lower()
    elif time_bucket == "Days Only":
        return d.strftime("%Y-%m-%d")
    elif time_bucket == "Weeks Only":
        return f"{d.year}-W{d.isocalendar()[1]:02d}"
    else:
        return d.strftime("%b_%Y").lower()

def build_diesel_receipts_section(diesel_receipts, time_columns, filters):
    """
    Build the Diesel Receipts section:
      - Level 1 row only: Asset (with "(Diesel Receipts)" appended),
        aggregating all litres_dispensed using date_time_diesel_receipt.
    """
    data = []
    asset = filters.get("asset_name")
    receipt_asset_row = {"label": f"{asset} (Diesel Receipts)", "indent": 0, "is_group": True}
    for col in time_columns:
        receipt_asset_row[col["key"]] = 0
    for rec in diesel_receipts:
        dt = rec.get("date_time_diesel_receipt")
        if dt:
            d = str_to_obj(dt)
            key = get_time_bucket_key(d, filters.get("time_bucket", "Month Only"))
            receipt_asset_row[key] += flt(rec.get("litres_dispensed", 0))
    data.append(receipt_asset_row)
    return data

def build_diesel_issues_section(diesel_issues, time_columns, filters):
    """
    Build the Diesel Issues section:
      - Level 1 row: Asset (with "(Diesel Issues)" appended) that aggregates all
        litres_issued_equipment from Daily Diesel Sheet records.
      - Then add new Level 2 rows grouping child records by asset_category (normalized)
        and Level 3 rows for each asset (from Daily Diesel Entries) with its aggregated
        sum of litres_issued.
    """
    data = []
    asset = filters.get("asset_name")
    issues_asset_row = {"label": f"{asset} (Diesel Issues)", "indent": 0, "is_group": True}
    for col in time_columns:
        issues_asset_row[col["key"]] = 0
    for rec in diesel_issues:
        dt = rec.get("daily_sheet_date")
        if dt:
            d = str_to_obj(dt)
            key = get_time_bucket_key(d, filters.get("time_bucket", "Month Only"))
            issues_asset_row[key] += flt(rec.get("litres_issued_equipment", 0))
    data.append(issues_asset_row)
    
    # Get parent's docnames from diesel_issues.
    parent_names = [rec.get("name") for rec in diesel_issues if rec.get("name")]
    if parent_names:
        # Query child table for these parents, grouping by asset_name.
        child_entries = frappe.db.sql("""
            SELECT asset_name, SUM(litres_issued) AS total_litres
            FROM `tabDaily Diesel Entries`
            WHERE parent IN ({})
            GROUP BY asset_name
        """.format(", ".join(["%s"] * len(parent_names))), tuple(parent_names), as_dict=1)
        
        # Group child entries by asset_category (normalized).
        category_groups = {}
        category_labels = {}
        for child in child_entries:
            a_name = child.get("asset_name")
            asset_cat = frappe.db.get_value("Asset", a_name, "asset_category") or "Unknown"
            norm_cat = asset_cat.strip().lower()
            if norm_cat not in category_groups:
                category_groups[norm_cat] = []
                category_labels[norm_cat] = asset_cat  # preserve original label
            category_groups[norm_cat].append(child)
        
        # For each asset_category, add a Level 2 row and then Level 3 rows.
        for norm_cat in sorted(category_groups.keys()):
            level2_row = {"label": category_labels[norm_cat], "indent": 1, "is_group": False}
            for col in time_columns:
                level2_row[col["key"]] = 0
            data.append(level2_row)
            for child in category_groups[norm_cat]:
                level3_row = {"label": child.get("asset_name"), "indent": 2, "is_group": False}
                for col in time_columns:
                    level3_row[col["key"]] = 0
                # Use a fixed bucket key derived from the filter's from_date (or adjust as needed).
                sample_date = getdate(filters.get("from_date"))
                bucket_key = get_time_bucket_key(sample_date, filters.get("time_bucket", "Month Only"))
                level3_row[bucket_key] = flt(child.get("total_litres"))
                level2_row[bucket_key] += flt(child.get("total_litres"))
                issues_asset_row[bucket_key] += flt(child.get("total_litres"))
                data.append(level3_row)
    
    return data

def execute(filters=None):
    filters = filters or {}
    
    # Validate required filters.
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are required"))
    if not filters.get("site"):
        frappe.throw(_("Site is required"))
    if not filters.get("asset_name"):
        frappe.throw(_("Asset is required"))
        
    # Calculate time bucket columns.
    time_columns = get_time_columns(filters)
    primary_columns = get_columns(time_columns)
    
    # Query Diesel Receipt records.
    conditions_receipts = "WHERE 1=1"
    params = {}
    conditions_receipts += " AND date_time_diesel_receipt BETWEEN %(from_date)s AND %(to_date)s"
    params["from_date"] = filters.get("from_date")
    params["to_date"] = filters.get("to_date")
    conditions_receipts += " AND location = %(site)s"
    params["site"] = filters.get("site")
    conditions_receipts += " AND asset_name = %(asset_name)s"
    params["asset_name"] = filters.get("asset_name")
    # Only select records with docstatus 0 or 1.
    conditions_receipts += " AND docstatus IN (0,1)"
    
    diesel_receipts = frappe.db.sql(f"""
        SELECT asset_name, date_time_diesel_receipt, diesel_receipt, litres_dispensed
        FROM `tabDiesel Receipt`
        {conditions_receipts}
        ORDER BY diesel_receipt, date_time_diesel_receipt
    """, params, as_dict=1)
    
    # Query Daily Diesel Sheet records.
    conditions_issues = "WHERE 1=1"
    params_issues = {}
    conditions_issues += " AND daily_sheet_date BETWEEN %(from_date)s AND %(to_date)s"
    params_issues["from_date"] = filters.get("from_date")
    params_issues["to_date"] = filters.get("to_date")
    conditions_issues += " AND location = %(site)s"
    params_issues["site"] = filters.get("site")
    conditions_issues += " AND asset_name = %(asset_name)s"
    params_issues["asset_name"] = filters.get("asset_name")
    # Only select records with docstatus 0 or 1.
    conditions_issues += " AND docstatus IN (0,1)"
    
    diesel_issues = frappe.db.sql(f"""
        SELECT name, asset_name, daily_diesel_sheet_ref, daily_sheet_date, litres_issued_equipment
        FROM `tabDaily Diesel Sheet`
        {conditions_issues}
        ORDER BY daily_diesel_sheet_ref, daily_sheet_date
    """, params_issues, as_dict=1)
    
    # Build hierarchical sections.
    receipts_section = build_diesel_receipts_section(diesel_receipts, time_columns, filters)
    issues_section = build_diesel_issues_section(diesel_issues, time_columns, filters)
    
    # Combine the sections.
    data = receipts_section + issues_section
    
    return primary_columns, data, None, None, [], None
