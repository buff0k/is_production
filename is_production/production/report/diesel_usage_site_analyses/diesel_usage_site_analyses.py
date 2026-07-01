# Copyright (c) 2025, Isambane Mining (Pty) Ltd and contributors
# For license information, please see license.txt

# Diesel Usage Site Analyses Report

import frappe

def execute(filters=None):
    if not filters:
        filters = {}

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
        data = [
            {
                "day": "Total",
                "group_value": group_value,
                "litres_issued": total,
                "asset_category": None,
                "docstatus": "Draft + Submitted"
            }
            for group_value, total in grouped_totals.items()
        ]
    else:
        # Append total rows to the data for detailed view
        for group_value, total in grouped_totals.items():
            data.append({
                "day": "Total",
                "group_value": group_value,
                "litres_issued": total,
                "asset_category": None,
                "docstatus": "Draft + Submitted + Cancelled"
            })

    # Append grand total row always
    data.append({
        "day": "Grand Total",
        "group_value": None,
        "litres_issued": grand_total,
        "asset_category": None,
        "docstatus": "Draft + Submitted"
    })

    # Sort so that Grand Total always last
    def sort_key(x):
        if x["day"] == "Grand Total":
            return ("ZZZZ", 2)  # Always last
        elif x["day"] == "Total":
            return (str(x["group_value"]), 1)
        else:
            return (str(x["group_value"]), 0)

    data.sort(key=sort_key)
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
    if filters.get("group_by") == "Site":
        query = """
        SELECT
            DATE_FORMAT(dds.daily_sheet_date, '%%Y-%%m-%%d') AS day,
            dds.location AS group_value,
            dds.docstatus,
            SUM(COALESCE(dds.litres_issued_equipment, 0)) AS litres_issued
        FROM
            `tabDaily Diesel Sheet` AS dds
        WHERE
            dds.daily_sheet_date IS NOT NULL
            AND dds.docstatus IN (0, 1)
        """

        conditions = []
        if filters.get("date_from"):
            conditions.append("dds.daily_sheet_date >= %(date_from)s")
        if filters.get("date_to"):
            conditions.append("dds.daily_sheet_date <= %(date_to)s")
        if filters.get("site"):
            conditions.append("dds.location = %(site)s")

        if conditions:
            query += " AND " + " AND ".join(conditions)

        query += """
        GROUP BY day, dds.location, dds.docstatus
        ORDER BY day, dds.location
        """

    else:
        if filters.get("group_by") == "Asset Name":
            group_by_field = "dde.asset_name"
        elif filters.get("group_by") == "Asset Category":
            group_by_field = "a.asset_category"
        else:
            group_by_field = "dds.location"

        additional_field = ", a.asset_category" if filters.get("group_by") in ["Asset Name", "Asset Category"] else ""

        query = f"""
        SELECT
            DATE_FORMAT(dds.daily_sheet_date, '%%Y-%%m-%%d') AS day,
            {group_by_field} AS group_value
            {additional_field},
            dds.docstatus,
            SUM(COALESCE(dde.litres_issued, 0)) AS litres_issued
        FROM
            `tabDaily Diesel Entries` AS dde
        INNER JOIN
            `tabDaily Diesel Sheet` AS dds ON dde.parent = dds.name
        LEFT JOIN
            `tabAsset` AS a ON dde.asset_name = a.name
        WHERE
            dds.daily_sheet_date IS NOT NULL
            AND dds.docstatus IN (0, 1)
        """

        conditions = []
        if filters.get("date_from"):
            conditions.append("dds.daily_sheet_date >= %(date_from)s")
        if filters.get("date_to"):
            conditions.append("dds.daily_sheet_date <= %(date_to)s")
        if filters.get("site"):
            conditions.append("dds.location = %(site)s")
        if filters.get("asset_name"):
            conditions.append("dde.asset_name = %(asset_name)s")
        if filters.get("asset_category"):
            conditions.append("a.asset_category = %(asset_category)s")

        if conditions:
            query += " AND " + " AND ".join(conditions)

        query += f" GROUP BY day, {group_by_field}, dds.docstatus"

        if filters.get("group_by") == "Asset Name":
            query += ", a.asset_category"

        query += f" ORDER BY day, {group_by_field}"

    data = frappe.db.sql(query, filters, as_dict=True)

    status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}

    formatted_data = [
        {
            "day": row["day"],
            "group_value": row["group_value"],
            "litres_issued": row["litres_issued"],
            "asset_category": row.get("asset_category") if filters.get("group_by") in ["Asset Name", "Asset Category"] else None,
            "docstatus": status_map.get(row["docstatus"], "Unknown")
        }
        for row in data
    ]

    return formatted_data

