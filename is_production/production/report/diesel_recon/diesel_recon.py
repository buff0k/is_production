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
        # Move to the first day of next month:
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
    """Generate weekly buckets (using ISO weeks) between from_date and to_date."""
    weeks = {}
    current = from_date
    while current <= to_date:
        iso_week = current.isocalendar()[1]
        week_key = f"{current.year}-W{iso_week:02d}"  # e.g., "2025-W05"
        if week_key not in weeks:
            weeks[week_key] = f"W{iso_week:02d} ({current.year})"
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
        # Fallback to Month Only if an invalid option is provided.
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
      - Top-level row: Asset (with "(Diesel Receipts)" appended).
      - Detail rows (indent 1): Group by diesel_receipt; aggregate litres_dispensed
        using date_time_diesel_receipt.
    """
    data = []
    asset = filters.get("asset_name")
    receipt_asset_row = {"label": f"{asset} (Diesel Receipts)", "indent": 0, "is_group": True}
    for col in time_columns:
        receipt_asset_row[col["key"]] = 0
    data.append(receipt_asset_row)
    
    # Group records by diesel_receipt.
    receipt_groups = {}
    for rec in diesel_receipts:
        dr_no = rec.get("diesel_receipt")
        receipt_groups.setdefault(dr_no, []).append(rec)
    
    for dr_no in sorted(receipt_groups.keys()):
        row = {"label": dr_no, "indent": 1, "is_group": False}
        for col in time_columns:
            row[col["key"]] = 0
        for rec in receipt_groups[dr_no]:
            dt = rec.get("date_time_diesel_receipt")
            if dt:
                d = str_to_obj(dt)
                key = get_time_bucket_key(d, filters.get("time_bucket", "Month Only"))
                row[key] += flt(rec.get("litres_dispensed", 0))
        data.append(row)
        # Aggregate detail rows into the top-level asset row.
        for col in time_columns:
            receipt_asset_row[col["key"]] += row[col["key"]]
    
    return data

def build_diesel_issues_section(diesel_issues, time_columns, filters):
    """
    Build the Diesel Issues section:
      - Top-level row: Asset (with "(Diesel Issues)" appended).
      - Detail rows (indent 1): Group by daily_diesel_sheet_ref; aggregate litres_issued_equipment
        using daily_sheet_date.
    """
    data = []
    asset = filters.get("asset_name")
    issues_asset_row = {"label": f"{asset} (Diesel Issues)", "indent": 0, "is_group": True}
    for col in time_columns:
        issues_asset_row[col["key"]] = 0
    data.append(issues_asset_row)
    
    # Group records by daily_diesel_sheet_ref.
    issues_groups = {}
    for rec in diesel_issues:
        ref = rec.get("daily_diesel_sheet_ref")
        issues_groups.setdefault(ref, []).append(rec)
    
    for ref in sorted(issues_groups.keys()):
        row = {"label": ref, "indent": 1, "is_group": False}
        for col in time_columns:
            row[col["key"]] = 0
        for rec in issues_groups[ref]:
            dt = rec.get("daily_sheet_date")
            if dt:
                d = str_to_obj(dt)
                key = get_time_bucket_key(d, filters.get("time_bucket", "Month Only"))
                row[key] += flt(rec.get("litres_issued_equipment", 0))
        data.append(row)
        # Aggregate detail rows into the top-level asset row.
        for col in time_columns:
            issues_asset_row[col["key"]] += row[col["key"]]
    
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
    
    diesel_issues = frappe.db.sql(f"""
        SELECT asset_name, daily_diesel_sheet_ref, daily_sheet_date, litres_issued_equipment
        FROM `tabDaily Diesel Sheet`
        {conditions_issues}
        ORDER BY daily_diesel_sheet_ref, daily_sheet_date
    """, params_issues, as_dict=1)
    
    # Build hierarchical sections.
    receipts_section = build_diesel_receipts_section(diesel_receipts, time_columns, filters)
    issues_section = build_diesel_issues_section(diesel_issues, time_columns, filters)
    
    # Combine the two sections.
    data = receipts_section + issues_section
    
    # Return the report without a chart.
    return primary_columns, data, None, None, [], None
