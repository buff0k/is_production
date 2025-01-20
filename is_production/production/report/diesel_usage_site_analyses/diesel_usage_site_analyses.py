# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

# Diesel Usage Site Analyses Report

# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

# Diesel Usage Site Analyses Report

import frappe

def execute(filters=None):
    return get_columns(), get_data(filters)

def get_columns():
    return [
        {"fieldname": "month", "label": "Month", "fieldtype": "Data", "width": 120},
        {"fieldname": "group_value", "label": "Group Value", "fieldtype": "Data", "width": 150},
        {"fieldname": "litres_issued", "label": "Total Litres Issued", "fieldtype": "Float", "width": 120},
        {"fieldname": "asset_category", "label": "Asset Category", "fieldtype": "Data", "width": 150}
    ]

def get_data(filters):
    # Determine group by field based on the filter
    group_by_field = "dds.location" if filters.get("group_by") == "Site" else "dde.asset_name"

    # Additional field for asset_category if grouping by asset_name
    additional_field = ", a.asset_category" if filters.get("group_by") == "Asset Name" else ""

    # SQL query to sum up litres issued grouped by the selected field
    query = f"""
    SELECT
        DATE_FORMAT(dds.daily_sheet_date, '%%Y-%%m') AS month,
        {group_by_field} AS group_value
        {additional_field},
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
        if filters.get("year"):
            conditions.append("YEAR(dds.daily_sheet_date) = %(year)s")
        if filters.get("month"):
            conditions.append("MONTH(dds.daily_sheet_date) = %(month)s")
        if filters.get("site"):
            conditions.append("dds.location = %(site)s")
        if filters.get("asset_name"):
            conditions.append("dde.asset_name = %(asset_name)s")

    # Add conditions to the query
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    # Add GROUP BY and ORDER BY clauses
    query += f" GROUP BY month, {group_by_field}"
    if filters.get("group_by") == "Asset":
        query += ", a.asset_category"
    query += f" ORDER BY month, {group_by_field}"

    # Execute the query with filters
    data = frappe.db.sql(query, filters, as_dict=True)

    # Format the data for the report
    formatted_data = [
        {
            "month": row["month"],
            "group_value": row["group_value"],
            "litres_issued": row["litres_issued"],
            "asset_category": row.get("asset_category") if filters.get("group_by") == "Asset Name" else None
        }
        for row in data
    ]

    return formatted_data
