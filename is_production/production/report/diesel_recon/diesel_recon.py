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
        key = current.strftime("%b_%Y").lower()  # e.g. "feb_2025"
        label = current.strftime("%b %Y")         # e.g. "Feb 2025"
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
        key = current.strftime("%Y-%m-%d")  # e.g. "2025-02-01"
        label = current.strftime("%d %b")    # e.g. "01 Feb"
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
        week_key = f"{current.year}-W{iso_week:02d}"  # e.g. "2025-W08"
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
    Options: "Month Only", "Days Only", "Weeks Only".
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
    Build the Diesel Receipts section.
    One Level 1 row ("(Diesel Receipts)") aggregates totals from Diesel Receipt records.
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
            bucket = get_time_bucket_key(d, filters.get("time_bucket", "Month Only"))
            receipt_asset_row[bucket] += flt(rec.get("litres_dispensed", 0))
    data.append(receipt_asset_row)
    return data

def build_diesel_issues_section(diesel_issues, time_columns, filters):
    """
    Build the Diesel Issues section from child table data.
    We retrieve Daily Diesel Entries (each with its parent's daily_sheet_date)
    and pivot them by time bucket, then group by asset_category and asset_name.
    This produces:
      - Level 1 row: Overall Diesel Issues total per time bucket.
      - Level 2 rows: One per unique asset_category (normalized), with totals per bucket.
      - Level 3 rows: One per asset within that category, with totals per bucket.
    """
    data = []
    asset = filters.get("asset_name")
    
    # Step 1: Get unique parent docnames from Daily Diesel Sheet records.
    parent_names = list(set(rec.get("name") for rec in diesel_issues if rec.get("name")))
    
    # Step 2: Retrieve child entries without grouping in SQL.
    child_entries = []
    if parent_names:
        child_entries = frappe.db.sql("""
            SELECT c.asset_name,
                   p.daily_sheet_date AS sample_date,
                   (SELECT asset_category FROM `tabAsset` WHERE name = c.asset_name) AS asset_category,
                   c.litres_issued
            FROM `tabDaily Diesel Entries` c
            JOIN `tabDaily Diesel Sheet` p ON c.parent = p.name
            WHERE p.name IN ({})
        """.format(", ".join(["%s"] * len(parent_names))), tuple(parent_names), as_dict=1)
    
    # Step 3: Pivot child entries into totals per time bucket.
    overall_totals = {}       # bucket -> total (Level 1)
    category_totals = {}      # norm_cat -> { bucket -> total } (Level 2)
    asset_totals = {}         # (norm_cat, asset_name) -> { bucket -> total } (Level 3)
    time_bucket = filters.get("time_bucket", "Month Only")
    for row in child_entries:
        sample_date = row.get("sample_date")
        if not sample_date:
            continue
        d = str_to_obj(sample_date)
        bucket = get_time_bucket_key(d, time_bucket)
        overall_totals[bucket] = overall_totals.get(bucket, 0) + flt(row.get("litres_issued"))
        asset_cat = row.get("asset_category") or "Unknown"
        norm_cat = asset_cat.strip().lower()
        if norm_cat not in category_totals:
            category_totals[norm_cat] = {}
        category_totals[norm_cat][bucket] = category_totals[norm_cat].get(bucket, 0) + flt(row.get("litres_issued"))
        key = (norm_cat, row.get("asset_name"))
        if key not in asset_totals:
            asset_totals[key] = {}
        asset_totals[key][bucket] = asset_totals[key].get(bucket, 0) + flt(row.get("litres_issued"))
    
    # Step 4: Build Level 1 row (overall total).
    issues_asset_row = {"label": f"{asset} (Diesel Issues)", "indent": 0, "is_group": True}
    for col in time_columns:
        b = col["key"]
        issues_asset_row[b] = overall_totals.get(b, 0)
    data.append(issues_asset_row)
    
    # Step 5: Build Level 2 and Level 3 rows grouped by asset_category.
    # We'll iterate over the unique normalized asset_category keys.
    for norm_cat in sorted(category_totals.keys()):
        level2_row = {"label": norm_cat.title(), "indent": 1, "is_group": False}
        for col in time_columns:
            b = col["key"]
            level2_row[b] = category_totals[norm_cat].get(b, 0)
        data.append(level2_row)
        # Level 3 rows: one per asset in this category.
        for (cat, asset_name) in sorted(asset_totals.keys()):
            if cat == norm_cat:
                level3_row = {"label": asset_name, "indent": 2, "is_group": False}
                for col in time_columns:
                    b = col["key"]
                    level3_row[b] = asset_totals[(cat, asset_name)].get(b, 0)
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
    
    # Query Diesel Receipt records (docstatus 0 or 1).
    conditions_receipts = "WHERE 1=1"
    params = {}
    conditions_receipts += " AND date_time_diesel_receipt BETWEEN %(from_date)s AND %(to_date)s"
    params["from_date"] = filters.get("from_date")
    params["to_date"] = filters.get("to_date")
    conditions_receipts += " AND location = %(site)s"
    params["site"] = filters.get("site")
    conditions_receipts += " AND asset_name = %(asset_name)s"
    params["asset_name"] = filters.get("asset_name")
    conditions_receipts += " AND docstatus IN (0,1)"
    
    diesel_receipts = frappe.db.sql(f"""
        SELECT asset_name, date_time_diesel_receipt, diesel_receipt, litres_dispensed
        FROM `tabDiesel Receipt`
        {conditions_receipts}
        ORDER BY diesel_receipt, date_time_diesel_receipt
    """, params, as_dict=1)
    
    # Query Daily Diesel Sheet records (docstatus 0 or 1).
    conditions_issues = "WHERE 1=1"
    params_issues = {}
    conditions_issues += " AND daily_sheet_date BETWEEN %(from_date)s AND %(to_date)s"
    params_issues["from_date"] = filters.get("from_date")
    params_issues["to_date"] = filters.get("to_date")
    conditions_issues += " AND location = %(site)s"
    params_issues["site"] = filters.get("site")
    conditions_issues += " AND asset_name = %(asset_name)s"
    params_issues["asset_name"] = filters.get("asset_name")
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
