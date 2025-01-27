# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

# Diesel Usage Site Analyses Report

import frappe

def execute(filters=None):
    columns, data = get_columns(), get_data(filters)

    # Add total row for each group
    grouped_totals = {}
    grand_total = 0
    for row in data:
        group_value = row.get("group_value")
        if group_value not in grouped_totals:
            grouped_totals[group_value] = 0
        grouped_totals[group_value] += row.get("litres_issued", 0)
        grand_total += row.get("litres_issued", 0)

    # Check if the filter is set to show only totals
    if filters.get("view_mode") == "Only Totals":
        data = []
        for group_value, total in grouped_totals.items():
            data.append({
                "day": "Total",
                "group_value": group_value,
                "litres_issued": total,
                "asset_category": None,
                "docstatus": None
            })

        # Append grand total row
        data.append({
            "day": "Grand Total",
            "group_value": None,
            "litres_issued": grand_total,
            "asset_category": None,
            "docstatus": None
        })
    else:
        # Append total rows to the data for detailed view
        for group_value, total in grouped_totals.items():
            data.append({
                "day": "Total",
                "group_value": group_value,
                "litres_issued": total,
                "asset_category": None,
                "docstatus": None
            })

        # Append grand total row
        data.append({
            "day": "Grand Total",
            "group_value": None,
            "litres_issued": grand_total,
            "asset_category": None,
            "docstatus": None
        })

    # Sort to ensure totals appear at the end of each group
    data.sort(key=lambda x: (x["group_value"] if x["group_value"] else "", x["day"] != "Total"))

    return columns, data

def get_columns():
    return [
        {"fieldname": "day", "label": "Day", "fieldtype": "Data", "width": 120},
        {"fieldname": "group_value", "label": "Group Value", "fieldtype": "Data", "width": 150},
        {"fieldname": "litres_issued", "label": "Total Litres Issued", "fieldtype": "Float", "width": 120},
        {"fieldname": "asset_category", "label": "Asset Category", "fieldtype": "Data", "width": 150},
        {"fieldname": "docstatus", "label": "Docstatus", "fieldtype": "Data", "width": 100}
    ]

def get_data(filters):
    # Determine group by field based on the filter
    if filters.get("group_by") == "Site":
        group_by_field = "dds.location"
    elif filters.get("group_by") == "Asset Name":
        group_by_field = "dde.asset_name"
    elif filters.get("group_by") == "Asset Category":
        group_by_field = "a.asset_category"
    else:
        group_by_field = ""

    # Additional field for asset_category if grouping by asset_name or asset_category
    additional_field = ", a.asset_category" if filters.get("group_by") in ["Asset Name", "Asset Category"] else ""

    # SQL query to sum up litres issued grouped by the selected field
    query = f"""
    SELECT
        DATE_FORMAT(dds.daily_sheet_date, '%%Y-%%m-%%d') AS day,
        {group_by_field} AS group_value
        {additional_field},
        dds.docstatus,
        SUM(dde.litres_issued) AS litres_issued
    FROM
        `tabDaily Diesel Entries` AS dde
    INNER JOIN
        `tabDaily Diesel Sheet` AS dds ON dde.parent = dds.name
    LEFT JOIN
        `tabAsset` AS a ON dde.asset_name = a.name
    WHERE
        dds.daily_sheet_date IS NOT NULL
    """

    # Apply filters dynamically
    conditions = []
    if filters:
        if filters.get("date_from"):
            conditions.append("dds.daily_sheet_date >= %(date_from)s")
        if filters.get("date_to"):
            conditions.append("dds.daily_sheet_date <= %(date_to)s")
        if filters.get("site"):
            conditions.append("dds.location = %(site)s")
        if filters.get("asset_name"):
            conditions.append("dde.asset_name = %(asset_name)s")
        if filters.get("docstatus") is not None:
            conditions.append("dds.docstatus = %(docstatus)s")
        if filters.get("asset_category"):
            conditions.append("a.asset_category = %(asset_category)s")

    # Add conditions to the query
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    # Add GROUP BY and ORDER BY clauses
    if group_by_field:
        query += f" GROUP BY day, {group_by_field}"
        if filters.get("group_by") == "Asset Name":
            query += ", a.asset_category"
    query += f" ORDER BY day, {group_by_field}"

    # Execute the query with filters
    data = frappe.db.sql(query, filters, as_dict=True)

    # Format the data for the report
    formatted_data = [
        {
            "day": row["day"],
            "group_value": row["group_value"],
            "litres_issued": row["litres_issued"],
            "asset_category": row.get("asset_category") if filters.get("group_by") in ["Asset Name", "Asset Category"] else None,
            "docstatus": "Draft" if row["docstatus"] == 0 else "Submitted"
        }
        for row in data
    ]

    return formatted_data